# Conf Manager

이 프로젝트는 HashiCorp Vault와 Jinja2 템플릿 엔진을 활용하여 `.env` 환경 변수 파일을 효율적으로 관리하는 CLI 도구입니다. 다양한 환경(개발, 스테이징, 프로덕션 등)에 걸쳐 환경 변수를 중앙에서 관리하고, 템플릿을 통해 쉽게 환경 파일을 생성하고 업데이트할 수 있도록 설계되었습니다.

## 주요 기능

이 도구는 다음과 같은 명령어를 지원합니다:

-   `commit`: 로컬 `.env` 파일을 읽어 특정 단계(phase)의 Vault에 환경 변수를 저장합니다.
-   `push`: `commit`과 동일하게 로컬 `.env` 파일을 Vault에 저장합니다. (현재 구현은 `commit`과 동일)
-   `pull`: Vault에서 특정 단계의 환경 변수를 가져와 `.env.template`을 기반으로 `.env` 파일을 생성합니다.
-   `build`: Vault에서 환경 변수의 계층 구조(예: dev -> stage -> prod)를 고려하여 상위 단계의 환경 변수를 상속받아 `.env` 파일을 생성합니다.

## 프로젝트 구조

```
conf-manager/
├── docker-compose.yml     # Vault 서버 실행을 위한 Docker Compose 파일
├── main.py                # 프로그램 진입점
├── pyproject.toml         # 프로젝트 의존성 관리 (Poetry)
├── README.md              # 프로젝트 설명 (현재 파일)
├── src/
│   ├── config.py          # 전역 설정 및 상수 정의
│   ├── controller.py      # CLI 인자 파싱 및 핵심 로직 제어
│   ├── env_compiler.py    # 환경 변수 컴파일 및 관리 로직
│   ├── template_parser.py # Jinja2 템플릿 파싱 및 환경 변수 로딩
│   ├── utils.py           # 환경 변수 직렬화/역직렬화 유틸리티
│   └── vault_engine.py    # HashiCorp Vault 연동
└── vault/                 # Vault 데이터 디렉토리 (Docker Compose 사용 시)
```

## 핵심 모듈 설명

### `src/controller.py`

이 모듈은 CLI(Command Line Interface) 인자를 파싱하고, 파싱된 인자에 따라 `VaultEngine` 및 `EnvCompiler` 클래스를 초기화하여 적절한 환경 변수 관리 명령을 실행하는 역할을 합니다. 사용자는 `--pjt` (프로젝트 이름)와 `--vault-token`을 필수로 제공해야 하며, `--phase`, `--root`, `--target`, `--template`과 같은 추가 옵션을 사용할 수 있습니다.

### `src/config.py`

프로젝트 전반에 사용되는 상수와 설정 값을 정의합니다.

-   `VAULT_URL`: HashiCorp Vault 서버의 기본 URL입니다. (기본값: `http://localhost:8200`)
-   `MAPPER_TO_PHASE`: `.env` 파일명과 해당 환경 변수 단계(phase)를 매핑합니다.
    예: `.env.dev` -> `dev`
-   `HIERARCHY_GRAPH`: 환경 변수 상속 계층 구조를 정의합니다.
    예: `prod`는 `stage`를 상속받고, `stage`는 `dev`를 상속받습니다. 이는 `build` 명령 실행 시 환경 변수 값을 결정하는 데 사용됩니다.

```python
// ... existing code ...
class Config:
    VAULT_URL = "http://localhost:8200"
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
// ... existing code ...
```

### `src/vault_engine.py`

`hvac` 라이브러리를 사용하여 HashiCorp Vault와 통신하는 역할을 합니다.

-   `__init__(self, pjt_name: str, url: str, token: str)`: Vault 클라이언트를 초기화합니다.
-   `get_env(self, phase: str)`: 특정 `phase`의 Vault에서 환경 변수를 가져옵니다.
-   `write_env(self, phase: str, data: Dict[str, str])`: 특정 `phase`의 Vault에 환경 변수를 저장합니다. 이 때, 빈 값을 가진 환경 변수는 저장되지 않습니다.

