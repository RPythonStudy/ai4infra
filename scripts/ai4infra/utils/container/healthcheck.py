
import subprocess
import time
from common.logger import log_info, log_warn, log_error


def check_container(service: str, custom_check=None) -> bool:
    # [변경] 모든 서비스에 대해 일관된 이름 규칙 적용
    filter_name = f"ai4infra-{service}"

    log_info(f"[check_container] 점검 시작 → {service} ({filter_name})")

    # 최대 120초(초기화 대기)
    for attempt in range(120):
        ps = subprocess.run(
            f"docker ps --filter name={filter_name} --format '{{{{.Status}}}}'",
            shell=True, text=True, capture_output=True
        )
        statuses = ps.stdout.strip().splitlines()

        # 1) 컨테이너 없음
        if not statuses:
            log_warn(f"[check_container] 컨테이너 없음 → 재시도 ({attempt+1}/120)")
            time.sleep(1)
            continue

        # 2) Up 상태 확인 (공통)
        if any("up" in s.lower() for s in statuses):
            break
        
        log_info(f"[check_container] {service} 준비중 → 재시도 ({attempt+1}/120)")
        time.sleep(1)

    else:
        log_error(f"[check_container] {service}: 상태 정상화 실패")
        return False

    # ----------------------------------------------------------------------
    # 로그 검사 (간결)
    # ----------------------------------------------------------------------
    logs = subprocess.run(
        f"docker logs {filter_name}",
        shell=True, text=True, capture_output=True
    )
    lowlog = logs.stdout.lower()

    if "error" in lowlog or "failed" in lowlog:
        log_warn("[check_container] 로그에서 error/failed 감지됨")
        # 오류 상세 출력 (최근 10줄 중 에러 포함 라인)
        lines = logs.stdout.splitlines()
        for line in lines[-20:]: 
            if "error" in line.lower() or "failed" in line.lower():
                log_warn(f"   >> {line}")
    else:
        log_info("[check_container] 로그 정상(Log clean)")

    # custom_check (Vault/Postgres 등)
    if custom_check:
        return custom_check(service)

    log_info(f"[check_container] 기본 점검 완료(PASS) → {service}")
    return True