#!/bin/bash
# Bitwarden 서버 컨테이너 설치 준비 스크립트 (sudo로 실행 필요)
# AI4RM 의료데이터 플랫폼 보안 표준 준수

set -euo pipefail  # 에러 발생 시 즉시 종료

# 로깅 함수
log_audit() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [AUDIT] $1" | sudo tee -a /var/log/ai4rm/security-audit.log
}

log_info() {
    echo "[INFO] $1"
}

# 사전준비 확인 (보안을 위해 매뉴얼로 진행 권장)
log_info "전제조건: bitwarden 사용자/그룹이 생성되어 있어야 합니다"
if ! id bitwarden &>/dev/null; then
    echo "[ERROR] bitwarden 사용자가 존재하지 않습니다. 먼저 생성해주세요:"
    echo "sudo useradd bitwarden"
    exit 1
fi

# AI4RM 표준 디렉토리 구조 생성
log_info "AI4RM 표준 디렉토리 구조 생성 중..."

# 1. 서비스별 Docker 디렉토리 (의료데이터 컨테이너 격리)
sudo mkdir -p /opt/ai4rm/docker/bitwarden/bwdata/
sudo chown -R bitwarden:bitwarden /opt/ai4rm/docker/bitwarden
sudo chmod -R 750 /opt/ai4rm/docker/bitwarden

# 2. 서비스별 백업 디렉토리 (GDPR 데이터 보존 요구사항)
sudo mkdir -p /opt/ai4rm/.backup/bitwarden/bwdata/
sudo chown -R bitwarden:bitwarden /opt/ai4rm/.backup/bitwarden
sudo chmod -R 700 /opt/ai4rm/.backup/bitwarden  # 백업은 더 엄격한 권한

# 3. 서비스별 운영 스크립트 디렉토리 (확장성 고려)
sudo mkdir -p /opt/ai4rm/scripts/bitwarden/
sudo cp /home/ben/projects/ai4rm/make/install_bitwarden.sh /opt/ai4rm/scripts/bitwarden/
sudo cp /home/ben/projects/ai4rm/make/backup_bitwarden.sh /opt/ai4rm/scripts/bitwarden/
sudo cp /home/ben/projects/ai4rm/make/restore_bitwarden.sh /opt/ai4rm/scripts/bitwarden/

# 의료데이터 환경 보안 강화: 소유자만 실행 가능
sudo chown -R bitwarden:bitwarden /opt/ai4rm/scripts/bitwarden
sudo chmod 700 /opt/ai4rm/scripts/bitwarden/install_bitwarden.sh
sudo chmod 700 /opt/ai4rm/scripts/bitwarden/backup_bitwarden.sh
sudo chmod 700 /opt/ai4rm/scripts/bitwarden/restore_bitwarden.sh

# 감사 로깅 (개인정보보호법 제28조 준수)
log_audit "Bitwarden 설치 준비 완료 - 사용자: $(whoami), 서비스: bitwarden"  

# 감사 로깅 (개인정보보호법 제28조 준수)
log_audit "Bitwarden 설치 준비 완료 - 사용자: $(whoami), 서비스: bitwarden"

# 결과 확인: 주요 폴더/파일 상태 출력
log_info "디렉토리/권한/소유자 상태 확인"
ls -ld /opt/ai4rm/docker/bitwarden
ls -ld /opt/ai4rm/docker/bitwarden/bwdata
ls -ld /opt/ai4rm/.backup/bitwarden
ls -ld /opt/ai4rm/.backup/bitwarden/bwdata
ls -ld /opt/ai4rm/scripts/bitwarden
ls -l /opt/ai4rm/scripts/bitwarden/install_bitwarden.sh
ls -l /opt/ai4rm/scripts/bitwarden/backup_bitwarden.sh
ls -l /opt/ai4rm/scripts/bitwarden/restore_bitwarden.sh

log_info "Bitwarden 설치 준비 완료"
log_info "다음 단계: su - bitwarden 후 /opt/ai4rm/scripts/bitwarden/install_bitwarden.sh 실행"

# 전체 구조 확인 (선택사항)
if command -v tree &> /dev/null; then
    tree -L 4 -a /opt/ai4rm/
else
    log_info "tree 명령어가 설치되지 않았습니다. 수동으로 구조를 확인하세요."
fi