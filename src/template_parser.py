from typing import Dict, List, Any
from jinja2 import Environment, BaseLoader, StrictUndefined
from src.vault_engine import VaultEngine

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
                    
                    value = self.context[i_phase][key]
                    return f"{value}\t\t# From '{i_phase}'"
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