### `src/utils.py`

환경 변수 파일(`dotenv`)의 직렬화(serialization) 및 역직렬화(deserialization)를 담당하는 유틸리티 클래스를 포함합니다.

-   `Serializer` (ABC): 직렬화 및 역직렬화를 위한 추상 기본 클래스입니다.
-   `DotEnvSerializer`: `.env` 파일 형식에 특화된 직렬화/역직렬화 구현입니다.
    -   `serialize`: 딕셔너리 형태의 환경 변수를 `.env` 형식의 문자열로 변환합니다.
    -   `unserialize`: `.env` 형식의 문자열을 딕셔너리 형태로 파싱합니다. 주석(`\#`) 및 빈 라인을 무시하고, 값 안에 포함된 주석도 올바르게 처리합니다.

### `src/env_compiler.py`

환경 변수의 `commit`, `render`, `pull`, `build`와 같은 핵심 로직을 구현합니다.

-   `commit(self, phase: str, target_env: str, root_dir: str = '.')`: 로컬 파일(`target_env`)의 환경 변수를 읽어 Vault에 저장합니다.
-   `render(self, phase: str, template_env: str, root_dir: str = '.')`: Vault에 저장된 환경 변수를 기반으로 `template_env` 파일에 새로운 환경 변수 항목을 추가합니다. 이는 주로 `.env.template` 파일 업데이트에 사용됩니다.
-   `pull(self, phase: str, target_env: str, template_env: str, root_dir: str = '.')`: `template_env` 파일을 템플릿으로 사용하여 Vault에서 가져온 환경 변수로 `target_env` 파일을 생성합니다. 이 때 `phase`에 해당하는 환경 변수만 로드됩니다.
-   `build(self, phase: str, target_env: str, template_env: str, root_dir: str = '.')`: `pull`과 유사하지만, `config.py`에 정의된 `HIERARCHY_GRAPH`를 사용하여 상위 단계의 환경 변수(예: `dev`, `stage`, `prod` 순)를 함께 로드하여 `target_env` 파일을 생성합니다.

### `src/template_parser.py`

Jinja2 템플릿 엔진을 사용하여 `.env.template` 파일을 파싱하고 Vault에서 가져온 환경 변수 데이터로 렌더링하는 역할을 합니다.

-   `EnvTemplateParser`: Jinja2 환경을 설정하고, Vault에서 환경 변수를 가져오는 데 사용됩니다.
-   `Parser` (내부 클래스): 템플릿 내에서 호출될 함수들을 정의합니다.
    -   `load_inheritance(self, key)`: 계층 구조(`HIERARCHY_GRAPH`)에 따라 환경 변수 `key`의 값을 로드합니다. 어떤 단계에서 값이 로드되었는지 주석으로 표시됩니다.
    -   `load(self, key)`: 현재 `phase`에 해당하는 환경 변수 `key`의 값을 로드합니다.
    -   `load_common(self, key)`: `common` 단계의 환경 변수 `key`의 값을 로드합니다.
-   `get_parser(self, phase: str, hierarchy: List[str])`: Jinja2 템플릿 렌더링에 필요한 컨텍스트(`Parser` 인스턴스)를 생성합니다. 이때 `common` 환경 변수와 지정된 `hierarchy`의 환경 변수들이 모두 로드됩니다.
-   `get_default_loader(self, key: str)`: `.env.template`에 새로운 환경 변수를 추가할 때 사용되는 기본 Jinja2 템플릿 로더 문자열을 생성합니다. 

## 프로젝트 빌드
```
uv pip install pyinstaller 
uv run pyinstaller main.py --name vault-wrapper
./dist/vault-wrapper/vault-wrapper {command}
```
