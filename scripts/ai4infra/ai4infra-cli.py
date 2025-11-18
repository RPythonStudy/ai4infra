#!/usr/bin/env python3
"""
파일명: scripts/ai4infra/ai4infra-cli.py
인자: 
  - install: `서비스명` 또는 `all`를 인자로 하며 아래의 옵션이 있음
    - default: 컨테이너중단/데이터백업 후 멱등성 설치 
    -   reset: 컨테이너중단/데이터삭제 후 설치 (개발용)
변경이력:
  - 2025-11-16: 최초 구현 (BenKorea)
"""

# Standard library imports
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List

# Third-party imports
import typer
from dotenv import load_dotenv

# Local imports
from common.logger import log_debug, log_error, log_info
from utils.container_manager import (
    create_user,
    add_docker_group,
    stop_container,
    copy_template,
    generate_env,
    install_bitwarden,
    ensure_network,
    start_container,
    backup_data,
    setup_usb_secrets,
    apply_override,   # ← 신규 추가
)
from utils.generate_certificates import generate_certificates

load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT")
BASE_DIR = os.getenv('BASE_DIR', '/opt/ai4infra')
app = typer.Typer(help="AI4INFRA 서비스 관리")
SERVICES = ('postgres', 'vault', 'elk', 'ldap', 'bitwarden') # 튜플로 선언하어 변경 방지


@app.command()
def install(
    service: str = typer.Argument("all", help="설치할 서비스 이름"),
    reset: bool = typer.Option(False, "--reset", help="기존 데이터/컨테이너 삭제 후 완전 재설치 (개발용)")
):
    services = list(SERVICES) if service == "all" else [service]

    # Bitwarden 사용자 생성
    if "bitwarden" in services:
        create_user("bitwarden")
        add_docker_group("bitwarden")

    # Vault USB secrets 준비
    if "vault" in services:
        setup_usb_secrets()

    for svc in services:
        print("####################################################################################")
        service_dir = f"{BASE_DIR}/{svc}"

        # 1) 컨테이너 중지
        stop_container("bitwarden" if svc == "bitwarden" else f"ai4infra-{svc}")

        # 2) reset 시 → 디렉터리 삭제
        if reset:
            log_info(f"[install] --reset 옵션: {svc} 기존 데이터 삭제 진행")
            subprocess.run(
                ["sudo", "rm", "-rf", service_dir],
                capture_output=True, text=True
            )
            log_info(f"[install] {service_dir} → 기존데이터 삭제 완료")

        # 3) reset=False → 백업
        else:
            backup_data(svc)

        # 4) 템플릿 복사
        copy_template(svc)

        # 5) 서비스별 추가 작업 (설치/인증서/override 등)
        if svc == "vault":
            generate_certificates(["vault"], overwrite=False)

        if svc == "bitwarden":
            ok = install_bitwarden()
            if not ok:
                log_error("[install] Bitwarden 설치 실패 → skip container start")
                continue
            apply_override("bitwarden")

        # 6) 환경파일(.env) 생성 — 서비스를 모두 준비한 뒤
        env_path = generate_env(svc)
        if not env_path:
            log_info(f"[install] {svc}: .env 생성 생략 또는 환경변수 없음")

        # 7) 컨테이너 시작
        start_container(svc)

        log_info(f"[install] {svc} 설치 완료")

  
@app.command()
def backup(service: str = typer.Argument(..., help="백업할 서비스 (postgres, all)")):
    """서비스 데이터 백업"""
    services = list(SERVICES) if service == "all" else [service]
    
    backup_files = []
    for svc in services:
        if svc in SERVICES:
            backup_file = backup_data(svc)
            if backup_file:
                backup_files.append(backup_file)
    
    if backup_files:
        log_info(f"[backup] {len(backup_files)}개 백업 완료")
    else:
        log_info("[backup] 백업할 데이터가 없습니다")

