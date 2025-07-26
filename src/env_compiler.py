from datetime import datetime
from pathlib import Path
from src.vault_engine import VaultEngine
from src.config import Config
from src.template_parser import EnvTemplateParser

from src.utils import Serializer

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