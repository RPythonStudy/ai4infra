# 보안 기술 구현 계획 및 검증 전략
# (Security Implementation Plan & Verification Strategy)

본 문서는 **세계 최고 수준의 12가지 보안 요소 (12 Pillars of World Class Security)**의 구현 전략을 공식화합니다.

구현 오류와 맥락 손실을 방지하기 위해, 각 기술은 더 이상 나눌 수 없는 **구현 단위 (Atomistic Unit)**로 세분화하고
**검증 (Verification)** 절차를 의무화합니다.

---

## 0. 전제 조건 및 핵심 철학 (Prerequisite & Core Philosophy)

*   **원칙 (Principle)**:
    "아무도 신뢰하지 말고, 모든 것을 검증하라." (Zero Trust)

*   **방법론 (Methodology)**:
    단계별 구현 후 검증을 의무적으로 수행한 뒤 다음 단계로 진행.

*   **상태 (Status)**:
    진행 상황에 따라 지속적으로 업데이트되는 살아있는 문서 (Living Document).

### 0.1 타겟 운영 환경 (Target Environment)

*   **OS**:
    Windows (병원 표준) 우선, WSL2(Docker 호환성) 및 Windows Native 병행 지원.

*   **Network**:
    폐쇄망(Air-gapped) 환경을 가정하여 **오프라인 설치** 및 **물리 키(USB) 관리** 필수.

### 0.2 데이터 보호 및 백업 (Data Protection)

*   **의료 정보 보호**:
    가명화 프로젝트 수행을 위한 엄격한 보안 기준 적용.

*   **백업 전략**:
    *   **Cold Backup**: 시스템 변경 전 서비스 완전 중단 후 전체 볼륨 복사.
    *   **Hot Backup**: Vault, Postgres 등은 자체 스냅샷 기능 병행 사용.

---

## 1단계: 계정 및 접근 제어 (Phase 1: Identity & Access)
*목표: 엄격하게 통제된 신원 확인을 통해 진입점을 보호합니다. (Secure the Front Door)*

### [SEC-01] 중앙 집중식 계정 관리 (Centralized Identity) - Keycloak **[완료]**

*   **정의 (Definition)**:
    사용자 로그인, 회원가입, 토큰 발급을 처리하는 신원의 유일한 원천(Source of Truth)입니다.

*   **구현 단위 (Units)**:
    1.  Keycloak 컨테이너 설치.
    2.  전용 데이터베이스(Postgres) 연결 및 설정.
    3.  게이트웨이를 통한 서비스 노출 (`/auth` 또는 `auth.domain`).

*   **검증 (Verification)**:
    *   **Track A: Automated Test** (`tests/security/test_sec01_keycloak.py`)
        - `/realms/ai4infra/.well-known/openid-configuration` 엔드포인트 호출 -> 200 OK.
    *   **Track B: Manual Guide** (사용자 직접 수행)
        - [x] `http://localhost:8484` 관리자 콘솔 접속 확인.
        - [x] Realm 생성 및 Client 설정 확인.


### [SEC-02] 제로 트러스트 게이트웨이 (Zero Trust Gateway) - Nginx OIDC **[완료]**

*   **정의 (Definition)**:
    모든 요청이 서비스에 도달하기 전에 인증을 강제하는 단일 진입점입니다.

*   **구현 단위 (Units)**:
    1.  Lua 모듈이 포함된 Nginx 설치.
    2.  OIDC 인증 로직 구현 (`oidc_auth.lua`).
    3.  전역 인증 정책 강제 적용.

*   **검증 (Verification)**:
    *   **Track A: Automated Test** (`tests/security/test_sec02_gateway.py`)
        - `requests.get('https://ai4infra.internal')` -> 302/401 응답 확인.
        - `requests.get('.../oidc/redirect')` -> 토큰 검증 로직 확인.
    *   **Track B: Manual Guide**
        - [x] 브라우저에서 `https://ai4infra.internal` 접속 시 Keycloak 로그인 화면이 뜨는지 눈으로 확인.
        - [x] 로그인 후 원래 페이지로 돌아오는지 확인.

### [SEC-03] 다중 인증 (Multi-Factor Authentication, MFA) **[완료]**

*   **정의 (Definition)**:
    비밀번호 외에 2차 인증 수단(TOTP/OTP)을 강제하여 계정 보안을 강화합니다.

*   **구현 단위 (Units)**:
    1.  **[SEC-03-A]** Keycloak 인증 흐름(Flow) 설정 (MFA 강제).
    2.  **[SEC-03-B]** 테스트 계정에 대한 TOTP 설정 및 검증.