@app.command()
def restore(
    service: str = typer.Argument(..., help="복원할 서비스"),
    backup_dir: str = typer.Argument(..., help="백업 디렉터리 경로")
):
    """
    AI4INFRA 서비스 복원 (백업 시점의 권한/소유권 그대로 복구)

    절차:
      1) 백업 디렉터리 존재 확인
      2) 컨테이너 중지
      3) rsync -a --numeric-ids 로 완전 복원
      4) generate_env() 재생성
      5) start_container()
    """
    log_info(f"[restore] {service} 복원 시작: {backup_dir}")

    # 1) 백업 디렉터리 확인
    if not os.path.exists(backup_dir):
        log_error(f"[restore] 백업 디렉터리 없음: {backup_dir}")
        return

    # 2) 컨테이너 중지
    stop_container("bitwarden" if service == "bitwarden" else f"ai4infra-{service}")

    # 3) rsync로 백업 그대로 복원 (권한/소유자 포함)
    service_dir = f"{BASE_DIR}/{service}"
    cmd = ['sudo', 'rsync', '-a', '--numeric-ids', f"{backup_dir}/", f"{service_dir}/"]
    subprocess.run(cmd, check=True)
    log_info(f"[restore] 복원 완료 (권한 포함 그대로): {backup_dir} → {service_dir}")

    # 4) 환경파일(.env) 재생성
    env_path = generate_env(service)
    if env_path:
        log_info(f"[restore] {service}: .env 재생성 완료 → {env_path}")
    else:
        log_info(f"[restore] {service}: .env 생성 생략")

    # 5) 컨테이너 재시작
    start_container(service)
    log_info(f"[restore] {service} 복원 완료")


@app.command()
def cert(
    services: List[str] = typer.Argument(help="인증서를 생성할 서비스 목록"),
    days: int = typer.Option(730, "--days", "-d", help="인증서 유효기간 (일)"),
    overwrite: bool = typer.Option(False, "--overwrite", "-f", 
                                 help="기존 인증서 덮어쓰기")
):
    """SSL 인증서 생성 - Vault 프로덕션 모드용"""
    log_info(f"[cert] {services} 인증서 생성 시작")
    
    # all이면 모든 서비스
    if services == ["all"]:
        services = SERVICES
    
    success = generate_certificates(services, days, overwrite)
    
    if success:
        log_info(f"[cert] {len(services)}개 서비스 인증서 생성 완료")
    else:
        log_error("[cert] 일부 인증서 생성 실패")

@app.command()
def init_vault():
    """Vault 프로덕션 모드 초기화 - 첫 실행 시에만"""
    log_info("[init_vault] Vault 초기화 시작")

    # 1) Vault 컨테이너 실행 확인
    result = subprocess.run(
        ['sudo', 'docker', 'ps', '--filter', 'name=ai4infra-vault', '--format', '{{.Names}}'],
        capture_output=True, text=True
    )

    if 'ai4infra-vault' not in result.stdout:
        log_error("[init_vault] Vault 컨테이너가 실행되지 않았습니다. 먼저 'ai4infra install vault' 실행하십시오.")
        return

    # 2) 초기화 안내 메시지
    print("\n===================================================================")
    print(" Vault 초기화를 진행합니다.")
    print(" !!! 아래 출력은 단 한 번만 표시되므로 반드시 저장하십시오 !!!")
    print("===================================================================\n")

    print("보관 권장사항:")
    print(" - 출력되는 JSON 전체를 Bitwarden/KeePass 등 암호화 저장소에 보관")
    print(" - 로컬 PC 텍스트 파일, 메모장, 이메일 저장 금지")
    print(" - 가능하면 인쇄하여 금고 등에 분산 보관\n")

    print("-------------------------------------------------------------------")
    print(" Vault operator init 결과(JSON)가 곧 화면에 그대로 출력됩니다.")
    print("-------------------------------------------------------------------\n")

    # 3) Vault init 실행 (출력을 캡처하지 않음 → 그대로 사용자 터미널로 출력됨)
    init_cmd = [
        'sudo', 'docker', 'exec', '-i', 'ai4infra-vault',
        'vault', 'operator', 'init',
        '-key-shares=5',
        '-key-threshold=3',
        '-format=json'
    ]

    try:
        # stdout/stderr을 캡처하지 않으므로 Vault의 출력이 그대로 화면에 표시됨
        subprocess.run(init_cmd, check=True)

        print("\n-------------------------------------------------------------------")
        print(" 초기화가 정상적으로 완료되었습니다.")
        print(" 다음 단계:")
        print("   ai4infra unseal-vault")
        print("-------------------------------------------------------------------\n")

    except subprocess.CalledProcessError as e:
        if e.stderr and "Vault is already initialized" in e.stderr:
            log_info("[init_vault] Vault는 이미 초기화되어 있습니다.")
        else:
            log_error("[init_vault] 초기화 실패")
            if e.stderr:
                print(e.stderr)


