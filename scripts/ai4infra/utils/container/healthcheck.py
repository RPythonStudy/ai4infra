
import subprocess
import time
from common.logger import log_info, log_warn, log_error


def check_container(service: str, custom_check=None) -> bool:
    # 1) Bitwarden만 prefix 매칭 필요
    if service == "bitwarden":
        filter_name = "ai4infra-bitwarden-"
    else:
        filter_name = f"ai4infra-{service}"

    log_info(f"[check_container] 점검 시작 → {service} ({filter_name}*)")

    # 최대 120초(초기화 대기)
    for attempt in range(120):
        ps = subprocess.run(
            f"sudo docker ps --filter name={filter_name} --format '{{{{.Status}}}}'",
            shell=True, text=True, capture_output=True
        )
        statuses = ps.stdout.strip().splitlines()

        # 1) 컨테이너 없음
        if not statuses:
            log_warn(f"[check_container] 컨테이너 없음 → 재시도 ({attempt+1}/120)")
            time.sleep(1)
            continue

        # ------------------------------------------------------------------
        # Bitwarden: 여러 컨테이너의 health를 종합적으로 판단
        # ------------------------------------------------------------------
        if service == "bitwarden":
            low = ps.stdout.lower()

            if "unhealthy" in low:
                log_error("[check_container] Bitwarden unhealthy 감지 → 실패")
                return False
            if "starting" in low:
                log_info(f"[check_container] Bitwarden 초기화 중 → 재시도 ({attempt+1}/120)")
                time.sleep(1)
                continue

            # starting 없음 + unhealthy 없음 = 정상
            log_info("[check_container] Bitwarden health 정상")
            break

        # ------------------------------------------------------------------
        # Vault: 단순히 Up 상태면 PASS
        # ------------------------------------------------------------------
        elif service == "vault":
            if any("up" in s.lower() for s in statuses):
                break
            log_info(f"[check_container] Vault 대기중 → 재시도 ({attempt+1}/120)")
            time.sleep(1)
            continue

        # ------------------------------------------------------------------
        # 기타 서비스: 단일 컨테이너 Up 확인
        # ------------------------------------------------------------------
        else:
            if any("up" in s.lower() for s in statuses):
                break
            log_info(f"[check_container] {service} 준비중 → 재시도 ({attempt+1}/120)")
            time.sleep(1)
            continue

    else:
        log_error(f"[check_container] {service}: 상태 정상화 실패")
        return False

    # ----------------------------------------------------------------------
    # 로그 검사 (간결)
    # ----------------------------------------------------------------------
    logs = subprocess.run(
        f"sudo docker logs {filter_name}",
        shell=True, text=True, capture_output=True
    )
    lowlog = logs.stdout.lower()

    if "error" in lowlog or "failed" in lowlog:
        log_warn("[check_container] 로그에서 error/failed 감지됨")
    else:
        log_info("[check_container] 로그 정상(Log clean)")

    # custom_check (Vault/Postgres 등)
    if custom_check:
        return custom_check(service)

    log_info(f"[check_container] 기본 점검 완료(PASS) → {service}")
    return True