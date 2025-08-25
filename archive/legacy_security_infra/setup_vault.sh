#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# File: setup_vault.sh
# Description: Vault 초기화 이후 PKI(자가서명 인증서) 발급 및 상태 검증까지 올인원 반자동 스크립트
# Usage: bash scripts/setup_vault.sh
# Author: BenKorea <benkorea.ai@gmail.com>
# Created: 2025-07-03
# ------------------------------------------------------------------------------

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color
info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()    { echo -e "${RED}[WARN]${NC} $1"; }
fail()    { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

info "===[1/6] Vault 컨테이너가 기동 중인지 확인"
sudo docker compose up -d vault
sudo docker ps | grep -q 'vault' && info "Vault 컨테이너 기동 상태 OK" || fail "Vault 컨테이너 기동 실패"

info "===[2/6] 반드시 아래 단계는 수동으로 진행하세요!"
echo "------------------------------------------------------"
echo "[수동 1] Vault 초기화:"
echo "  sudo docker exec -it vault vault operator init"
echo "[수동 2] Vault 언실:"
echo "  sudo docker exec -it vault vault operator unseal"
echo "[수동 3] Vault 로그인:"
echo "  sudo docker exec -it vault vault login"
echo "※ 반드시 Root Token, Unseal Key를 별도 안전한 경로에 보관하세요!"
echo "------------------------------------------------------"
read -p "위 수동 단계를 모두 마치셨으면 Enter 키를 눌러주세요..."

info "===[3/6] Vault PKI/인증서(자가서명) 자동화 진행"

VAULT_CONTAINER="vault"
CERT_DIR="./docker/vault/certs"


# 1. pki 엔진 mount 및 튠
sudo docker exec $VAULT_CONTAINER vault secrets enable pki || true
sudo docker exec $VAULT_CONTAINER vault secrets tune -max-lease-ttl=8760h pki

# 2. Root CA 발급
sudo docker exec $VAULT_CONTAINER vault write pki/root/generate/internal \
    common_name="KIRAMS RPythonStudy PseudoStruct CA" \
    ttl=8760h

# 3. CRL, issuing cert URL 설정
sudo docker exec $VAULT_CONTAINER vault write pki/config/urls \
    issuing_certificates="http://127.0.0.1:8200/v1/pki/ca" \
    crl_distribution_points="http://127.0.0.1:8200/v1/pki/crl"

# 4. Role 생성
sudo docker exec $VAULT_CONTAINER vault write pki/roles/example-dot-com \
    allowed_domains="localhost,elasticsearch,kibana,logstash,keycloak,vault,openldap" \
    allow_subdomains=true \
    allow_bare_domains=true \
    allow_ip_sans=true \
    allow_localhost=true \
    max_ttl="168h"

# 5. 인증서 발급
sudo docker exec $VAULT_CONTAINER vault write -format=json pki/issue/example-dot-com \
    common_name=localhost \
    alt_names="localhost,elasticsearch,kibana,logstash,keycloak,vault,openldap" \
    ip_sans=127.0.0.1 \
    ttl=168h \
    > cert.json 2>/dev/null

# 6. 인증서, 프라이빗키, CA, 체인 추출
jq -r '.data.certificate' cert.json > vault.crt
jq -r '.data.private_key' cert.json > vault.key
jq -r '.data.issuing_ca' cert.json > ca.crt
jq -r '.data.ca_chain[]?' cert.json > chain.crt

# 7. 마운트 폴더로 복사
sudo cp vault.crt vault.key $CERT_DIR/

# 8. 권한 설정
sudo chown 100:100 $CERT_DIR/vault.key

info "임시 인증서(PKI) 발급 및 저장 완료"

info "===[4/6] 인증서 반영 위해 Vault 컨테이너 재가동"
sudo docker compose restart vault

info "===[5/6] 재언실/로그인 수동 진행 후 상태 점검"
echo "------------------------------------------------------"
echo "[수동 4] Vault 재언실:"
echo "  sudo docker exec -it vault vault operator unseal"
echo "[수동 5] Vault 로그인:"
echo "  sudo docker exec -it vault vault login"
echo "------------------------------------------------------"
read -p "위 수동 단계를 마치셨으면 Enter 키를 눌러주세요..."

info "===[6/6] Vault 상태 자동 검증"
sudo docker exec -it vault vault status
info "Vault PKI/인증서/상태가 정상적으로 적용되었는지 위 메시지를 확인하세요."

echo -e "${GREEN}===[완료] Vault PKI 및 인증서 발급/상태검증 워크플로우가 완료되었습니다.${NC}"
