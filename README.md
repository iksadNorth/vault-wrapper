# 환경 변수 관리 시스템

이 프로젝트는 MSA(Microservices Architecture) 환경에서 환경 변수를 효율적이고 안전하게 관리하기 위한 시스템입니다. HashiCorp Vault를 활용하여 환경 변수를 중앙에서 통제하고, 페이즈(phase)별 상속 및 버전 관리를 통해 유지보수를 용이하게 합니다.

## 주요 기능

*   **페이즈 기반 설정**: `local`, `dev`, `prod` 등 각 서버의 페이즈에 따라 환경 변수를 관리합니다.
*   **변수 상속**: 페이즈 간 변수 값 상속을 지원하여 중복을 줄이고 유지보수를 쉽게 합니다.
*   **Vault 통합**: Vault를 통해 환경 변수를 안전하게 저장하고, 사용자별 인가 및 토큰 갱신을 통해 보안을 강화합니다.
*   **버전 관리/백업**: 데이터 변경 시 주기적 또는 요청 시 백업을 수행하여 버전 관리를 용이하게 합니다.
*   **공통 환경 변수**: 서버 간 공통으로 사용되는 환경 변수(`env.common`)를 별도로 관리합니다.

## 시스템 프로세스

이 시스템은 크게 세 가지 명령어를 통해 운영됩니다:

1.  **`commit`**: 
    *   실행 루트 경로의 `.env`, `.env.dev`, `.env.prod` 등의 `.env.*` 파일을 읽어들입니다.
    *   각 파일의 변수를 파싱하고, 이를 Vault에 일괄 등록합니다.
    *   등록된 모든 키를 기반으로 `.env.template` 파일을 생성합니다.
    *   `.env.common` 및 `.env.common.template` 파일도 함께 관리합니다.

2.  **`pull`**: 
    *   `vault`에 저장된 변수 및 `.env.template`를 기반으로 `.env.local`, `.env.dev`, `.env.prod`와 같은 페이즈별 `.env` 파일을 생성합니다.
    *   이 과정에서는 상속 개념이 적용되지 않고, 실제 `vault`에 설정된 값으로만 렌더링됩니다. 정의되지 않은 항목은 빈칸으로 처리됩니다.
    *   환경 값이 비어있어도 오류를 발생시키지 않으며, 주로 팀원 간 환경 값 공유 및 드라이 런(dry run) 목적으로 사용됩니다.

3.  **`build`**: 
    *   특정 페이즈를 타겟으로 하여 접미사 없는 단일 `.env` 파일을 생성합니다.
    *   페이즈 간 변수 상속 규칙이 적용됩니다. (`local > [cash.dev, order.dev]`, `order.dev > order.prod` 등 사용자가 정의한 상속 그래프 활용)
    *   `Key={{ loadInheritance('keyname') }}`: 상속 규칙에 따라 변수 값을 가져옵니다.
    *   `Key={{ load('keyname') }}`: 상속 없이 해당 키의 값을 가져옵니다.
    *   `Key={{ loadCommon('keyname') }}`: 공통 환경 변수에서 값을 가져옵니다.
    *   실제로 사용된 변수 값의 출처 페이즈가 주석으로 표기되어 추적을 용이하게 합니다.
    *   상속을 요구하지 않음에도 불구하고 값이 존재하지 않으면 빌드 오류를 발생시킵니다.

## 아키텍처

*   **MVC 패턴**: `Controller`, `VaultEngine`, `EnvCompiler` 클래스로 구성된 MVC 아키텍처를 따릅니다. 서비스 코드는 클래스로 구현되어 유지보수를 최소화합니다.
*   **CLI 기반**: `argparse`를 사용하여 명령줄 인터페이스로 구현됩니다.
*   **템플릿 엔진**: Jinja2를 활용하여 환경 변수 템플릿을 렌더링합니다.
*   **EnvTemplateParser**: 템플릿 관련 로직을 분리하여 `EnvTemplateParser` 클래스에서 관리합니다. (예정)

## 사용 방법

```bash
# commit 명령어 예시
python main.py commit --root ./ --vault-url http://localhost:8200 --vault-token YOUR_VAULT_TOKEN

# pull 명령어 예시
python main.py pull --vault-url http://localhost:8200 --vault-token YOUR_VAULT_TOKEN

# build 명령어 예시
python main.py build --phase cash.dev --vault-url http://localhost:8200 --vault-token YOUR_VAULT_TOKEN
``` 