*   **검증 (Verification)**:
    *   **Track A: Automated Test**
        - 셀레니움(Selenium) 또는 API를 통해 로그인 시도 시 MFA 요구 응답 확인.
    *   **Track B: Manual Guide**
        - [x] 로그인 시도 시 "Google Authenticator 설정" 화면이 뜨는지 확인.
        - [x] 모바일 앱으로 QR 스캔 후 코드 입력하여 로그인 성공 확인.

### [SEC-04] 역할 기반 접근 제어 (Role-Based Access Control, RBAC) **[완료]**

*   **정의 (Definition)**:
    단순 로그인이 아닌, 사용자 역할(예: `doctor`, `admin`)에 따라 접근 권한을 차등 부여합니다.

*   **구현 단위 (Units)**:
    1.  **[SEC-04-A]** Keycloak 내 역할 정의 (`admin`, `user`).
    2.  **[SEC-04-B]** ID 토큰(ID Token)에 역할(Role) 정보 포함 설정 (Audience/Role Mapper).
    3.  **[SEC-04-C]** Nginx 게이트웨이(Lua Script)에서 역할 확인 로직 적용 (Pre-Validation Strategy).

*   **검증 (Verification)**:
    *   **Track A: Automated Test**
        - `admin` 토큰으로 `/admin` 접근 -> 200 OK (Pass).
        - `user` 토큰으로 `/admin` 접근 -> 403 Forbidden (Pass).
    *   **Track B: Manual Guide**
        - [x] `user1`(일반)으로 로그인 후 관리자 메뉴 클릭 시 차단 메시지 확인.

---

## 2단계: 비밀 및 데이터 보호 (Phase 2: Secret & Data Protection)
*목표: 하드코딩된 비밀번호를 제거하고, 저장 및 전송 구간의 데이터를 암호화합니다.*

### [SEC-05] 비밀 관리 (Secret Management) - HashiCorp Vault **[완료]**

*   **정의 (Definition)**:
    API 키, 비밀번호, 인증서 등을 중앙에서 관리하여 코드 내 하드코딩을 제거합니다.

*   **구현 단위 (Units)**:
    1.  **[SEC-05-A]** Vault 컨테이너 설치 (`IPC_LOCK` 권한).
    2.  **[SEC-05-B]** Vault 초기화 및 Unseal Key 안전 저장.
    3.  **[SEC-05-C]** 서비스별 "AppRole" 설정 (기계 인증, Machine Identity).

*   **검증 (Verification)**:
    *   **Track A: Automated Test**
        - Vault API 상태 체크 (`/sys/health`) -> 200/4xx (Active/Sealed).
    *   **Track B: Manual Guide**
        - [x] 재부팅 후 Vault UI (`http://localhost:8200`) 접속 시 'Sealed' 상태 확인.

### [SEC-06] 지식의 분리 (Split Knowledge) - 자동 Unseal 전략 **[완료]**

*   **정의 (Definition)**:
    Vault 봉인 해제(Unseal)를 위해 물리적 토큰(USB)과 논리적 토큰(서버) 두 가지를 모두 요구합니다.

*   **구현 단위 (Units)**:
    1.  **[SEC-06-A]** Unseal 스크립트 개발 (Python, `auto_unseal.py`).
    2.  **[SEC-06-B]** USB 마운트 감지 로직 구현 (Volume Mount `/mnt/usb`).
    3.  **[SEC-06-C]** 부팅 시 자동 실행 설정 (Systemd/Startup Script).

*   **검증 (Verification)**:
    *   **Track A: Automated Test**
        - Mock USB 환경 구성 후 스크립트 실행 -> Unseal 성공 여부 리턴값 확인 (Pass).
    *   **Track B: Manual Guide**
        - [ ] 실제 USB 제거 후 재부팅 -> 서비스 접속 불가 확인.
        - [x] USB 연결(모사) 후 스크립트 실행 -> `Unseal Key Accepted`, `Vault Unsealed Successfully` 로그 확인.

### [SEC-07] 종단간 암호화 (End-to-End Encryption, E2E/mTLS)

*   **정의 (Definition)**:
    내부 네트워크(게이트웨이 <-> 서비스) 구간의 통신까지 모두 암호화합니다.

*   **구현 단위 (Units)**:
    1.  **[SEC-07-A]** 내부 인증기관(Private CA) 구축.
    2.  **[SEC-07-B]** 서비스별 인증서 발급 표준화.
    3.  **[SEC-07-C]** 각 서비스(Postgres, Keycloak 등)의 TLS 수신 설정.

