from argparse import ArgumentParser
from hvac import Client as hvacClient
from datetime import datetime
from typing import Dict, List, Any
from jinja2 import Environment, BaseLoader, StrictUndefined
from pathlib import Path

from src.utils import Serializer, DotEnvSerializer

class Config:
    MAPPER_TO_PHASE = {
        '.env.common':  'common',
        '.env':         'local',
        '.env.dev':     'dev',
        '.env.stage':   'stage',
        '.env.prod':    'prod',
    }
    HIERARCHY_GRAPH = {
        'prod':     'stage',
        'stage':    'dev',
        'dev':      'local',
    }

class VaultEngine:
    def __init__(self, pjt_name: str, url: str, token: str):
        self.client = hvacClient(url=url, token=token)
        self.pjt_name = pjt_name

    def get_env(self, phase: str) -> Dict[str, Any]:
        return self._read(f"{self.pjt_name}/{phase}")

    def write_env(self, phase: str, data: Dict[str, str]):
        # 빈 value의 환경변수는 업데이트 하지 않는다.
        data = { k:v for k,v in data.items() if v }
        
        self.client.secrets.kv.v2.create_or_update_secret(
            path=f"{self.pjt_name}/{phase}",
            secret=data
        )

    def _read(self, path: str) -> Dict:
        try:
            return self.client.secrets.kv.v2.read_secret_version(path=path)['data']['data']
        except Exception:
            return {}

class EnvTemplateParser:
    def __init__(self, vault: VaultEngine):
        self.env = Environment(
            loader=BaseLoader(),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True
        )
        self.vault = vault
    
    class Parser:
        def __init__(self, context: Dict[str, Any], phase: str, hierarchy: List[str]) -> None:
            self.phase = phase
            self.context = context
            self.hierarchy = hierarchy
        
        def load_inheritance(self, key):
            try:
                for i_phase in self.hierarchy:
                    if i_phase not in self.context: continue
                    if key not in self.context[i_phase]: continue
                    if not self.context[i_phase][key]: continue
                    
                    return self.context[i_phase][key]
                raise Exception
            except Exception as e:
                return ''
        
        def load(self, key):
            try:
                return self.context[self.phase][key]
            except Exception as e:
                return ''
        
        def load_common(self, key):
            try:
                return self.context['common'][key]
            except Exception as e:
                return ''
    
    def get_parser(self, phase: str, hierarchy: List[str]):
        context = {}
        context['common'] = self.vault.get_env('common')
        for phase in hierarchy:
            context[phase] = self.vault.get_env(phase)
        
        return EnvTemplateParser.Parser(
            context=context,
            phase=phase,
            hierarchy=hierarchy
        )
    
    def get_default_loader(self, key: str):
        return "{{ "+ f"parser.load_inheritance('{key}')" +" }}"

class EnvCompiler:    
    def __init__(self, vault: VaultEngine, serializer: Serializer):
        self.vault = vault
        self.serializer = serializer
        self.parser = EnvTemplateParser(vault)

    def commit(self, phase: str, target_env: str, root_dir: str = '.'):
        # 파라미터 전처리
        root_path = Path(root_dir)
        file_path = root_path / target_env
        
        # env 파일 해석 및 저장.
        with open(file_path, "r") as f:
            target_content = f.read()
        
        env = self.serializer.unserialize(target_content)
        self.vault.write_env(phase, env)

    def render(self, phase: str, template_env: str, root_dir: str = '.'):
        # 파라미터 전처리
        root_path = Path(root_dir)
        template_path = root_path / template_env
        
        env = self.vault.get_env(phase)

        # 기존 파일 역직렬화
        # .env.template 파일을 근거로 존재하지 않는 키를 파악
        if not template_path.exists():
            template_path.touch()
        with open(template_path, "r") as f:
            template_content = f.read()
        template = self.serializer.unserialize(template_content)
        
        # 존재하지 않는 키를 새롭게 기록함
        new_table = {
            key: self.parser.get_default_loader(key)
            for key in env
            if not key in template
        }
        comment=f"작성일자: {datetime.now()}"
        template_content = "\n".join([
            template_content,
            *self.serializer.serialize(new_table, comment=comment),
        ])
        
        with open(template_path, "w") as f:
            f.write(template_content)

    def pull(self, phase: str, target_env: str, template_env: str, root_dir: str = '.'):
        # 파라미터 전처리
        root_path = Path(root_dir)
        file_path = root_path / target_env
        template_path = root_path / template_env
        
        # 상속 순서 설정
        hierarchy = [ phase ]
        
        # 렌더링
        with open(template_path, "r") as f:
            template = f.read()
        parser = self.parser.get_parser(phase=phase, hierarchy=hierarchy)
        rendered = self.parser.env.from_string(template).render(parser=parser)
        
        # 파일 내용 쓰기
        with open(file_path, "w") as f:
            f.write(rendered)

    def build(self, phase: str, target_env: str, template_env: str, root_dir: str = '.'):
        # 파라미터 전처리
        root_path = Path(root_dir)
        file_path = root_path / target_env
        template_path = root_path / template_env
        
        # 상속 순서 설정
        hierarchy = self.get_hierarchy(phase, Config.HIERARCHY_GRAPH)
        hierarchy = list(hierarchy)
        
        # 렌더링
        with open(template_path, "r") as f:
            template = f.read()
        parser = self.parser.get_parser(phase=phase, hierarchy=hierarchy)
        rendered = self.parser.env.from_string(template).render(parser=parser)
        
        # 파일 내용 쓰기
        with open(file_path, "w") as f:
            f.write(rendered)
    
    def get_hierarchy(self, phase: str, graph: dict):
        yield phase
        while phase in graph:
            if phase == graph[phase]: return
            yield graph[phase]
            phase = graph[phase]

class Controller:
    def __init__(self):
        parser = ArgumentParser(description="Env Management CLI")
        parser.add_argument("command", choices=["commit", "push", "pull", "build"])
        parser.add_argument("--pjt", help="Project Name", required=True)
        
        parser.add_argument("--phase", help="Target phase")
        parser.add_argument("--root", default=".", help="Root director`y to read .env files from")
        parser.add_argument("--target", default=".env", help="env file")
        parser.add_argument("--template", default=".env.template", help="env template file")
        
        parser.add_argument("--vault-url", default="http://localhost:8200")
        parser.add_argument("--vault-token", required=True)
        
        args = parser.parse_args()

        vault = VaultEngine(args.pjt, args.vault_url, args.vault_token)
        serializer = DotEnvSerializer()
        compiler = EnvCompiler(vault=vault, serializer=serializer)
        phase = Config.MAPPER_TO_PHASE[args.target]
        args.phase = args.phase or phase

        if args.command == "commit":
            compiler.commit(args.phase, args.target, args.root)
            compiler.render(args.phase, args.template, args.root)
        elif args.command == "push":
            compiler.commit(args.phase, args.target, args.root)
        elif args.command == "pull":
            compiler.pull(args.phase, args.target, args.template, args.root)
        elif args.command == "build":
            compiler.build(args.phase, args.target, args.template, args.root)

if __name__ == "__main__":
    Controller()
