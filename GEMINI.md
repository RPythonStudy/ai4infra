# GEMINI.md - AI Agent Guidelines
> 이 문서는 Gemini Code Assistant가 리 프로젝트를 이해하고 코드를 생성할 때 반드시 참고해야 할 기술적 명세와 지침을 담고 있습니다.

## 0. Language Policy (언어 정책) - **Start Here**
> **최우선 지침**: 본 프로젝트의 모든 커뮤니케이션은 **한국어(Korean)**를 원칙으로 합니다.

1.  **Scope (적용 범위)**:
    -   채팅 대화 (Chat Responses)
    -   사고 과정 및 상태 요약 (Task Status/Summary)
    -   기술 문서 및 주석 (Documentation & Comments)
2.  **Terminology (용어 사용)**:
    -   모든 내용은 한글로 서술하되, 전문 용어는 이해를 돕기 위해 최초 1회 또는 필요한 경우 **한글(English)** 형태로 병기합니다.
    -   유머나 은유적인 표현을 배제하고, **명확하고 전문적인 어조(Professional Tone)**를 유지합니다.

## 0.1 Core Principles (핵심 원칙)
> **기본 철학**: 이 프로젝트는 "서툰 사용자(Non-Expert User)"와 "디테일이 약한 관리자(Maintainer)"를 위해 존재합니다.

1.  **Remote Support Friendly (원격 지원 최적화)**:
    -   문제가 발생했을 때, 사용자가 당황하지 않고 화면에 출력된 "에러 메시지"만 읽어주면, 전화기 너머의 개발자가 즉시 원인을 파악할 수 있어야 합니다.
    -   "알 수 없는 오류"는 죄악입니다. 모든 예외 처리는 **"어디서(Where), 왜(Why), 어떻게 해결(How)"** 하라는 정보를 포함해야 합니다.

2.  **Extreme Maintenance Simplicity (극단적 유지보수 용이성)**:
    -   **"돌아가기만 하는 복잡한 코드"보다 "읽히는 바보 같은 코드"가 낫습니다.**
    -   유지보수 담당자(나)가 6개월 뒤에 코드를 봐도 즉시 이해하고 수정할 수 있어야 합니다.

3.  **World Class Security via Open Source (오픈소스 기반 세계 최고 보안)**:
    -   상용 솔루션 없이, 검증된 오픈소스(Docker, Vault, Nginx 등)만을 조합하여 Palantir/Epic 수준의 보안을 구현합니다.
    -   **The 12 Pillars of World Class Security**:
        1.  **Immutable Infrastructure**: 서버/컨테이너 수정 불가 (Read-only).
        2.  **WAF**: 웹 해킹(SQLi, XSS) 원천 차단.
        3.  **Network Segmentation**: 서비스 간 통신 격리.
        4.  **DDoS/Rate Limiting**: 트래픽 폭주 방어.
        5.  **Zero Trust Gateway**: 단일 관문(Gateway) 통제.
        6.  **Centralized Identity (OIDC)**: 통합 인증 (Google/Keycloak).
        7.  **MFA**: 다중 인증 강제.
        8.  **RBAC**: 최소 권한 원칙.
        9.  **Secret Management (Vault)**: 코드 내 비밀번호 제거 (No Hardcoded Secrets).
        10. **Split Knowledge**: 물리 키(USB)와 논리 키(Password) 분리.
        11. **E2E Encryption**: 내부망 포함 전 구간 암호화.
        12. **Audit Logging**: 위변조 불가능한 감사 로그 (HIPAA).

4.  **Extreme Conciseness (극단적 간결성)**:
    -   모든 스크립트와 설정은 극단적으로 간결해야 합니다.
    -   중복을 제거하고, "한 줄로 설명 가능한" 로직을 지향합니다.

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

### 2.1 Windows WSL2 Optimization (Critical)
> **Disk Space Reclamation**: WSL2의 가상 디스크(`ext4.vhdx`)는 기본적으로 용량이 늘어나기만 하고 줄어들지 않습니다.
- **Requirement**: 윈도우 사용자 홈 디렉터리(`%UserProfile%`)에 `.wslconfig` 파일을 생성하고 아래 내용을 추가해야 합니다.
  ```ini
  [wsl2]
  sparseVhd=true
  ```
