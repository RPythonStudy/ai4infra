#!/bin/bash
# Bitwarden 데이터 복구 스크립트
# bitwarden 계정으로 실행 필요

# 복구 전 컨테이너 중지
sudo docker stop bitwarden

# 기존 데이터 폴더 백업(옵션, 안전)
if [ -d /opt/ai4rm/docker/bitwarden/bwdata ]; then
  mv /opt/ai4rm/docker/bitwarden/bwdata /opt/ai4rm/docker/bitwarden/bwdata_backup_$(date +%Y%m%d_%H%M%S)
  echo "[INFO] 기존 bwdata 폴더 백업 완료"
fi

# 백업 데이터 복원
rsync -avz /opt/ai4rm/.backup/bitwarden/bwdata /opt/ai4rm/docker/bitwarden/

# 컨테이너 재시작
sudo docker start bitwarden

echo "[INFO] 복구결과 폴더구조"
tree -L 3 -a /opt/ai4rm/
