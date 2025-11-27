#!/usr/bin/env python3

import subprocess
import time
import json

from common.logger import log_debug, log_error, log_info, log_warn


VAULT_HEALTH_MAP = {
    200: "OK (initialized, unsealed, active)",
    429: "Standby (initialized, unsealed, standby)",
    472: "DR Secondary",
    473: "Performance Standby",
    474: "Standby but active node unreachable",
    501: "Not initialized",
    503: "Sealed (unsealed required)",
    530: "Node removed from cluster",
}

def check_vault(service: str) -> bool:
    container = f"ai4infra-{service}"
    url = "https://localhost:8200/v1/sys/health"

    success_attempt = None
    status_code = None
    response_body = None

    # --------------------------------------------
    # Retry loop (HTTP Status + JSON)
    # --------------------------------------------
    for attempt in range(20):
        result = subprocess.run(
            f"curl -sk -o /tmp/vault_health.json -w '%{{http_code}}' {url}",
            shell=True, text=True, capture_output=True
        )

        status_str = result.stdout.strip()

        # status_code만 먼저 파싱
        if status_str.isdigit():
            status_code = int(status_str)

        # JSON 본문 로드
        try:
            with open("/tmp/vault_health.json", "r") as f:
                response_body = f.read().strip()
        except:
            response_body = ""

        if status_code and response_body:
            success_attempt = attempt
            break

        log_warn(f"[check_vault] API healthcheck 실패 → 재시도 ({attempt+1}/20)")
        time.sleep(1)

    if success_attempt is None:
        log_error("[check_vault] 20회 실패 → Vault API 응답 없음")
        return False

    # --------------------------------------------
    # 성공 attempt 출력
    # --------------------------------------------
    log_info(f"[check_vault] API healthcheck 성공 → {success_attempt+1}번째 시도")

    # --------------------------------------------
    # Debug 모드일 때: HTTP Code 의미를 상세 표시
    # --------------------------------------------
    meaning = VAULT_HEALTH_MAP.get(status_code, "Unknown status")

    log_debug(f"[check_vault] HTTP Code: {status_code} → {meaning}")

    # --------------------------------------------
    # Info 모드용 간결한 status 출력
    # --------------------------------------------
    try:
        data = json.loads(response_body)
    except Exception as e:
        log_error(f"[check_vault] API JSON 파싱 실패: {e}")
        return False

    log_info(f" initialized: {data.get('initialized')}")
    log_info(f" sealed     : {data.get('sealed')}")
    log_info(f" standby    : {data.get('standby')}")
    log_info(f" version    : {data.get('version')}")

    return True
