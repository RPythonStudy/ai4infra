# Vault 프로덕션 설정 파일
# 파일명: templates/vault/config/vault.hcl

# 스토리지 백엔드 - 파일 기반
storage "file" {
  path = "/vault/file"
}

# 리스너 설정 - HTTPS 필수 + mTLS (상호 인증)
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_cert_file = "/vault/certs/certificate.crt"
  tls_key_file  = "/vault/certs/private.key"
  
  # [SEC-07] mTLS Enforcement
  tls_client_ca_file = "/vault/certs/rootCA.crt"
  tls_require_and_verify_client_cert = "true"
}

# API 주소 (환경변수 VAULT_API_ADDR, VAULT_CLUSTER_ADDR 사용을 위해 주석 처리)
# api_addr = "https://vault:8200"
# cluster_addr = "https://vault:8201"

# UI 활성화
ui = true

# 로그 레벨 (선택: "TRACE", "DEBUG", "INFO", "WARN", "ERROR")
log_level = "INFO"

# mlock 활성화 (Docker cap_add: IPC_LOCK 필요)
disable_mlock = false
