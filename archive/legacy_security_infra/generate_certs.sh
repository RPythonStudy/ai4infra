#!/bin/bash
# ------------------------------------------------------------------------------
# File: generate_certs.sh (임시 extfile로 v3_ca 확장 자동주입, 완전 자동화)
# Description: Root CA + Intermediate CA 생성, 신뢰 anchor 등록(리눅스/WSL2) 자동화
# Author: BenKorea <benkorea.ai@gmail.com>
# Usage: sudo bash generate_certs.sh
# ------------------------------------------------------------------------------

set -e

CA_DIR="/opt/ai4rm/ca"
CA_KEY="$CA_DIR/rootCA.key"
CA_CRT="$CA_DIR/rootCA.crt"
INT_KEY="$CA_DIR/intCA.key"
INT_CSR="$CA_DIR/intCA.csr"
INT_CRT="$CA_DIR/intCA.crt"
CA_DAYS=3650      # Root CA 유효기간(10년)
INT_DAYS=1825     # Intermediate CA 유효기간(5년)
CA_BASENAME="ai4rm_rootCA.crt"
TRUST_DIR="/usr/local/share/ca-certificates"
BUNDLE_FILE="/etc/ssl/certs/ca-certificates.crt"

echo "[DEBUG] === generate_certs.sh(extfile v3_ca 자동주입) 시작 ==="

# 1. CA 디렉토리 생성 및 권한 설정
echo "[DEBUG] CA 디렉토리 확인/생성: $CA_DIR"
sudo mkdir -p "$CA_DIR"
sudo chown root:root "$CA_DIR"
sudo chmod 700 "$CA_DIR"
ls -ld "$CA_DIR"

# 2. Root CA 생성(존재 시 skip)
if [ ! -f "$CA_KEY" ] && [ ! -f "$CA_CRT" ]; then
  echo "[INFO] Root CA(v3_ca 확장 extfile) 생성 중..."
  sudo openssl genrsa -out "$CA_KEY" 4096

  # 임시 extfile에 v3_ca 확장 명시
  cat > /tmp/v3ca_ext.cnf <<EOF
basicConstraints = critical,CA:TRUE
keyUsage = critical, digitalSignature, cRLSign, keyCertSign
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid:always,issuer
EOF

  sudo openssl req -x509 -new -nodes -key "$CA_KEY" -sha256 -days $CA_DAYS \
    -out "$CA_CRT" \
    -subj "/CN=ai4rm-root-ca" \
    -extensions v3_ca \
    -extfile /tmp/v3ca_ext.cnf

  sudo rm -f /tmp/v3ca_ext.cnf

  sudo chown root:root "$CA_KEY" "$CA_CRT"
  sudo chmod 600 "$CA_KEY"
  sudo chmod 644 "$CA_CRT"
  echo "[OK] Root CA(v3_ca extfile) 생성 완료"
else
  echo "[SKIP] Root CA가 이미 존재합니다."
  ls -l "$CA_KEY" "$CA_CRT"
fi

# 3. Intermediate CA 생성 및 서명 (intCA.crt만 기준으로 동작)
if [ ! -f "$INT_CRT" ]; then
  echo "[INFO] Intermediate CA 서명(또는 신규 생성) 중..."

  # 필요시 key/csr 생성
  if [ ! -f "$INT_KEY" ]; then
    sudo openssl genrsa -out "$INT_KEY" 4096
    echo "[DEBUG] intCA.key 생성됨:"
    ls -l "$INT_KEY"
  fi

  if [ ! -f "$INT_CSR" ]; then
    sudo openssl req -new -key "$INT_KEY" -out "$INT_CSR" -subj "/CN=ai4rm-intermediate-ca"
    echo "[DEBUG] intCA.csr 생성됨:"
    ls -l "$INT_CSR"
  fi

  EXTFILE=$(mktemp)
  echo "basicConstraints=CA:TRUE,pathlen:0" | sudo tee "$EXTFILE" > /dev/null
  echo "[DEBUG] extfile 위치: $EXTFILE, 내용:"
  cat "$EXTFILE"

  set -x
  sudo openssl x509 -req -in "$INT_CSR" -CA "$CA_CRT" -CAkey "$CA_KEY" \
    -CAcreateserial -out "$INT_CRT" -days $INT_DAYS -sha256 \
    -extfile "$EXTFILE"
  set +x

  sudo rm -f "$EXTFILE"

  sudo chown root:root "$INT_KEY" "$INT_CSR" "$INT_CRT"
  sudo chmod 600 "$INT_KEY"
  sudo chmod 600 "$INT_CSR"
  sudo chmod 644 "$INT_CRT"
  echo "[OK] Intermediate CA 생성/서명 완료"
  ls -l "$INT_KEY" "$INT_CSR" "$INT_CRT"
else
  echo "[SKIP] Intermediate CA가 이미 존재합니다."
  ls -l "$INT_KEY" "$INT_CSR" "$INT_CRT" 2>/dev/null || true
fi

# 4. Root CA 신뢰 anchor로 등록(리눅스/WSL2용, 이미 등록 시 skip)
if [ -f "$CA_CRT" ]; then
  if [ ! -f "$TRUST_DIR/$CA_BASENAME" ]; then
    echo "[INFO] Root CA를 시스템 신뢰 anchor로 등록 중..."
    sudo cp "$CA_CRT" "$TRUST_DIR/$CA_BASENAME"
    echo "[DEBUG] 복사 후 해당 파일 정보:"
    ls -l "$TRUST_DIR/$CA_BASENAME"
  else
    echo "[SKIP] 이미 시스템 신뢰 anchor에 등록 준비됨."
    ls -l "$TRUST_DIR/$CA_BASENAME"
  fi

  echo "[DEBUG] update-ca-certificates 명령 실행!"
  sudo update-ca-certificates --fresh | tee /tmp/update_ca_cert.log

  echo "[DEBUG] update-ca-certificates 실행 결과:"
  cat /tmp/update_ca_cert.log

  echo "[DEBUG] 번들 파일에서 ai4rm 등록 확인:"
  grep -A 1 "ai4rm" "$BUNDLE_FILE" || echo "[WARN] ca-certificates.crt에 ai4rm이 보이지 않습니다!"

  echo "[DEBUG] symlink 확인:"
  ls -l /etc/ssl/certs | grep ai4rm || echo "[WARN] symlink도 없음"
fi

echo ""
echo "[INFO] 모든 과정이 완료되었습니다."
ls -l "$CA_DIR"
echo " - Root CA: $CA_CRT"
echo " - Intermediate CA: $INT_CRT"
echo " - 신뢰 anchor 등록: $TRUST_DIR/$CA_BASENAME"
echo "[DEBUG] === generate_certs.sh 종료 ==="