*   **검증 (Verification)**:
    *   **Track A: Automated Test**
        - `requests.get(..., verify=ca_cert)` 로 내부 서비스 직접 호출 성공 확인.
    *   **Track B: Manual Guide**
        - [ ] 브라우저에서 '자물쇠' 아이콘 클릭 -> 'Verified by AI4Infra CA' 확인.

---

## 3단계: 인프라 강화 (Phase 3: Infrastructure Hardening)
*목표: 공격 표면(Attack Surface)을 최소화하고 피해 반경을 제한합니다.*

### [SEC-08] 네트워크 분리 (Network Segmentation)

*   **정의 (Definition)**:
    서비스 간 망을 분리하여 하나가 뚫려도 전체가 위험해지지 않도록 격리합니다.

*   **구현 단위 (Units)**:
    1.  **[SEC-08-A]** Docker 네트워크 정의 (`frontend`, `backend`, `db_net`).
    2.  **[SEC-08-B]** 컨테이너별 최소 필요 네트워크 할당.
    3.  **[SEC-08-C]** 컨테이너 간 직접 통신 차단 (ICC=false).

*   **검증 (Verification)**:
    *   **Track A: Automated Test**
        - `docker run --network frontend ... ping backend` -> 실패 확인.
    *   **Track B: Manual Guide**
        - [ ] (보이지 않으므로 생략 가능, 또는 로그 확인)

### [SEC-09] 불변 인프라 (Immutable Infrastructure)

*   **정의 (Definition)**:
    컨테이너를 읽기 전용(Read-Only)으로 구동하여 악성코드의 침투 및 지속을 방지합니다.

*   **구현 단위 (Units)**:
    1.  **[SEC-09-A]** 볼륨 마운트 재설계 (쓰기 가능 영역 분리).
    2.  **[SEC-09-B]** Docker Compose에 `read_only: true` 적용.

*   **검증 (Verification)**:
    *   **Track A: Automated Test**
        - `docker exec ... touch /tmp/test` -> Error 확인.
    *   **Track B: Manual Guide**
        - [ ] (자동화 테스트로 충분)

### [SEC-10] 웹 방화벽 (Web Application Firewall, WAF)

*   **정의 (Definition)**:
    SQL 인젝션(SQLi), 사이트 간 스크립팅(XSS) 등의 웹 공격 패턴을 차단합니다.

*   **구현 단위 (Units)**:
    1.  **[SEC-10-A]** Nginx ModSecurity 모듈 활성화.
    2.  **[SEC-10-B]** OWASP Core Rule Set (CRS) 적용.
    3.  **[SEC-10-C]** 오탐(False Positive) 튜닝.

*   **검증 (Verification)**:
    *   **Track A: Automated Test**
        - `requests.get('/?q=<script>alert(1)</script>')` -> 403 확인.
    *   **Track B: Manual Guide**
        - [ ] URL 뒤에 `?id=' OR 1=1` 입력 후 403 Forbidden 화면 확인.

### [SEC-11] 분산 서비스 거부 방어 (DDoS Protection / Rate Limiting)

*   **정의 (Definition)**:
    특정 IP나 사용자의 과도한 요청을 제한하여 시스템을 보호합니다.

*   **구현 단위 (Units)**:
    1.  **[SEC-11-A]** Nginx `limit_req_zone` 설정.
    2.  **[SEC-11-B]** 민감한 경로(로그인, API)에 엄격한 제한 적용.

*   **검증 (Verification)**:
    *   **Track A: Automated Test**
        - 루프 돌며 100회 요청 -> 429 Too Many Requests 응답 확인.
    *   **Track B: Manual Guide**
        - [ ] F5 키를 연타했을 때 "잠시 후 다시 시도해주세요" 에러 확인.

### [SEC-12] 보안 감사 로그 (Audit Logging)

*   **정의 (Definition)**:
    "누가, 언제, 무엇을 했는지"에 대한 위변조 불가능한 기록을 남깁니다.

*   **구현 단위 (Units)**:
    1.  **[SEC-12-A]** 로그 포맷 표준화 (JSON).
    2.  **[SEC-12-B]** 로그 중앙 수집 (ELK Stack).

*   **검증 (Verification)**:
    *   **Track A: Automated Test**
        - 로그 파일 파싱하여 특정 이벤트(Login) 존재 확인.
    *   **Track B: Manual Guide**
        - [ ] Kibana 대시보드에서 방금 로그인한 내역 검색.

