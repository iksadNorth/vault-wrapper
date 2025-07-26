from typing import Iterator
from abc import ABC, abstractmethod

class Serializer(ABC):
    @abstractmethod
    def serialize(self, table: dict, comment: str = '') -> Iterator[str]:
        raise NotImplementedError
    
    @abstractmethod
    def unserialize(self, content: str) -> dict:
        raise NotImplementedError

class DotEnvSerializer(Serializer):
    def serialize(self, table: dict, comment: str = '') -> Iterator[str]:
        if comment:
            yield f'\n# {comment}'
        for key, val in table.items():
            yield f'{key}={val}'
    
    def unserialize(self, content: str) -> dict:
        result = {}
        for line in content.split('\n'):
            line = line.strip()
            if not line: continue
            if line.startswith("#"): continue
            if "=" in line:
                key, val = line.split("=", 1)
                result[key] = val
        return result

class JsonSerializer(Serializer):
    def serialize(self, table: dict, comment: str = '') -> Iterator[str]:
        raise NotImplementedError
    
    def unserialize(self, content: str) -> dict:
        raise NotImplementedError

class YamlSerializer(Serializer):
    def serialize(self, table: dict, comment: str = '') -> Iterator[str]:
        raise NotImplementedError
    
    def unserialize(self, content: str) -> dict:
        raise NotImplementedError