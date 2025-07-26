import argparse
import hvac
import json
from collections import defaultdict
from datetime import datetime
from typing import Dict, List
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
    TEMPALTE_FILE = '.env.template'
    INCLUDE_TO_TEMPALTE = {
        'local',
        'dev',
        'stage',
        'prod',
    }

class VaultEngine:
    def __init__(self, pjt_name: str, url: str, token: str):
        self.client = hvac.Client(url=url, token=token)
        self.pjt_name = pjt_name

    def get_env(self, phase: str) -> Dict[str, str]:
        return self._read(f"{self.pjt_name}/{phase}")

    def get_inheritance(self) -> Dict[str, List[str]]:
        return self._read(f"{self.pjt_name}/inheritance")

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

    def list_phases(self) -> List[str]:
        try:
            response = self.client.secrets.kv.v2.list_secrets(path=f"{self.pjt_name}/")
            return [key.replace('/', '') for key in response.get('data', {}).get('keys', [])]
        except Exception as e:
            print(f"Error listing phases from Vault: {e}")
            return []

    def write_inheritance(self, data: Dict[str, List[str]]):
        self.client.secrets.kv.v2.create_or_update_secret(
            path=f"{self.pjt_name}/inheritance",
            secret=data
        )

class EnvTemplateParser:
    def __init__(self, vault: VaultEngine):
        self.vault = vault
        self.env = Environment(
            loader=BaseLoader(),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True
        )
        self.config = Config()

    def render_preview(self, phase: str, template_name: str = "default") -> str:
        with open(self.config.TEMPALTE_FILE, "r") as f:
            template = f.read()
        context = self.vault.get_env(phase)
        return self.env.from_string(template).render(**context)

    def render_build(self, phase: str) -> str:
        with open(self.config.TEMPALTE_FILE, "r") as f:
            template = f.read()
        inheritance_data = self._resolve_inheritance(phase)
        
        def load_inheritance(key):
            value, source_phase = inheritance_data.get(key, ("", ""))
            if value == "" and self._is_inheritance_required(key, template):
                raise ValueError(f"Missing required key during build (inheritance): {key}")
            return f"{value} # From {source_phase}" if source_phase else value

        def load(key):
            env_data = self.vault.get_env(phase)
            value = env_data.get(key, "")
            if value == "" and self._is_load_required(key, template):
                raise ValueError(f"Missing required key during build (load): {key}")
            return value

        def load_common(key):
            common_env = self.vault.get_env('common')
            value = common_env.get(key, "")
            if value == "" and self._is_load_common_required(key, template):
                raise ValueError(f"Missing required key during build (load common): {key}")
            return value

        self.env.globals['load_inheritance'] = load_inheritance
        self.env.globals['load'] = load
        self.env.globals['load_common'] = load_common

        rendered_env = self.env.from_string(template).render()
        return rendered_env

    def _resolve_inheritance(self, phase):
        result = {}
        inheritance = self.vault.get_inheritance()
        visited = set()
        stack = [phase]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            env = self.vault.get_env(current)
            for k, v in env.items():
                if k not in result:
                    result[k] = (v, current)
            parents = inheritance.get(current)
            if parents:
                stack.extend(parents if isinstance(parents, list) else [parents])
        return result

    def _is_inheritance_required(self, key, template):
        return f"{{ {{ load_inheritance('{key}') }}" in template

    def _is_load_required(self, key, template):
        return f"{{ {{ load('{key}') }}" in template

    def _is_load_common_required(self, key, template):
        return f"{{ {{ load_common('{key}') }}" in template

class EnvCompiler:    
    def __init__(self, vault: VaultEngine, serializer: Serializer):
        self.vault = vault
        self.serializer = serializer
        self.parser = EnvTemplateParser(vault)
        self.config = Config()

    def commit(self, target_env: str, template_env: str, root_dir: str = '.'):
        # 파라미터 전처리
        root_path = Path(root_dir)
        all_keys = defaultdict(set)
        
        # 해석 대상 .env 파일 선정
        env_files = [
            f for f in root_path.iterdir() 
            if f.is_file() 
            and f.name in self.config.MAPPER_TO_PHASE.keys()
        ]
        
        # env 파일 해석 및 저장.
        for file_path in env_files:
            with open(file_path, "r") as f:
                content = f.read()
            
            phase: str|None = self.config.MAPPER_TO_PHASE.get(file_path.name)
            if not phase: continue
            
            env = self.serializer.unserialize(content)
            all_keys[phase] = set(env.keys())
            self.vault.write_env(phase, env)

        # 기존 파일 역직렬화
        with open(self.config.TEMPALTE_FILE, "r") as f:
            content = f.read()
        
        # .env.template 파일을 근거로 존재하지 않는 키를 파악
        template = self.serializer.unserialize(content)
        now_keytable = set()
        for phase in self.config.INCLUDE_TO_TEMPALTE:
            now_keytable.update(all_keys[phase])
        
        # 존재하지 않는 키를 새롭게 기록함
        new_table = {
            key: f"{{ load_inheritance('{key}') }}"
            for key in now_keytable
            if not key in template
        }
        content += f"""{ self.serializer.serialize(new_table, comment=f"작성일자: {datetime.now()}") }"""
        
        with open(self.config.TEMPALTE_FILE, "a") as f:
            f.write(content)

    def pull(self) -> Dict[str, str]:
        envs = {}
        all_phases_in_vault = self.vault.list_phases()
        
        # .env 목록 가져오기
        
        # 각 .env를 .env.template 내용을 근거로 반영
        
        common_template_name = "common"
        common_env_content = self.parser.render_preview("common", common_template_name)
        with open(Path(".env.common"), "w") as f:
            f.write(common_env_content)
        envs["common"] = common_env_content

        for phase in all_phases_in_vault:
            if phase == "common":
                continue
            env_content = self.parser.render_preview(phase)
            with open(Path(f".env.{phase}"), "w") as f:
                f.write(env_content)
            envs[phase] = env_content
        return envs

    def build(self, phase: str) -> str:
        env = self.parser.render_build(phase)

        with open(Path(".env"), "w") as f:
            f.write(env)
        return env

class Controller:
    def __init__(self):
        parser = argparse.ArgumentParser(description="Env Management CLI")
        parser.add_argument("command", choices=["commit", "pull", "build"])
        parser.add_argument("--phase", help="Target phase")
        parser.add_argument("--root", default=".", help="Root directory to read .env files from")
        parser.add_argument("--vault-url", default="http://localhost:8200")
        parser.add_argument("--vault-token", required=True)
        args = parser.parse_args()

        vault = VaultEngine('test-pjt', args.vault_url, args.vault_token)
        serializer = DotEnvSerializer()
        compiler = EnvCompiler(vault=vault, serializer=serializer)

        if args.command == "commit":
            compiler.commit(args.root)
        elif args.command == "pull":
            print(json.dumps(compiler.pull(), indent=4))
        elif args.command == "build":
            if not args.phase:
                raise Exception("--phase required for build")
            print(compiler.build(args.phase))

if __name__ == "__main__":
    Controller()
