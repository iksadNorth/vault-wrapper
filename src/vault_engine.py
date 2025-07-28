from hvac import Client as hvacClient
from typing import Dict, Any

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

    def append_env(self, phase: str, data: Dict[str, str]):
        # 빈 value의 환경변수는 업데이트 하지 않는다.
        data = { k:v for k,v in data.items() if v }
        
        self.client.secrets.kv.v2.patch(
            path=f"{self.pjt_name}/{phase}",
            secret=data
        )

    def _read(self, path: str) -> Dict:
        try:
            return self.client.secrets.kv.v2.read_secret_version(path=path)['data']['data']
        except Exception:
            return {}