- **Effect**: 이 설정을 통해 리눅스에서 파일을 삭제하면 윈도우의 호스트 디스크 용량도 자동으로 회복됩니다. (Docker 로그 폭주 사고 예방 필수)

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

### 3.4 Container Naming Convention
- **Prefix**: 모든 컨테이너 이름은 반드시 `ai4infra-` 접두사를 붙여야 합니다.
- **Format**: `ai4infra-{service_name}` (예: `ai4infra-vault`, `ai4infra-postgres`)
- **Reason**: 
    - `stop_container` 등 관리 스크립트가 이름 기반으로 필터링(`filter name=ai4infra-{service}`)을 수행합니다.
    - 동일 서버 내 다른 프로젝트 컨테이너와의 충돌을 방지합니다.

## 4. Project Structure (프로젝트 구조)
프로젝트의 세부 아키텍처와 상세 설명은 `documentations/` 폴더 내의 각 markdown 파일을 참조하십시오.

**주요 서비스 문서 및 카테고리:**

**1. Core Infrastructure (필수/기반)**
- [Security Architecture](documentations/security-architecture.md): 보안 원칙 및 운영 전략.
- [Nginx Service Guide](documentations/nginx.md): 통합 리버스 프록시 및 TLS Termination. (Gateway)
- [PostgreSQL Service Guide](documentations/postgres.md): 공통 관계형 데이터베이스.
- [Vault Service Guide](documentations/vault.md): 보안 키 및 시크릿 관리.

**2. Application Services (선택)**
- [Vaultwarden Service Guide](documentations/vaultwarden.md): 패스워드 매니저 (Vaultwarden).

**3. Identity Management (선택 - SSO/계정)**
- [OpenLDAP Guide](documentations/ldap.md): 중앙 계정 저장소 (Directory Service).
- [Keycloak Guide](documentations/keycloak.md): 통합 인증 및 SSO 공급자 (IdP).

**4. Observability (선택 - 로그/모니터링)**
- [ELK Stack Guide](documentations/elk.md): 로그 수집 및 시각화 (Elasticsearch, Logstash, Kibana).
- [Filebeat Guide](documentations/filebeat.md): 로그 수집 에이전트.

**5. Medical & AI Data Ops (선택 - 의료/AI 특화)**
- [HAPI FHIR Guide](documentations/fhir.md): 차세대 의료 데이터 표준(FHIR) 저장소.
- [Orthanc Guide](documentations/orthanc.md): 의료 영상(DICOM) 저장 및 PACS 서버.
- [Slicer Guide](documentations/slicer.md): 3D Slicer 이미지 분석 및 자동화 플랫폼.
- [OpenREM Guide](documentations/openrem.md): 방사선량 관리 및 분석 플랫폼 (벤치마킹/비교용).
- [MLflow Guide](documentations/mlflow.md): 의료 AI 모델 실험 추적 및 생명주기 관리.

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
        - **Service Identity**: 모든 설정 파일은 반드시 맨 위에 `service: enable: true` (또는 false) 형식을 따라야 합니다.
        - **Passwords**: 비밀번호와 같은 민감 정보는 yml 파일에 직접 적지 않고, `.env` 파일에 정의한 후 이를 참조하거나 주입받도록 구성해야 합니다. (예: Postgres, LDAP)
        - `env_vars`: 컨테이너 내부로 전달되는 공식 환경변수.
        - `compose_vars`: `docker-compose.yml` 구성에 사용되는 치환용 변수. 특히 **Port**는 하드코딩하지 않고 여기서 변수(`LDAP_PORT` 등)로 정의하여 충돌을 방지합니다.
    - **Docker Compose Templates**:
        - **Ports**: `${VAR:-Default}` 형식으로 변수화하여 `compose_vars`와 연동합니다.
        - **Images**: 버전 태그를 명시(`1.32.0`)하고, `config/*.yml`에는 중복 기재하지 않습니다.
    - **작동 원리**: 전용 스크립트가 위 설정들을 병합하여, 서비스 실행 시점에 해당 서비스 전용 `.env` 파일을 동적으로 생성합니다.

4.  **네트워크 바인딩 (Network Binding)**:
    - 컨테이너 내부의 서비스 Listen Address는 반드시 **와일드카드(`0.0.0.0`)**를 사용해야 합니다.
    - `127.0.0.1`(Loopback) 사용 시 컨테이너 외부(Host 및 타 컨테이너)에서의 접근이 차단됩니다.

