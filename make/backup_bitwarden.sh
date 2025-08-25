#!/bin/bash
# Bitwarden 데이터 백업 스크립트

# sudo_prepare_install.sh에 의해 아래가 실행되었다고 가정합니다.
# sudo mkdir -p /opt/ai4rm/.backup/bitwarden/bwdata/
# sudo chown -R bitwarden:bitwarden /opt/ai4rm/.backup/bitwarden/
# sudo mkdir -p /opt/ai4rm/scripts/
# sudo chown -R bitwarden:bitwarden /opt/ai4rm/scripts/
# sudo cp /home/ben/projects/ai4rm/make/backup_bitwarden.sh /opt/ai4rm/scripts/backup_bitwarden.sh
# sudo chown -R bitwarden:bitwarden /opt/ai4rm/scripts/backup_bitwarden.sh

# bitwarden 계정으로 전환한 뒤에 이 스크립트가 실행된다고 가정합니다.
# su - bitwarden
# 아래의 경로로 자동이동이 되므로 실행명령은 bash scripts/backup_bitwarden.sh로 가정합니다. 

cd /opt/ai4rm/
sudo docker stop bitwarden
rsync -avz /opt/ai4rm/docker/bitwarden/bwdata /opt/ai4rm/.backup/bitwarden/

echo "[INFO] 백업결과 폴더구조"
tree -L 4 -a /opt/ai4rm/