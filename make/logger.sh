#!/bin/bash
# AI4RM 쉘스크립트 표준 로거 (make/logger.sh)
# 
# 작성자: BenKorea
# 작성일: 2025-07-21
# 버전: 0.1.0
# 
# 설명: AI4RM 프로젝트 표준 로깅 시스템 (쉘스크립트용)
#       - 운영 로그: stdout + /var/log/ai4rm/service.log (JSON)
#       - 감사 로그: /var/log/ai4rm/audit.log (JSON)
#       - 6단계 로그레벨 지원: CRITICAL, ERROR, WARNING, INFO, DEBUG, TRACE
#       - 환경변수로 로그레벨/경로 제어 가능
#       - 이모지/이모티콘 금지, 개인정보 로그 금지
# 
# 사용법:
#   # 스크립트에서 로거 불러오기
#   source make/logger.sh
#   
#   # 운영 로그 (stdout + 파일)
#   service_log INFO "백업 작업 시작"
#   service_log ERROR "파일 처리 실패"
#   
#   # 감사 로그 (파일만)
#   audit_log "backup_started" '"target":"bitwarden","status":"initiated"'
#   audit_log "patient_data_processed" '"record_count":100'
# 
# 환경변수:
#   LOG_LEVEL - 로그레벨 (기본값: INFO)
#   LOG_PATH - 운영로그 파일 경로 (기본값: /var/log/ai4rm/service.log)
#   AUDIT_PATH - 감사로그 파일 경로 (기본값: /var/log/ai4rm/audit.log)

# 로그레벨 매핑
declare -A LOG_LEVELS=(
  [CRITICAL]=0
  [ERROR]=1
  [WARNING]=2
  [INFO]=3
  [DEBUG]=4
  [TRACE]=5
)

LOG_LEVEL="${LOG_LEVEL:-INFO}"
LOG_PATH="${LOG_PATH:-/var/log/ai4rm/service.log}"
AUDIT_PATH="${AUDIT_PATH:-/var/log/ai4rm/audit.log}"

# 로그 디렉토리 생성
mkdir -p "$(dirname "$LOG_PATH")"
mkdir -p "$(dirname "$AUDIT_PATH")"

# 로그레벨 비교 함수
function _should_log() {
  local level="$1"
  [[ ${LOG_LEVELS[$level]} -le ${LOG_LEVELS[$LOG_LEVEL]} ]]
}

# 운영 로그 기록 (stdout + JSON 파일)
function service_log() {
  local level="$1"
  local msg="$2"
  local ts
  ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  if _should_log "$level"; then
    # stdout 출력 (운영로그만)
    echo "[$ts] [$level] $msg"
    # 파일(JSON) 기록
    printf '{"timestamp":"%s","level":"%s","message":"%s","logger":"shell_script","pathname":"%s","funcName":"service_log"}\n' \
      "$ts" "$level" "$msg" "$0" >> "$LOG_PATH"
  fi
}

# 감사 로그 기록 (파일만, stdout 없음)
function audit_log() {
  local action="$1"
  local detail="$2"
  local compliance="${3:-개인정보보호법_제28조}"
  local user="${USER:-unknown}"
  local pid="$$"
  local host
  host="$(hostname)"
  local ts
  ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  
  # 감사로그는 파일에만 기록 (stdout 없음)
  printf '{"action":"%s","user":"%s","process_id":"%s","server_id":"%s","timestamp":"%s","compliance_check":"%s"%s}\n' \
    "$action" "$user" "$pid" "$host" "$ts" "$compliance" \
    "${detail:+,$detail}" >> "$AUDIT_PATH"
}

# 사용 예시
# service_log INFO "백업 시작"
# audit_log "backup_started" '"target":"bitwarden"'