## 6. Automation & Workflow (자동화)
`Makefile`을 통해 주요 작업을 자동화합니다. 새로운 기능을 추가할 때 가급적 Makefile 타겟이나 `scripts/` 내의 파이썬 스크립트로 모듈화하십시오.

- `make setup`: 초기 환경 설정 (venv, log 폴더, syspath 등).
- `make venv`: 가상환경 생성 및 패키지 설치.
- `source .venv/bin/activate`: 가상환경 활성화 (Linux/Mac).

## 6.3 Offline Installation Strategy (Closed Network)
> **대상**: 병원 내부망 등 인터넷 접근이 차단된 폐쇄망 환경.
> **전제**: 외부에서 미리 빌드된 Docker Image(.tar)와 소스 코드를 USB 등의 물리 매체로 반입합니다.

### A. Image Delivery (USB Strategy)
1.  **Export (Internet PC)**:
    - 외부망 PC에서 필요한 이미지를 `docker save` 명령으로 파일화합니다.
    - 예: `docker save -o dcmtk_3.6.7.tar ai4infra-dcmtk:3.6.7`
    - **중요**: 모든 이미지는 `latest`가 아닌 **고정된 버전(Pinned Version)**을 사용해야 합니다. (예: `3.6.7`)

2.  **Import (Hospital Server)**:
    - USB를 서버에 마운트하고 이미지를 로드합니다.
    - 예: `docker load -i /path/to/usb/dcmtk_3.6.7.tar`

### B. Configuration Adjustment
- `docker-compose.yml`에서 `build:` 섹션을 주석 처리하고 `image:` 섹션만 활성화합니다.
- 로컬 빌드 대신 로드된 이미지를 사용하도록 `ai4infra-cli.py`나 `Makefile`을 조정합니다.

## 6.2 Auto-Start Strategy (OS별 자동 구동 전략)
> **목표**: 서버 부팅(또는 로그인) 시 Docker 컨테이너와 필수 서비스(Vault Unseal 등)를 사람의 개입 없이 자동으로 구동 완료 상태로 만듭니다.

### A. Linux & Windows 11 (WSL2 w/ Systemd)
**전제 조건**: `systemd`가 활성화되어 있어야 합니다. (`ps --no-headers -o comm 1` → `systemd`)

1.  **Docker Container**: `restart: unless-stopped` 정책에 의해 Docker 서비스 구동 시 자동 복구됨. (별도 설정 불필요)
2.  **Auto-Unseal Service**:
    - **Service File**: `/etc/systemd/system/ai4infra-unseal.service` 등록.
    - **Trigger**: `After=docker.service` (도커 구동 직후 실행).
    - **Action**: `ai4infra-cli.py unseal-vault` 명령 실행 (Mock USB 등 키 파일 감지).

### B. Windows 10 (Docker Desktop / Native)
1.  **Docker Desktop 사용자 (일반적)**:
    - **설정**: Settings > General > **Start Docker Desktop when you log in** 체크.
    - **WSL Integration**: Settings > Resources > WSL Integration > 사용 중인 배포판(Ubuntu 등) **ON**.
    - **결과**: 윈도우 로그인 시 컨테이너 자동 구동. (단, Unseal은 3번 스크립트로 처리)

2.  **Native Docker 사용자 (WSL2 Custom)**:
    - **sudoers**: `/etc/sudoers`에 `NOPASSWD: /usr/sbin/service docker start` 추가.
    - **Start Script**: 윈도우 `shell:startup` 폴더에 `start_docker.bat` 배치 파일 생성.
    - **내용**: `wsl -d Ubuntu -u root service docker start`

3.  **Auto-Unseal (Windows 공통)**:
    - `shell:startup` 폴더에 `auto_unseal.bat` 생성.
    - 내용: `wsl -d Ubuntu -u ben /path/to/venv/python /path/to/ai4infra-cli.py unseal-vault`
- **Restore Strategy**: `stop` -> `template check` -> `restore(overwrite)` -> `permission fix` -> `start`


## 6.2 Windows 10 Auto-Start Strategy (Native Docker without Desktop)
> **대상**: Windows 10 사용자 (표준 사용자 계정) / Docker Desktop 미사용(라이선스/성능 이슈).
> **목표**: 윈도우 부팅(로그인) 시 WSL2 내부의 Docker 데몬과 컨테이너들을 자동으로 깨웁니다.

