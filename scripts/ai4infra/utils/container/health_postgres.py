#!/usr/bin/env python3

import subprocess
import time

from common.logger import log_info, log_error, log_warn


def check_postgres(service: str) -> bool:

    container = f"ai4infra-{service}"

    # ========================================
    # 1) Docker health 확인
    # ========================================
    for attempt in range(60):
        ps = subprocess.run(
            f"sudo docker ps --filter name={container} --format '{{{{.Status}}}}'",
            shell=True, text=True, capture_output=True
        )
        status = ps.stdout.strip().lower()

        if "healthy" in status:
            log_info(f"[check_postgres] Docker healthcheck 통과 (healthy) → {attempt+1}번째 시도")
            break

        if "unhealthy" in status:
            log_error("[check_postgres] Docker healthcheck: unhealthy")
            return False

        log_info(f"[check_postgres] PostgreSQL 준비중... 상태={status} → 재시도 ({attempt+1}/60)")
        time.sleep(1)
    else:
        log_error("[check_postgres] 60초 동안 healthy 상태가 되지 않음")
        return False

    # ========================================
    # 2) SELECT 1 확인
    # ========================================
    result = subprocess.run(
        f"sudo docker exec {container} psql -U postgres -c 'SELECT 1;'",
        shell=True, text=True, capture_output=True
    )
    if "1 row" in result.stdout:
        log_info("[check_postgres] SELECT 1 성공 → PostgreSQL 정상 동작")
    else:
        log_warn("[check_postgres] SELECT 1 실패 (그러나 healthcheck는 정상입니다)")

    # ========================================
    # 3) TLS 기본 상태 확인
    # ========================================
    log_info("[check_postgres] TLS 설정 점검 시작")

    tls_status = subprocess.run(
        f"sudo docker exec {container} psql -U postgres -t -c \"SHOW ssl;\"",
        shell=True, text=True, capture_output=True
    )
    ssl_value = tls_status.stdout.strip().lower()

    if ssl_value == "on":
        log_info("[check_postgres] TLS 활성화 확인됨 (ssl=on)")
    else:
        log_warn(f"[check_postgres] TLS 비활성화 (ssl={ssl_value}) → 자동 원인 분석 시작")
        return check_postgres_tls_diagnostics(container)


    # TLS가 실제 "on"이면 기본 인증 파일 경로와 존재 여부는 별도 점검
    return check_postgres_tls_diagnostics(container, tls_must_be_on=True)

def check_postgres_tls_diagnostics(container: str, tls_must_be_on: bool=False) -> bool:
    log_info("[TLS-DIAG] PostgreSQL TLS 진단 시작")

    # ---------------------------
    # ① 실제 config_file 경로 확인
    # ---------------------------
    cfg = run_psql_show(container, "config_file")
    data_dir = run_psql_show(container, "data_directory")

    log_info(f"[TLS-DIAG] config_file = {cfg}")
    log_info(f"[TLS-DIAG] data_directory = {data_dir}")

    if "postgresql.conf" not in cfg:
        log_error("[TLS-DIAG] postgresql.conf 파일 경로 비정상 → override 적용 안됨 가능성이 매우 높습니다.")


    # ---------------------------
    # ② 설정파일 내부에서 SSL 항목 확인
    # ---------------------------
    grep_ssl = subprocess.run(
        f"sudo docker exec {container} grep -iE '^[ ]*ssl' {cfg}",
        shell=True, text=True, capture_output=True
    )

    if grep_ssl.returncode != 0:
        log_error("[TLS-DIAG] postgresql.conf에서 ssl 관련 항목을 찾을 수 없습니다.")
    else:
        log_info(f"[TLS-DIAG] postgresql.conf 내 SSL 항목:\n{grep_ssl.stdout.strip()}")


    # ---------------------------
    # ③ SHOW ssl_* 파라미터 확인
    # ---------------------------
    ssl_cert = run_psql_show(container, "ssl_cert_file")
    ssl_key  = run_psql_show(container, "ssl_key_file")
    ssl_ca   = run_psql_show(container, "ssl_ca_file")

    log_info(f"[TLS-DIAG] ssl_cert_file = {ssl_cert}")
    log_info(f"[TLS-DIAG] ssl_key_file  = {ssl_key}")
    log_info(f"[TLS-DIAG] ssl_ca_file   = {ssl_ca}")

    # ---------------------------
    # ④ 파일 존재 여부 테스트
    # ---------------------------
    missing = False
    for p in [ssl_cert, ssl_key, ssl_ca]:
        if not file_exists_in_container(container, p):
            log_error(f"[TLS-DIAG] 파일 없음 → {p}")
            missing = True
        else:
            log_info(f"[TLS-DIAG] 파일 존재 확인 → {p}")

    # ---------------------------
    # ⑤ key 파일 권한 및 소유자 검증
    # ---------------------------
    if file_exists_in_container(container, ssl_key):
        perm = run_stat(container, ssl_key)
        log_info(f"[TLS-DIAG] key 파일 권한 = {perm}")

        if not perm.startswith("600"):
            log_error(f"[TLS-DIAG] key 파일 권한 오류 → 600 이어야 합니다: {ssl_key}")
            missing = True
        
        owner = run_owner(container, ssl_key)
        log_info(f"[TLS-DIAG] key 파일 소유자 = {owner}")

        if "postgres:postgres" not in owner:
            log_error(f"[TLS-DIAG] key 파일 소유자 오류 → postgres:postgres 이어야 합니다.")
            missing = True

    # ---------------------------
    # TLS가 반드시 켜져 있어야 하는 모드일 때
    # ---------------------------
    if tls_must_be_on:
        ssl_state = run_psql_show(container, "ssl")
        if ssl_state != "on":
            log_error("[TLS-DIAG] TLS가 켜져 있어야 하는데 ssl=off 입니다.")
            return False

    if missing:
        log_error("[TLS-DIAG] TLS 설정 오류 감지됨")
        return False

    log_info("[TLS-DIAG] TLS 설정 및 파일 검증 완료 (모두 OK)")
    return True

def run_psql_show(container: str, name: str) -> str:
    cmd = f"sudo docker exec {container} psql -U postgres -t -c \"SHOW {name};\""
    res = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return res.stdout.strip()

def file_exists_in_container(container: str, path: str) -> bool:
    test = subprocess.run(f"sudo docker exec {container} test -f '{path}'", shell=True)
    return test.returncode == 0

def run_stat(container: str, path: str) -> str:
    cmd = f"sudo docker exec {container} stat -c '%a' '{path}'"
    res = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return res.stdout.strip()

def run_owner(container: str, path: str) -> str:
    cmd = f"sudo docker exec {container} stat -c '%U:%G' '{path}'"
    res = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return res.stdout.strip()
