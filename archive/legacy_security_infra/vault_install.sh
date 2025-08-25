#!/bin/bash

set -e

info() { echo -e "\033[32m[INFO]\033[0m $1"; }
fail() { echo -e "\033[31m[FAIL]\033[0m $1"; exit 1; }

# [1] 디렉토리 생성 및 권한 설정
sudo mkdir -p \
  /opt/ai4rm/docker/vault/config \
  /opt/ai4rm/docker/vault/file \
  /opt/ai4rm/docker/vault/certs \
  /opt/ai4rm/docker/vault/logs \
  /opt/ai4rm/docker/vault/agent/config \
  /opt/ai4rm/docker/vault/agent/sink

sudo chown -R 100:100 \
  /opt/ai4rm/docker/vault/config \
  /opt/ai4rm/docker/vault/file \
  /opt/ai4rm/docker/vault/certs \
  /opt/ai4rm/docker/vault/logs \
  /opt/ai4rm/docker/vault/agent/config \
  /opt/ai4rm/docker/vault/agent/sink

sudo chmod -R 750 \
  /opt/ai4rm/docker/vault/config \
  /opt/ai4rm/docker/vault/file \
  /opt/ai4rm/docker/vault/certs \
  /opt/ai4rm/docker/vault/logs \
  /opt/ai4rm/docker/vault/agent/config \
  /opt/ai4rm/docker/vault/agent/sink

info "### [3/4] Vault 임시 인증서 (존재 시 skip)"

CERT_DIR="/opt/ai4rm/docker/vault/certs"
CERT_KEY=${CERT_DIR}/vault.key
CERT_CRT=${CERT_DIR}/vault.crt

# 인증서가 존재하면 skip, 아니면 생성
if [ -f "$CERT_KEY" ] && [ -f "$CERT_CRT" ]; then
    info "임시 인증서가 이미 존재하여 생성하지 않습니다."
else
    sudo openssl req \
      -x509 -newkey rsa:2048 \
      -keyout "$CERT_KEY" \
      -out "$CERT_CRT" \
      -days 14 \
      -nodes \
      -subj "/CN=localhost" \
      -addext "subjectAltName = DNS:localhost, IP:127.0.0.1, DNS:elasticsearch, DNS:kibana, DNS:logstash, DNS:keycloak, DNS:vault, DNS:openldap" \
      >/dev/null 2>&1
    sudo chown 100:100 "$CERT_KEY" "$CERT_CRT"
    sudo chmod 640 "$CERT_KEY" "$CERT_CRT"
    if [ -f "$CERT_KEY" ] && [ -f "$CERT_CRT" ]; then
        CRT_TIME=$(stat -c %y "$CERT_CRT")
        info "임시 인증서 생성시각: $CRT_TIME"
    else
        fail "Vault 임시 인증서 생성 실패"
    fi
fi


# [3] Vault 설정 파일/컴포즈 파일 복사 (존재 시 skip)
if [ -f /opt/ai4rm/docker/vault/docker-compose.yml ]; then
    info "docker-compose.yml 이미 존재하여 복사하지 않음"
else
    sudo cp ./templates/vault/docker-compose.yml  /opt/ai4rm/docker/vault/
fi

if [ -f /opt/ai4rm/docker/vault/config/vault.hcl ]; then
    info "vault.hcl 이미 존재하여 복사하지 않음"
else
    sudo cp ./templates/vault/conf/vault.hcl  /opt/ai4rm/docker/vault/config/
    sudo chown 100:100 /opt/ai4rm/docker/vault/config/vault.hcl
    sudo chmod 640     /opt/ai4rm/docker/vault/config/vault.hcl
fi

if [ -f /opt/ai4rm/docker/vault/agent/config/config.hcl ]; then
    info "config.hcl 이미 존재하여 복사하지 않음"
else
    sudo cp ./templates/vault/conf/config.hcl /opt/ai4rm/docker/vault/agent/config/
    sudo chown 100:100 /opt/ai4rm/docker/vault/agent/config/config.hcl
    sudo chmod 640     /opt/ai4rm/docker/vault/agent/config/config.hcl
fi

echo "[OK] Vault 서비스 프로비저닝 및 인증서(Intermediate CA 서명) 배포 완료."