1.  **WSL2 sudoers 설정** (비밀번호 없이 서비스 실행 허용):
    - `sudo visudo` 명령으로 `/etc/sudoers` 편집.
    - `%sudo ALL=(ALL) NOPASSWD: /usr/sbin/service docker start` 추가.

2.  **Windows Startup Script**:
    - `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup` 폴더에 `start_docker.bat` 생성.
    - 내용:
      ```batch
      @echo off
      wsl -d Ubuntu -u root service docker start
      timeout /t 5
      ```

### 6.2.1 Service Specific Strategy
- **Postgres (2-Step Initialization)**:
    - **Concept**: 초기 구동 시 `certificate` 유무에 따른 Crash를 방지하기 위해 2단계로 설치합니다.
    - **Step 1**: `docker-compose.override.yml`(TLS 설정)을 **제외**하고 기본 템플릿만 복사하여 구동 (DB 초기화 및 볼륨 생성).
    - **Step 2**: 인증서 발급 및 권한 설정 후, `override` 파일을 추가 복사하고 재기동하여 TLS 적용.

## 7. Security & Vault Strategy (보안 및 볼트 전략)

### 7.1 TLS Implementation Strategy (TLS 적용 기준)
모든 서비스는 mTLS(상호 인증) 또는 TLS 암호화를 지향하지만, **컨테이너의 구동 특성**에 따라 적용 시점을 달리합니다.

1.  **Native TLS Support (One-Shot)** (예: Vault)
    -   설정 파일(`config.hcl`)을 통해 인증서 경로를 지정하며, **최초 구동 시** 인증서가 존재하면 즉시 TLS 모드로 시작 가능합니다.
    -   **전략**: 템플릿 복사 후 `start` 전에 인증서를 생성/배치하여 **One-Shot 구동**.

2.  **Strict Permission Requirement (2-Step)** (예: Postgres)
    -   데이터 디렉터리(`/var/lib/postgresql/data`) 및 사용자(`postgres`)가 생성되기 전에는 인증서에 올바른 권한(`chown postgres:postgres`)을 부여할 수 없습니다.
    -   **전략**: **2-Step Initialization** (평문 구동 → 사용자/폴더 생성 → 인증서 권한 설정 → TLS 모드 재기동).

3.  **Reverse Proxy / Termination** (예: Web Apps)
    -   Nginx 등이 앞단에서 TLS를 처리하고 내부 통신은 평문을 사용하는 경우. (단, Vault/Bitwarden 등 보안이 중요한 서비스는 내부 통신도 TLS를 적용합니다.)
    -   **전략**: 컨테이너는 평문으로 유지하고 `docker-compose` 네트워크 내부 통신만 허용.
    -   **Nginx Gateway**: `vault.conf` 등의 설정에서 `proxy_pass https://...`를 사용하여 백엔드(Vault)와도 암호화 통신을 수행합니다. (Protocol Mismatch 방지)

본 프로젝트는 보안성과 개발 편의성(잦은 재부팅)의 균형을 위해 **"Smart Key (USB + Server File)"** 전략을 사용합니다.

### 7.1 Strategy Overview (Smart Key)
- **개념**: 물리적 USB(Key)가 서버에 꽂혀 있을 때만 서버 내부의 비밀번호로 Unseal을 수행합니다. (자동차 스마트키 원리)
- **보안 원리**: **지식의 분리 (Split Knowledge)**
    - **Physical Token**: 암호화된 Unseal Key 파일 (`vault_keys.enc`) -> **USB에 저장**.
    - **Knowledge Token**: 복호화 비밀번호 -> **서버 내부 안전 영역** (`root` only) 및 **외부 비트바르덴(Bitwarden)** 에 분산 저장.

### 7.2 Workflow (Auto-Unseal)
1.  **Boot**: 서버 부팅 시 `auto-unseal` 스크립트 실행.
2.  **Check**: USB 마운트 확인 및 `vault_keys.enc` 존재 여부 확인.
3.  **Decrypt**: 서버 내부의 복호화 비밀번호를 사용하여 Unseal Key를 메모리 상에서 복호화.
4.  **Unseal**: Vault API를 호출하여 Unseal 수행.
5.  **FailSafe**: USB가 없거나 복호화 실패 시 관리자 개입 요청 (수동 입력).

