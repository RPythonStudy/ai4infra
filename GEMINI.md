# GEMINI.md - AI Agent Guidelines
> 이 문서는 Gemini Code Assistant가 리 프로젝트를 이해하고 코드를 생성할 때 반드시 참고해야 할 기술적 명세와 지침을 담고 있습니다.

## 1. Project Context (프로젝트 개요)
> **중요**: 이 프로젝트는 RPython 연구회에서 개발하는 서비스들에서 필요한 공통 인프라(보안, 데이터베이스 등)를 구축/관리하는 플랫폼입니다.  
> 원본 템플릿: `rpy-quarto-template` 기반으로 생성되었습니다.

- **역할**: 사용자 요청 시 인프라 구축, 설정 자동화, 서비스 연동 코드를 제안합니다.
- **핵심 목표**: 오픈소스를 활용한 안정적인 인프라 서비스 제공.

## 2. Tech Stack & Environment (기술 스택 및 환경)
- **OS**: Linux (주) / Windows / macOS (지원). 
    - **주의**: 코드를 제안할 때 OS 간 경로 구분자(`\` vs `/`)와 권한 문제를 반드시 고려하고, 필요 시 분기 처리(`sys.platform`)를 제안해야 합니다.
- **Languages**: 
    - Python (3.x): 주요 로직 및 자동화 스크립트. 구체적인 버전은 `.python-version` 파일 참조.
    - R: 데이터 분석 및 리포팅 (Quarto 연동). 구체적인 버전은 `.R-version` 파일 참조.
- **Virtual Environment**: 
    - Python: `.venv` (표준 `venv` 모듈 사용).
    - R: `renv` (패키지 버전 관리).
- **Configuration**: `.env` 파일에서 주요 환경변수(PROJECT_NAME, LOG_LEVEL 등)를 로드합니다.

## 3. Coding Standards (코딩 컨벤션)

### 3.1 Python Import Path
- **기준 경로**: `{PROJECT_ROOT}/src`
- **규칙**: `src` 폴더가 `sys.path`에 추가되도록 설정되어 있습니다. 따라서 import 시 `src.`가 아닌 내부 모듈명을 바로 사용합니다.
- **예시**: `src/common/logger.py`를 사용할 때 -> `from common.logger import log_info`

### 3.2 Logging Policy
print() 대신 반드시 아래의 전용 로거를 사용합니다. 로그 폴더(`logs/`)는 시스템 보안 정책상 스크립트가 자동 생성하거나 사용자가 직접 생성해야 합니다.

- **Python**: `src/common/logger.py`
    - 사용법: `from common.logger import log_info, log_error`
    - 설정: `config/logging.yml` 및 `.env` 참조.
- **R**: `src/R/logger.R`
    - 함수: `log_debug`, `log_info`, `log_warn`, `log_error`, `log_critical`

**Logging Best Practice:**
- **Verbose Debugging**: 스크립트 실행 흐름을 파악할 수 있도록 주요 단계(Step)와 분기점마다 `log_debug`를 적극적으로 사용하여 "의미 있는 단위"의 로그를 남깁니다.
- **Level Control**: 개발 시에는 `.env`의 `LOG_LEVEL=DEBUG`로 상세 내용을 확인하고, 운영 시에는 `INFO` 이상으로 설정하여 출력을 조절합니다.
- **Standardized Format (ELK Ready)**: 의료 정보 감사(Audit) 및 ELK 스택 연동을 위해, `common.logger`가 제공하는 표준 포맷을 절대적으로 준수해야 합니다. 임의의 `print` 사용은 금지됩니다.

### 3.3 AI Script Guidelines
- **간결성**: 극단적으로 직관적이고 디버깅하기 쉬운 코드를 우선 제안합니다.
- **오류 대응**: 환경변수 누락, 권한 오류 등 예상되는 문제에 대해 에러 메시지 기반 수정 가이드를 주석이나 로그로 포함합니다.

## 4. Project Structure (프로젝트 구조)
프로젝트의 세부 아키텍처와 상세 설명은 `documentations/` 폴더 내의 각 markdown 파일을 참조하십시오.

**주요 서비스 문서:**
- [Security Architecture](documentations/security-architecture.md): 보안 원칙 및 운영 환경 전략.
- [Vault Service Guide](documentations/vault.md): 보안 및 가명화 키 관리 서비스 정의 및 구축 가이드.
- [Vaultwarden Service Guide](documentations/vaultwarden.md): 패스워드 매니저(Bitwarden 호환) 서비스 정의 및 선정 배경.

- `docs/`: Quarto 렌더링 결과물 (GitHub Pages 등 웹 게시용). **변경 불가(템플릿 표준)**.
- `posts/`: 기술 블로그/문서화용 Quarto(.qmd) 소스 파일.
- `documentations/`: AI Agent 및 개발자를 위한 상세 기술 문서 저장소.
- `template/`: 서비스 컨테이너용 기본 설정 파일(Docker Compose 등) 보관소. 서비스 생성 시 복사하여 사용.
- `scripts/`: 설치, 셋업, 백업 등 자동화 스크립트.
- `src/`: 주요 소스 코드 (Python 및 R).
- `config/`: 설정 파일 (logging, nginx 등).
- `logs/`: (Git 제외) 로그 파일 저장소.

## 5. Configuration Policy (설정 원칙)
> **철학**: "사용자가 설정을 통해 시스템을 배우게 하되, 위험한 자유는 제한한다."

1.  **설정 노출 (Educational Configuration)**:
    - 각 서비스의 포트, 메모리 제한 등 *변경해도 안전한 값*은 `config/<service>.yml`을 통해 사용자가 직접 설정할 수 있도록 하드코딩을 지양합니다.
    - 이를 통해 사용자가 설정 파일을 작성하며 해당 서비스의 동작 원리를 자연스럽게 이해하도록 유도합니다.

2.  **경로 고정 (Convention over Configuration)**:
    - **Data Mount Path**: 컨테이너의 데이터 저장 경로(`-v /data:/...`) 등은 보안상 위험하거나 구조를 복잡하게 만들 수 있으므로 사용자 설정에서 제외(주석으로만 설명)하고 **코드 레벨에서 고정**합니다.
    - 이는 사용자 실수로 인한 데이터 유실/보안 사고를 방지하고, 유지보수 코드를 간결하게 유지하기 위함입니다. (현재 `vault.yml` 적용 중, 전 서비스 확대 예정)

3.  **변수 명명 및 관리 (Variable Strategy)**:
    - **.env**: 전역 변수 및 `env_vars`(공식 환경변수)를 정의하며, 서비스명 주석으로 구분합니다.
    - **config/*.yml**:
        - `env_vars`: 컨테이너 내부로 전달되는 공식 환경변수 (예: `VAULT_ADDR`).
        - `compose_vars`: `docker-compose.yml` 구성에 사용되는 치환용 변수 (예: `PORT`, `VAULT_MEM_LIMIT`).
    - **작동 원리**: 전용 스크립트가 위 설정들을 병합하여, 서비스 실행 시점에 해당 서비스 전용 `.env` 파일을 동적으로 생성합니다.

## 6. Automation & Workflow (자동화)
`Makefile`을 통해 주요 작업을 자동화합니다. 새로운 기능을 추가할 때 가급적 Makefile 타겟이나 `scripts/` 내의 파이썬 스크립트로 모듈화하십시오.

- `make setup`: 초기 환경 설정 (venv, log 폴더, syspath 등).
- `make venv`: 가상환경 생성 및 패키지 설치.
- `source .venv/bin/activate`: 가상환경 활성화 (Linux/Mac).
