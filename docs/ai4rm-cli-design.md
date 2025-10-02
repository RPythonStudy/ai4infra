# AI4RM Docker Container Management CLI 설계안

## 목표
- `/opt/ai4rm/{service}/` 구조로 각종 Docker 컨테이너 관리
- 현재 security-infra-cli.py의 장점을 유지하면서 확장성 제공
- 보안, 감사 로깅, 권한 관리를 포함한 통합 관리 도구

## 권장 접근법: Python CLI + Docker Compose 조합

### 1. 아키텍처 구조

```
ai4rm-cli.py (메인 CLI)
├── src/ai4rm/
│   ├── __init__.py
│   ├── core/
│   │   ├── config_manager.py    # 통합 설정 관리
│   │   ├── logger.py           # 감사 로깅
│   │   ├── security.py         # 보안 정책
│   │   └── validation.py       # 설정 검증
│   ├── services/
│   │   ├── base_service.py     # 서비스 베이스 클래스
│   │   ├── postgres.py         # PostgreSQL 관리
│   │   ├── vault.py           # HashiCorp Vault 관리
│   │   ├── elk.py             # ELK Stack 관리
│   │   ├── bitwarden.py       # Bitwarden 관리
│   │   └── ldap.py            # OpenLDAP 관리
│   ├── managers/
│   │   ├── directory_manager.py # 디렉터리 생성/관리
│   │   ├── cert_manager.py     # 인증서 관리
│   │   ├── network_manager.py  # 네트워크 설정
│   │   ├── backup_manager.py   # 백업/복원
│   │   └── compose_manager.py  # Docker Compose 통합 관리
│   └── utils/
│       ├── file_utils.py       # 파일 조작
│       ├── docker_utils.py     # Docker 헬퍼
│       └── system_utils.py     # 시스템 관련
├── config/
│   ├── ai4rm.yml              # 메인 설정
│   ├── services/
│   │   ├── postgres.yml
│   │   ├── vault.yml
│   │   ├── elk.yml
│   │   ├── bitwarden.yml
│   │   └── ldap.yml
│   └── templates/             # Docker Compose 템플릿
└── /opt/ai4rm/               # 실제 서비스 배포 경로
    ├── postgres/
    ├── vault/
    ├── elk/
    ├── bitwarden/
    └── ldap/
```

### 2. 핵심 기능 설계

#### 2.1 서비스 관리 명령어
```bash
# 서비스 설치
ai4rm-cli install postgres --config=/opt/ai4rm/postgres/
ai4rm-cli install vault --with-certs --backup-existing

# 서비스 관리
ai4rm-cli start postgres
ai4rm-cli stop all
ai4rm-cli restart elk
ai4rm-cli status

# 설정 관리
ai4rm-cli config sync postgres  # 템플릿을 실제 경로로 동기화
ai4rm-cli config validate      # 모든 설정 검증
ai4rm-cli config backup        # 설정 백업

# 보안 관리
ai4rm-cli security setup-certs vault elk
ai4rm-cli security fix-permissions postgres
ai4rm-cli security audit-check all
```

#### 2.2 백업/복원 시스템
```bash
# 전체 또는 개별 서비스 백업
ai4rm-cli backup all --output=/backup/ai4rm-$(date +%Y%m%d)
ai4rm-cli backup postgres --compress

# 복원
ai4rm-cli restore postgres --from=/backup/postgres-20241002
ai4rm-cli restore all --from=/backup/ai4rm-20241002
```

### 3. 설정 파일 구조

#### 3.1 메인 설정 (config/ai4rm.yml)
```yaml
ai4rm:
  base_path: "/opt/ai4rm"
  log_level: "INFO"
  audit_log: true
  
  global:
    timezone: "Asia/Seoul"
    backup_retention_days: 30
    security_scan_enabled: true
    
  network:
    internal_network: "ai4rm_network"
    subnet: "172.20.0.0/16"
    
  security:
    certificate_days: 730
    enforce_permissions: true
    audit_compliance: "개인정보보호법 제28조"
```

#### 3.2 서비스별 설정 예시 (config/services/postgres.yml)
```yaml
postgres:
  service_name: "ai4rm_postgres"
  install_dir: "/opt/ai4rm/postgres"
  data_dir: "/opt/ai4rm/postgres/data"
  backup_dir: "/opt/ai4rm/postgres/backup"
  port: 5432
  
  docker:
    image: "postgres:15"
    container_name: "ai4rm_postgres"
    restart_policy: "unless-stopped"
    
  environment:
    POSTGRES_DB: "ai4rm"
    POSTGRES_USER: "ai4rm_user"
    # POSTGRES_PASSWORD는 .env에서 로드
    
  volumes:
    - "${PG_DATA_DIR}:/var/lib/postgresql/data"
    - "${PG_BACKUP_DIR}:/backup"
    
  networks:
    - "ai4rm_network"
    
  dependencies: []  # 다른 서비스 의존성
  
  security:
    owner: "999:999"  # postgres 사용자
    permissions:
      data_dir: "700"
      config_dir: "755"
      backup_dir: "700"
```

### 4. 구현 우선순위

1. **Phase 1**: 기본 구조 및 PostgreSQL 관리
   - 디렉터리 생성 및 권한 설정
   - Docker Compose 템플릿 관리
   - 기본적인 start/stop/status 기능

2. **Phase 2**: 보안 및 인증서 관리
   - 자체 서명 인증서 생성
   - 권한 검증 및 자동 수정
   - 감사 로깅 통합

3. **Phase 3**: 백업/복원 시스템
   - 자동화된 백업 스케줄링
   - 포인트-인-타임 복원
   - 설정 버전 관리

4. **Phase 4**: 모니터링 및 헬스체크
   - 서비스 상태 모니터링
   - 자동 복구 메커니즘
   - 알림 시스템

### 5. 현재 프로젝트와의 통합 방안

현재의 `security-infra-cli.py`를 기반으로 하되, 다음과 같이 진화:

1. **기존 코드 재사용**:
   - `compose_manager.py` → `managers/compose_manager.py`로 이동
   - `generate_certificates.py` → `managers/cert_manager.py`로 통합
   - 기존 로깅 시스템 활용

2. **설정 시스템 통합**:
   - 현재 `config/postgres.yml` 등을 새로운 구조로 마이그레이션
   - `.env` 파일 관리 방식 유지

3. **점진적 마이그레이션**:
   - 기존 PostgreSQL 관리 스크립트를 새로운 구조로 이전
   - 다른 서비스들을 순차적으로 추가

## 결론

**Python CLI + Docker Compose 조합이 가장 적합한 이유:**

1. **현재 프로젝트와의 연속성**: 기존 코드 자산 재활용 가능
2. **복잡성 관리**: 복잡한 설정, 권한, 보안 정책을 체계적으로 관리
3. **확장성**: 새로운 서비스 추가가 용이한 모듈화 구조
4. **보안성**: 감사 로깅, 권한 관리, 규정 준수 기능 내장
5. **유지보수성**: 타입 힌트, 구조화된 로깅, 테스트 가능한 설계

이 접근법으로 `/opt/ai4rm/` 구조에서 각종 Docker 컨테이너를 효율적이고 안전하게 관리할 수 있습니다.
