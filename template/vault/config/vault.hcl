# Vault 프로덕션 설정 파일
# 파일명: template/vault/config/vault.hcl

# 스토리지 백엔드 - 파일 기반
storage "file" {
  path = "/vault/file"
}

# 리스너 설정 - HTTPS 필수
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_cert_file = "/vault/certs/certificate.crt"
  tls_key_file  = "/vault/certs/private.key"
}

# API 주소
api_addr = "https://vault:8200"
cluster_addr = "https://vault:8201"

# UI 활성화
ui = true

# 로그 레벨
log_level = "INFO"

# mlock 비활성화 (Docker 환경용)
disable_mlock = true
