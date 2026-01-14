# Vault Service Definition & Development Guide

> **목적**:
> 이 프로젝트는 직접 가명화 키를 관리하는 것이 아니라, 추후 **의료정보 가명화 프로젝트** 등에서
> **가명화 키(Pseudonymization Keys)** 를 안전하게 관리할 수 있도록
> **Vault 인프라를 구축하고 지원하는 것**을 목적으로 합니다.
>
> 즉, 데이터 분석가가 사용할 "키 관리소"를 지어주는 역할입니다.

## 1. 서비스 역할 및 목표

- **Infrastructure Provider**:
    가명화 프로젝트 수행 시 즉시 활용 가능한, 보안성이 검증된 Vault 서버 환경 제공.

- **Key Management Support**:
    사용자가 가명화 키(FF3 등)를 직접 생성하고 안전하게 보관/불러오기 할 수 있는 기능 및 인터페이스(CLI/API) 지원.

- **Security Standard**:
    의료 데이터 등 민감 정보 취급 기준에 부합하는 접근 제어(AppRole, ACL) 환경 구성.

## 2. 개발 및 배포 전략

- **Docker 기반**:
    `hashicorp/vault` 공식 이미지를 사용하여 컨테이너로 배포.

- **설정 자동화**:
    - `docker-compose.yml`은 `template/vault/`에 위치하며, 서비스 생성 시 복사하여 사용.
    - 주요 설정(포트 등)은 `config/vault.yml` 및 `.env` 파일에서 관리하여 하드코딩 방지.

- **계정 분리 (Future Plan)**:
    운영(`vaultop`)과 관리(`vaultadmin`) 계정을 분리하는 2-tier 체계는 현재 기술적 검토 중이며,
    추후 안정화 단계에서 도입 예정입니다.

- **Auto Unseal 전략 (USB 기반)**:
    - **제약 사항**:
        - Vault 무료 버전(OSS)의 기능적 한계(HSM 미지원 등).
        - **폐쇄망(Closed Network)**: 병원 등 의료망은 인터넷 연결이 차단된 경우가 많아
          AWS/GCP KMS와 같은 클라우드 기반 자동화 사용 불가.
    - **구현 방식**:
        Shamir's Secret Sharing으로 분할된 5개의 Key 중 3개를 USB 등 물리 매체에 저장.
    - **운영 프로세스**:
        서버 재기동 시 USB를 마운트하면 스크립트가 이를 읽어 자동으로 Unseal 수행.
        (USB 미연결 시 수동 입력 모드로 fallback 지원)
    - **Development Simulation**:
        개발 단계에서는 실제 USB 대신 `/mnt/usb` 폴더를 생성하여 가상의 키 파일(예: `[계정].enc`)을 배치하고
        테스트를 수행합니다.

---

## 3. 구축 가이드 (Reference)
*아래 내용은 기존 Wiki에서 이관된 기술 상세 노트입니다.*

### 도커 이미지 및 변수
- **Official Image**: `hashicorp/vault`
- **Address**: `https://0.0.0.0:8200`
- **Docker-compose Port**: `8200` (Default)

# docker-compose.yml 대체변수
- PORT: 8200

# health check
- vault container는 별도의 health check endpoint를 제공하지 않음
- vault cli를 통해 상태 확인 가능
```bash
vault status
```

# 진행상황
- 다른 서비스들처럼 template/<service명>/에 docker-compose.yml 방식으로 설정
- {PROJECT_ROOT}/config/service명.yml에 필요한 컨테이너용 환경변수 설정
- {PROJECT_ROOT}/scripts/ai4infra/ai4infra-cli.py에 서비스별로 인자를 전달하거나 all을 전달하도록 구현
- --reset 옵션으로 기존 데이터 삭제 후 설치 가능하도록 구현

# 시행착오
- docker 컨테이너의 vault uid/gid 100:100 변경이 되지 않고, host의ㅣuid 100은 시스템에서 사용하고 있어
  Bitwarden 처럼 별도 계정을 만들지 않고 소유를 100:100으로 부여하여 진행
- `VAULT_LOCAL_CONFIG`와 다른 설정에서 listener를 중복으로 설정하면 8200이 점유되어 오류발생


# CLI
> auto unseal 기능 구현에 필요
> sudo 권한으로 설치하고 wsl2에는 vaultadmin/vaultop 2단계 계정체계를 구현

