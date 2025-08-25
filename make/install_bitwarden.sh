#!/bin/bash
# Bitwarden 서버 설치 스크립트 (bitwarden 계정에서 실행)

INSTALL_DIR="/opt/ai4rm/docker/bitwarden"

# 1. 설치 폴더로 이동
cd "$INSTALL_DIR" || { echo "[ERROR] 설치 폴더 이동 실패: $INSTALL_DIR"; exit 1; }

# 2. 설치 스크립트 다운로드 및 권한 설정
curl -Lso bitwarden.sh "https://func.bitwarden.com/api/dl/?app=self-host&platform=linux"
chmod 700 bitwarden.sh

# 3. Bitwarden 서버 설치 (sudoers 설정 필요)
sudo ./bitwarden.sh install



# 5. 설치 결과 확인
echo "[INFO] Bitwarden 설치 결과 폴더 구조"
tree -L 2 -a "$INSTALL_DIR"

echo "[INFO] Bitwarden 서버 설치 완료"