#!/bin/bash
# Bitwarden docker-compose.override.yml 복사 및 권한 설정 스크립트 (sudo로 실행)
# 프로젝트 폴더에서 sudo bash make/sudo_override_yml.sh로 실행

INSTALL_DIR="/opt/ai4rm/docker/bitwarden"
SRC_YML="/home/ben/projects/ai4rm/templates/bitwarden/docker-compose.override.yml"
TARGET_YML="$INSTALL_DIR/bwdata/docker/docker-compose.override.yml"

# 경로 확인 및 폴더 생성
if [ ! -d "$INSTALL_DIR/bwdata/docker" ]; then
  sudo mkdir -p "$INSTALL_DIR/bwdata/docker"
fi

# 파일 복사
sudo cp "$SRC_YML" "$TARGET_YML"

# 소유자/권한 설정
sudo chown bitwarden:bitwarden "$TARGET_YML"
sudo chmod 644 "$TARGET_YML"

# 결과 확인
ls -l "$TARGET_YML"
echo "[INFO] docker-compose.override.yml 복사 및 권한 설정 완료"