## 설치여부 확인
```bash
vault --version
```

## 설치 스크립트
https://developer.hashicorp.com/vault/install?product=vault
- 패키지 서명키(GPG key)를 다운로드
```bash
wget -O - https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
```
- 위 명령뒤에 ben 권한 요청이 뜨면 비밀번호 입력
```bash
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(grep -oP '(?<=UBUNTU_CODENAME=).*' /etc/os-release || lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
```
```bash
sudo apt update && sudo apt install vault
```
- 진행될 때, Vault TLS key and self-signed certificate...
- 검증
```bash
vault --version
```

# 2단계 계정 체계

## vaultadmin
```bash
sudo adduser --disabled-password --gecos "" vaultadmin
```
uid:gid 1002:1002
```bash
sudo adduser --disabled-password --gecos "" vaultop
```
uid:gid 1003:1003


## auto-unseal
> - bitwarden/vault server들이 도커로 구동된 상태에서
> - init -> unseal 키를 bitwarden에 입력하는 것은 수동
> - usb 마운트과정은 테스트가 되었으니 개발 단계에서는 /mnt/usb/암호화키를 저장하여 모사
> - 만약 vault가 unseal 상태라면 auto-unseal.py로 unseal 가능

## 가명화키 저장
> vault가 unseal 상태일 때

### 로그인
```bash
sudo docker exec -it vault vault login
```
### 저장경로설정
```bash
sudo docker exec -it vault vault secrets enable -path=pseudonymize kv-v2
```
### 가명화키 저장
```bash
sudo docker exec -it vault vault kv put pseudonymize/ff3 KEY="0123456789abcdef0123456789abcdef" TWEAK="abcdef12345678"
```
### 조회
```bash
sudo docker exec -it vault vault kv get pseudonymize/ff3
```

## AppRole 정책 생성
```bash
# pseudonymize 키/값(Read Only)만 접근 가능
path "pseudonymize/data/ff3" {
  capabilities = ["read"]
}

# KV v2 metadata도 조회 가능 (선택)
path "pseudonymize/metadata/ff3" {
  capabilities = ["read"]
}
```
### 정책등록
```bash
VAULT_SKIP_VERIFY=true vault policy write pseudonymize-approle policies/pseudonymize-approle-policy.hcl
```
### 인증키복사
```bash
sudo cp ./docker/vault/certs/vault.crt /etc/ssl/certs/
```
### 활성화
```bash
vault auth enable approle
```
### 연결
```bash
vault write auth/approle/role/pseudonymize-role \
    token_policies="pseudonymize-approle" \
    token_ttl=10m \
    token_max_ttl=1h
```
### id 발급
```bash
vault write auth/approle/role/pseudonymize-role \
    token_policies="pseudonymize-approle" \
    token_ttl=10m \
    token_max_ttl=1h
```

### role_id 발급
```bash
sudo mkdir -p /etc/vault-agent
vault read -field=role_id auth/approle/role/pseudonymize-role/role-id | sudo tee /etc/vault-agent/role_id > /dev/null
```
### secret_id 발급 (각 앱/에이전트별 1회용)
```bash
vault write -field=secret_id -f auth/approle/role/pseudonymize-role/secret-id | sudo tee /etc/vault-agent/secret_id > /dev/null
```
### 권한설정
```bash
sudo chmod 600 /etc/vault-agent/role_id /etc/vault-agent/secret_id
sudo chown $(whoami):$(whoami) /etc/vault-agent/role_id /etc/vault-agent/secret_id
```

### 설정파일
```bash
pid_file = "/var/run/vault-agent.pid"

auto_auth {
  method "approle" {
    mount_path = "auth/approle"
    config = {
      role_id_file_path = "/etc/vault-agent/role_id"
      secret_id_file_path = "/etc/vault-agent/secret_id"
    }
  }

  sink "file" {
    config = {
      path = "/etc/vault-agent/vault-token"
      mode = 0600
    }
  }
}

vault {
  address = "https://127.0.0.1:8200"
  ca_cert = "/etc/ssl/certs/vault.crt"
  # tls_skip_verify = false   # 신뢰할 수 없는 인증서라면 true, 아니면 false
}
```


### vault-agent 실행
```bash
sudo vault agent -config=/etc/vault-agent/vault-agent.hcl
```