@app.command()
def unseal_vault():
    """Vault 언씰 - 사용자가 직접 터미널에서 vault operator unseal 명령을 실행하도록 안내합니다."""
    log_info("[unseal_vault] Vault 언씰 절차 시작")

    status_cmd = [
        'sudo', 'docker', 'exec', 'ai4infra-vault',
        'vault', 'status', '-format=json'
    ]

    # 1) Vault 상태 확인
    try:
        result = subprocess.run(status_cmd, capture_output=True, text=True, check=True)
        import json
        status_json = json.loads(result.stdout)
        initialized = status_json.get("initialized", False)
        sealed = status_json.get("sealed", True)
        threshold = status_json.get("t", status_json.get("threshold", 3))
    except Exception:
        log_info("[unseal_vault] Vault 상태 확인 실패: sealed 상태일 수 있습니다.")
        initialized = True
        sealed = True
        threshold = 3
        status_json = {"sealed": True}

    # 2) 초기화 여부 확인
    if not initialized:
        log_error("[unseal_vault] Vault가 초기화되지 않았습니다. 먼저 init-vault 실행하십시오.")
        return

    # 3) 언실 여부 확인
    if not sealed:
        log_info("[unseal_vault] Vault는 이미 언실되어 있습니다.")
        print("Vault UI: https://localhost:8200")
        return

    print("\n===================================================================")
    print(" Vault 언실(Unseal) 절차 안내 (수동 방식)")
    print("===================================================================\n")

    print("Vault는 보안상의 이유로 sealed 상태로 시작합니다.")
    print(f"이 Vault는 총 {threshold}개의 Unseal Key 중 최소 {threshold}개가 필요합니다.\n")

    print("이제 사용자가 직접 vault operator unseal 명령을 실행해야 합니다.")
    print("각 키 입력은 반드시 사람이 직접 수행해야 하며, 자동화할 수 없습니다.\n")

    print("-------------------------------------------------------------------")
    print("  아래 명령을 터미널에 직접 입력하십시오.")
    print("-------------------------------------------------------------------\n")

    print("1) Vault 컨테이너 내부로 들어가기:")
    print("   sudo docker exec -it ai4infra-vault /bin/sh\n")

    print("2) Vault 언실 명령 실행:")
    print("   vault operator unseal\n")
    print("   → Unseal Key #1 입력")
    print("   vault operator unseal\n")
    print("   → Unseal Key #2 입력")
    print("   vault operator unseal\n")
    print("   → Unseal Key #3 입력\n")

    print("3) sealed=false 상태가 되면 언실이 완료됩니다.")
    print("   vault status\n")

    print("\n-------------------------------------------------------------------")
    print(" Vault 웹 UI:")
    print("   https://localhost:8200")
    print("-------------------------------------------------------------------\n")

    log_info("[unseal_vault] 사용자에게 Vault 언실 명령 실행 안내 완료")





if __name__ == "__main__":
    try:
        app()
    except Exception as e:
        log_error(str(e))
        sys.exit(1)