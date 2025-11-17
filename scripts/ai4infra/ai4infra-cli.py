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
from utils.container_manager import create_user, add_sudoer, stop_container, copy_template, generate_env, install_bitwarden, ensure_network, start_container, backup_data, setup_usb_secrets
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

    # Bitwarden 사용자 생성 (bitwarden 서비스 설치 시에만)
    if 'bitwarden' in services:
        create_user('bitwarden')
        add_sudoer('bitwarden', 'bitwarden ALL=(ALL) NOPASSWD: /usr/bin/docker, /opt/ai4infra/bitwarden/bitwarden.sh')
    
    # USB 비밀번호 파일 준비 (Vault 설치 시에만)
    if 'vault' in services:
        setup_usb_secrets()
    
    for svc in services:
        print("####################################################################################")
        service_dir = f"{BASE_DIR}/{svc}"

        # 1) 컨테이너 중지
        stop_container(f"ai4infra-{svc}" if svc != "bitwarden" else "bitwarden")

        # 2) reset 옵션인 경우 → 컨테이너 + 데이터 제거
        if reset:
            log_info(f"[install] --reset 옵션 감지: {svc} 기존 데이터 제거")

            # 1) 서비스 루트 폴더 전체 삭제
            #    예: /opt/ai4infra/vault → 전체 삭제
            subprocess.run(
                ["sudo", "rm", "-rf", service_dir],
                capture_output=True,
                text=True
            )

            log_info(f"[install] 삭제 완료 → {service_dir}")


        # 3) 기존 데이터 백업 (reset=False 인 경우만)
        else:
            backup_data(svc)  # 서비스 전체 백업 (통일)

        # 4) 템플릿 복사 (멱등)
        copy_template(svc)

        # 5) 환경파일 생성
        generate_env(svc)

        # 6) Vault 인증서 생성 (reset 여부와 무관)
        if svc == "vault":
            generate_certificates(["vault"], overwrite=False)

        # 7) Bitwarden 설치
        if svc == "bitwarden":
            install_bitwarden()


        # 8) 컨테이너 시작
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
    """서비스 데이터 복원 (전체 복원)
    
    동작:
    1. 백업 디렉터리 존재 확인
    2. 컨테이너 중지
    3. 백업 디렉터리 내용을 서비스 디렉터리로 복원 (덮어쓰기)
       - 백업에 포함된 파일만 덮어씀 (file/, config/, certs/)
       - docker-compose.yml, .env는 백업에 없으므로 유지됨
    4. 소유권 및 권한 재조정
       - bitwarden: bitwarden:bitwarden 소유, MSSQL 데이터 파일 660 권한
       - 기타: 원본 소유권 유지
    5. 컨테이너 시작
    
    사용 예:
      ai4infra restore vault /opt/ai4infra/backups/vault/vault_20251116_153000
    """
    log_info(f"[restore] {service} 복원 시작: {backup_dir}")

    # 1. 백업 디렉터리 존재 확인
    if not os.path.exists(backup_dir):
        log_error(f"[restore] 백업 디렉터리 없음: {backup_dir}")
        return

    # 2. 컨테이너 중지
    stop_container(f"ai4infra-{service}" if service != "bitwarden" else "bitwarden")

    # 3. 백업 디렉터리에서 복원 (덮어쓰기)
    # 주의: docker-compose.yml, .env는 백업에 없으므로 기존 파일 유지됨
    service_dir = f"{BASE_DIR}/{service}"
    cmd = ['sudo', 'rsync', '-a', f"{backup_dir}/", f"{service_dir}/"]
    subprocess.run(cmd, check=True)
    log_info(f"[restore] 백업 복원 완료 (덮어쓰기): {backup_dir} → {service_dir}")

    # 4. 소유권 및 권한 재조정 (비트워든 특화)
    if service == 'bitwarden':
        try:
            # 4-1. 전체 bwdata는 우선적으로 bitwarden 사용자 소유로 설정
            subprocess.run(['sudo', 'chown', '-R', 'bitwarden:bitwarden', service_dir], check=True)
            log_info(f"[restore] 소유권 설정: bitwarden:bitwarden (전체)")

            # 4-2. MSSQL 데이터 파일 경로가 있으면 파일 권한을 보정
            mssql_data_dir = f"{service_dir}/bwdata/mssql/data"
            if os.path.exists(mssql_data_dir):
                # 4-2a. .mdf/.ldf 파일에 660 권한 부여 (소유자+그룹 읽기/쓰기)
                subprocess.run([
                    'sudo', 'find', mssql_data_dir, '-type', 'f',
                    '(', '-name', '*.mdf', '-o', '-name', '*.ldf', ')',
                    '-exec', 'chmod', '660', '{}', '+'
                ], check=True, capture_output=True, text=True)
                log_info(f"[restore] MSSQL 데이터 파일 권한 수정: 660 (rw-rw----)")

                # 4-2b. 만약 docker override에 의해 mssql이 비트워든 사용자(1001)로 실행되지
                # 않는다면(예: root로 실행), 데이터 파일 소유자를 root로 변경하는 옵션을
                # 적용할 수 있도록 검사합니다. 우선 docker-compose override 파일을 확인.
                override_path = f"{service_dir}/bwdata/docker/docker-compose.override.yml"
                run_as_1001 = False
                if os.path.exists(override_path):
                    try:
                        with open(override_path, 'r', encoding='utf-8') as ox:
                            ov_text = ox.read()
                        # 간단 탐색: mssql 섹션에 user: 1001이 포함되어 있는지 확인
                        if 'mssql' in ov_text and '1001' in ov_text:
                            run_as_1001 = True
                    except Exception:
                        run_as_1001 = False

                # 4-2c. override에 따라 소유권 조정
                if run_as_1001:
                    subprocess.run(['sudo', 'chown', '-R', 'bitwarden:bitwarden', mssql_data_dir], check=True)
                    log_info(f"[restore] MSSQL 데이터 소유자: bitwarden:bitwarden (override detected)")
                else:
                    # 기본적으로 MSSQL 컨테이너는 root로 동작하므로 root 소유로 변경
                    subprocess.run(['sudo', 'chown', '-R', 'root:root', mssql_data_dir], check=True)
                    log_info(f"[restore] MSSQL 데이터 소유자: root:root (default)")

        except subprocess.CalledProcessError as e:
            log_error(f"[restore] 권한/소유권 재조정 실패: {e.stderr}")
    else:
        # PostgreSQL, Vault 등은 원본 소유권을 그대로 두고 넘어갑니다
        log_info(f"[restore] 소유권 유지 (원본 그대로) for {service}")

    # 5. 컨테이너 시작
    start_container(service)

    # 6. (선택) 컨테이너 건강 상태 확인 안내 로그
    log_info(f"[restore] {service} 복원 완료 - 컨테이너가 정상인지 'docker ps' 및 로그를 확인하세요")

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