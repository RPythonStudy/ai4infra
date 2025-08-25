#!/usr/bin/env python3
"""
AI4RM OpenLDAP 설치/관리 CLI
- docker-compose 기반 OpenLDAP 컨테이너 설치/상태 확인/로그 조회
- 표준 로깅 및 감사 로그 중복 기록
"""

import subprocess
import sys
import os
from logger import get_logger
from datetime import datetime, timezone
import socket

DOCKER_COMPOSE_PATH = "templates/ldap/docker-compose.yml"

def audit_log(action: str, detail: dict = None, compliance: str = "개인정보보호법 제28조"):
    import logging
    user = os.getenv("USER") or "unknown"
    log = {
        "action": action,
        "user": user,
        "process_id": os.getpid(),
        "server_id": socket.gethostname(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "compliance_check": compliance
    }
    if detail:
        log.update(detail)
    logging.getLogger("audit").info(log)

def run_cmd(cmd, desc):
    logger = get_logger("openldap_install_cli")
    logger.info(f"{desc} 명령 실행: {cmd}")
    audit_log(action=desc, detail={"cmd": cmd})
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        logger.info(f"{desc} 성공")
        audit_log(action=f"{desc}_success", detail={"stdout": result.stdout})
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(f"{desc} 실패: {e.stderr}")
        audit_log(action=f"{desc}_fail", detail={"stderr": e.stderr})
        print(e.stderr, file=sys.stderr)
        sys.exit(1)

def install():
    run_cmd(f"docker compose -f {DOCKER_COMPOSE_PATH} up -d", "OpenLDAP 설치")

def status():
    run_cmd(f"docker compose -f {DOCKER_COMPOSE_PATH} ps", "OpenLDAP 상태 확인")

def logs():
    run_cmd(f"docker compose -f {DOCKER_COMPOSE_PATH} logs -f openldap", "OpenLDAP 로그 조회")

def main():
    if len(sys.argv) < 2:
        print("사용법: openldap_install_cli.py [install|status|logs]")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "install":
        install()
    elif cmd == "status":
        status()
    elif cmd == "logs":
        logs()
    else:
        print("지원하지 않는 명령입니다: install, status, logs 중 선택하세요.")
        sys.exit(1)

if __name__ == "__main__":
    main()
