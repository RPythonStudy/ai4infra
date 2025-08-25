# src/security_infra/compose_manager.py

import subprocess
from pathlib import Path

def check_sudoers_for_docker(logger):
    test_cmd = ["sudo", "-n", "docker", "ps"]
    result = subprocess.run(test_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        msg = (
            "[ERROR] 현재 사용자는 'sudo docker' 명령에 패스워드 없이 접근할 수 없습니다.\n"
            "아래 라인을 '/etc/sudoers'에 추가해야 완전 자동화가 가능합니다:\n"
            "  <USERNAME> ALL=(ALL) NOPASSWD: /usr/bin/docker, /usr/bin/docker-compose\n"
            "오류 메시지: " + result.stderr.decode().strip()
        )
        logger.error(msg)
        return False
    return True

def compose_command(action, service, compose_file, logger, make_audit_log):
    service_map = {
        "all": [],
        "vault": ["vault"],
        "elk": ["elasticsearch", "logstash", "kibana"],
        "keycloak": ["keycloak"],
        "openldap": ["openldap"],
    }
    if service not in service_map:
        logger.error(make_audit_log("compose-실패", action=action, service=service, result="서비스미지원"))
        raise ValueError(f"[ERROR] 지원하지 않는 서비스: {service}")
    svc_args = service_map[service]
    cmd = ["sudo", "docker", "compose", "-f", str(compose_file)]
    if action == "up":
        cmd += ["up", "-d"] + svc_args
    elif action == "down":
        cmd += ["down"] + svc_args
    elif action == "restart":
        cmd += ["restart"] + svc_args
    elif action == "logs":
        cmd += ["logs", "-f"] + svc_args
    elif action in ["ps", "status"]:
        cmd += ["ps"] + svc_args
    else:
        logger.error(make_audit_log("compose-실패", action=action, service=service, result="action미지원"))
        raise ValueError(f"[ERROR] 지원하지 않는 action: {action}")

    # 1. audit log (실행 전)
    logger.info(make_audit_log("compose-실행시도", action=action, service=service, cmd=" ".join(cmd)))

    # 2. sudoers 체크
    if not check_sudoers_for_docker(logger):
        logger.error(make_audit_log("compose-실패", action=action, service=service, result="sudoers미설정"))
        raise PermissionError("[ERROR] sudoers 설정이 필요합니다.")

    # 3. compose 명령 실행
    try:
        result = subprocess.run(cmd, check=True)
        logger.info(make_audit_log("compose-성공", action=action, service=service, result="OK"))
        return "[성공]"
    except subprocess.CalledProcessError as e:
        logger.error(make_audit_log(
            "compose-실패", action=action, service=service, result="실패",
            stderr=e.stderr.decode() if e.stderr else None,
            returncode=e.returncode
        ))
        raise RuntimeError(f"[실패] docker compose 명령 오류: {e}")