### 7.3 Disaster Recovery (재해 복구)
- **USB 분실**: 금고에 보관된 **예비 USB** 사용.
- **서버 디스크 파손**: 외부 **Bitwarden** (Secure Note)에 백업된 복호화 비밀번호를 참조하여 서버 파일 복구.
- **Whole System Down**: 어떠한 경우에도 외부(Bitwarden)에 비밀번호가 있고, 물리적(금고)으로 Unseal Key가 있으므로 복구 가능.

### 7.4 Vault Provisioning Strategy (볼트 프로비저닝 전략)
> **원칙**: `ai4infra`는 **범용적인 인프라 환경(Base)**만 구성하며, 특정 서비스(APP)에 종속된 정책(Policy)이나 역할(Role)은 정의하지 않습니다.

1.  **Common Infrastructure (ai4infra 담당)**:
    *   **KV Engine (v2) 활성화**: `secret/` 경로. (모든 앱의 공통 저장소)
    *   **AppRole Auth 활성화**: `auth/approle/` 경로. (서버 인증 표준)
    *   **Audit Log 활성화**: `file` 디바이스 (`/vault/logs/audit.log`). (보안 감사 필수)
    *   **Action**: `setup-vault-base` 명령어로 구현.

2.  **Service Specific (각 앱 프로젝트 담당)**:
    *   **Policy Definition**: 특정 경로(`secret/my-app/*`)에 대한 접근 제어.
    *   **Role Creation**: 앱별 인증 역할(`my-app-role`) 및 Secret ID 발급.
    *   **Secret Injection**: 실제 사용할 키/데이터 저장.

### 7.5 Recovery Policy (복구 정책)
- **General Recovery**: 일반적인 복구(장애 대응)는 `make restore-<service>` 명령을 사용하며, 자동으로 **가장 최신**의 백업 파일을 찾아 복원합니다.
- **Point-in-Time Recovery (PITR)**: 특정 시점으로의 복구는 데이터 정합성을 해칠 수 있는 민감한 작업이므로, 자동화 스크립트(Makefile) 대신 **CLI를 직접 사용**하여 복구할 시점의 파일 경로를 명시적으로 지정해야 합니다.
    - 권장 명령: `python scripts/ai4infra/ai4infra-cli.py restore <service> <backup_file_path>`

## 8. Testing & Certification Strategy (테스트 및 인증 전략)
> **목표**: "한국 우수 소프트웨어 인증(GS 인증 등)" 획득을 대비하여, 기능 구현과 테스트 작성을 분리된 프로세스로 관리합니다.

### 8.1 Workflow (Dual-Track Verification)
사용자의 요청에 따라 모든 보안 기능 검증은 **두 가지 트랙**으로 동시 진행합니다.

- **Track A: Automated Verification (에이전트 담당)**
    - **위치**: `{PROJECT_ROOT}/tests/security/`
    - **도구**: `pytest` 및 `requests` 라이브러리.
    - **내용**: 코드로 검증 가능한 모든 항목(상태 코드, 헤더, 리다이렉트 등)을 테스트 스크립트로 구현합니다.
    - **실행**: `make test-security` 명령으로 일괄 수행.

- **Track B: Manual Verification (사용자 담당)**
    - **위치**: `security_implementation_plan.md` 내 각 항목의 "Manual Guide" 섹션.
    - **내용**: 브라우저 UI 조작, USB 탈부착 등 **사람의 개입이 필수적인** 시나리오를 명시합니다.
    - **형식**: "어디를 클릭하고(Action) -> 무엇이 보여야 하는지(Expectation)" 명확히 기술.

### 8.2 Test Standards
- **Framework**: `pytest`
- **Criteria**:
    - **Unit Test**: 개별 모듈/함수의 정상 동작 및 예외 처리 검증.
    - **Integration Test**: 서비스(Container) 간 연동 및 시나리오 검증.
    - **Documentation**: 모든 테스트 함수에는 "평가 항목"과 "기대 결과"가 명시된 Docstring 포함.

### 8.3 Reporting & Archiving (리포팅 및 아카이빙)
- **Concept**: 단순 로그가 아닌, 비전문가도 이해할 수 있는 **문서(Document)** 형태의 리포트를 생성합니다. (GS인증 등 제출용)
- **Standard**:
    - **Header**: 시험 환경(OS, Docker ver), 시험 일시, 시험자(Agent/Human), 전체 성공/실패 요약.
    - **Body**: 시나리오별 "수행 절차" -> "기대 결과" -> "실제 결과" -> "판정(Pass/Fail)".
- **Versioning**:
    - 리포트는 `documentations/test-reports/{version}/` 경로에 보관합니다.
    - 예: `documentations/test-reports/v1.0.0/report_20260111.md`
- **Goal**: 언제든 특정 버전의 소프트웨어가 "언제, 어떻게 검증되었는지" 증명할 수 있어야 합니다.

## 9. Application Delivery Strategy (앱 배포 및 환경 전략)
> **핵심 원칙**: "사용자는 **컨테이너**로 실행하고, 개발자는 **로컬 가상환경**에서 개발한다."

### 9.1 Environment isolation (환경 격리)
1.  **Runtime (User)**:
    *   **Docker Only**: 모든 응용 서비스(`apps/`)는 반드시 **Docker Container** 내에서 실행되어야 합니다.
    *   **No Host Venv**: 사용자 서버(Host OS)에 파이썬 라이브러리를 직접 설치하거나 venv를 생성하지 않습니다. (의존성 지옥 방지)
    *   **Web Access**: 사용자는 로컬 브라우저(`http://service.ai4infra.internal`)를 통해 서비스에 접근합니다.

2.  **Development (Developer)**:
    *   **Local Venv**: 각 앱 리포지토리(`apps/my-app/`)마다 개별 `.venv`를 생성하여 개발 도구(Linter, Autocomplete)를 지원합니다.
    *   **Independence**: `apps/` 하위의 각 프로젝트는 서로 완전히 독립된 개발 환경을 가집니다.

### 9.2 Delivery Mechanism (배포 방식)
*   **Artifact**: Docker Image (Registry Push 또는 `.tar` 파일).
*   **Configuration**: `config/*.yml` 및 `templates/` (Git Repository).
*   **Workflow**:
    1.  **Build**: 개발자가 이미지를 빌드하고 태깅합니다. (예: `ai4infra/nmdose:1.0`)
    2.  **Pull**: 사용자가 `git pull`로 최신 설정(`apps/`)을 가져옵니다.
    3.  **Deploy**: `make install-nmdose` 실행 시, 시스템이 이미지를 가져와 컨테이너를 구동합니다.


## 10. Zero Trust Gateway Strategy (Web Access & Security)
> **원칙**: "모든 웹 서비스는 **단일 게이트웨이(Single Entry Point)** 를 통해서만 접근하며, **중앙 집중식 인증(OIDC)** 을 강제한다."

### 10.1 OpenResty Gateway Architecture
- **Technology**: OpenResty (Nginx + LuaJIT) + `lua-resty-openidc`.
- **Role**:
    - **Termination**: TLS 암호화 해제.
    - **Authentication**: Keycloak과 연동하여 OIDC 인증 수행. 세션이 없는 요청은 즉시 로그인 페이지로 리다이렉트.
    - **Offloading**: 백엔드 서비스(Orthanc 등)는 복잡한 인증 로직을 제거하고, 순수 비즈니스 로직에 집중.

### 10.2 Implementation Rules
1.  **Lua Enforcement**: 모든 Nginx Server Block은 `oidc_auth.lua`를 로드하여 인증을 검사해야 합니다.
    ```nginx
    access_by_lua_block { require("oidc_auth").validate() }
    ```
2.  **Asset Bypass**: CSS, JS, 이미지는 성능 및 세션 락킹 방지를 위해 인증 예외 처리(`location ~* \.(css|js)...`)를 권장합니다.
3.  **Config Centralization**: 주요 OIDC 설정(Client ID, Secret 등)은 `nginx.conf` 또는 `lua` 스크립트 한곳에서 관리하며, 개별 서비스 설정 파일에 하드코딩하지 않습니다.

### 10.3 Benefit
- 개별 서비스(Orthanc, OpenREM 등)가 OIDC를 지원하지 않아도, 게이트웨이 레벨에서 강력한 보안(MFA, SSO)을 적용할 수 있습니다.
