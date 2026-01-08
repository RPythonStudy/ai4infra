#!/usr/bin/env python3

# Standard library imports
import os
import re
import subprocess
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List

# Third-party imports
import typer
from dotenv import load_dotenv

# Local imports
from common.logger import log_debug, log_error, log_info

# user manager


# base manager
from utils.container.base_manager import stop_container
from utils.container.base_manager import copy_template
from utils.container.base_manager import start_container
from utils.container.base_manager import ensure_network

# backup & restore
from utils.container.backup_manager import backup_data
from utils.container.backup_manager import restore_data

# bitwarden installer


# USB secrets
from utils.container.usb_secrets import setup_usb_secrets

# healthcheck modules
from utils.container.healthcheck import check_container
from utils.container.health_vault import check_vault
from utils.container.health_postgres import check_postgres

# service discovery
from utils.container.installer import discover_services, is_hot_backup_service
from common.load_config import load_config

#
from utils.container.env_manager import generate_env
# -------------------------------------------------------------
# 인증서 모듈 (기존 유지, 한 줄씩)
# -------------------------------------------------------------
from utils.certs_manager import generate_root_ca_if_needed
from utils.certs_manager import create_service_certificate
from utils.certs_manager import apply_service_permissions
from utils.certs_manager import install_root_ca_windows


load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT")
BASE_DIR = os.getenv('BASE_DIR', '/opt/ai4infra')
app = typer.Typer(help="AI4INFRA 서비스 관리")


@app.command()
def generate_rootca():
    generate_root_ca_if_needed()

@app.command()

    
@app.command()
def install(
    service: str = typer.Argument("all", help="설치할 서비스 이름"),
    reset: bool = typer.Option(False, "--reset", help="기존 데이터/컨테이너 삭제 후 완전 재설치 (개발용)")
):
    
    # discover_services() 함수로 서비스 목록을 가져옴
    services = list(discover_services()) if service == "all" else [service]
    for svc in services:
        service_dir = f"{BASE_DIR}/{svc}"

        # 1) 컨테이너 중지
        stop_container(f"ai4infra-{svc}")

        # 2) 데이터 처리
        if reset:
            log_info(f"[install] --reset 모드: {svc} 서비스폴더 삭제진행")
            subprocess.run(["sudo", "rm", "-rf", service_dir], capture_output=True, text=True)
            log_info(f"[install] {service_dir} 삭제 완료")

        else:
            # 멱등성 모드
            log_info(f"[install] 옵션 없음 = 멱등성 모드: {svc} 기존 데이터∙설정 유지")

        # 3) 템플릿 복사
        copy_template(svc)

        # 4) 서비스별 권한 설정 (복사 직후 실행)
        apply_service_permissions(svc)

        # 5) 서비스별 인증서 생성 (Bitwarden 설치 완료 후)
        create_service_certificate(service=svc, san=None)

        # 6) 환경파일 생성 (.env)
        env_path = generate_env(svc)
        if not env_path:
            log_info(f"[install] {svc}: .env 생성 생략")

        # 7) 컨테이너 시작
        start_container(svc)

        # -----------------------------
        # 설치 후 자동 점검 단계 추가
        # -----------------------------
        if svc == "vault":
            check_container("vault", check_vault)
        elif svc == "postgres":
            check_container("postgres", check_postgres)
        else:
            check_container(svc)  # 기본 점검

            # ai4infra-cli.py 내부 install() 루프 중
        if svc == "postgres":
            log_info("[install] PostgreSQL 1단계 설치 및 점검 완료")

            # 1) 컨테이너 중지
            stop_container("ai4infra-postgres")
            log_info("[install] PostgreSQL 컨테이너 중지 완료 (TLS 적용 준비)")

            # 2) override 파일 복사
            override_src = f"{PROJECT_ROOT}/templates/postgres/docker-compose.override.yml"
            override_dst = f"{BASE_DIR}/postgres/docker-compose.override.yml"

            if Path(override_src).exists():
                subprocess.run(
                    ["sudo", "cp", "-a", override_src, override_dst],
                    check=True
                )
                log_info(f"[install] TLS override 적용 완료 → {override_dst}")
            else:
                log_error("[install] TLS override 템플릿이 없습니다")
                continue

            # 2-1) TLS 인증서 권한 재설정
            apply_service_permissions("postgres")

            # 3) TLS 모드 재기동
            start_container("postgres")
            log_info("[install] PostgreSQL TLS 모드 재가동 완료")

            # 4) TLS 기반 PostgreSQL 점검
            check_container("postgres", check_postgres)
            log_info("[install] PostgreSQL 2단계(TLS) 검증 완료")
        

        log_info(f"[install] {svc} 설치 및 점검 완료")

@app.command()
def backup(service: str = typer.Argument(..., help="백업할 서비스 (postgres, all)")):
    """서비스 데이터 백업 (컨테이너 중지 → 백업 → 재시작)"""

    # install()과 동일한 서비스 자동 탐색 방식
    services = list(discover_services()) if service == "all" else [service]

    backup_files = []

    for svc in services:
        
        # [Policy] Cold Backup Enforcement (GEMINI.md 참조)
        # Hot/Cold 구분 없이 무조건 중지하여 정합성 보장
        stop_container(f"ai4infra-{svc}")

        try:
            # 2) 백업 수행
            backup_file = backup_data(svc)
            if backup_file:
                backup_files.append(backup_file)
        finally:
            # 3) 반드시 재시작 (백업 성공/실패 여부와 관계없이)
            start_container(svc)

    if backup_files:
        log_info(f"[backup] {len(backup_files)}개 백업 완료")
    else:
        log_info("[backup] 백업할 데이터가 없습니다")

@app.command()
def restore(
    service: str = typer.Argument(..., help="복원할 서비스"),
    backup_dir: str = typer.Argument(None, help="백업 디렉터리 경로 (생략 시 최신 백업 자동 선택)")
):
    """
    AI4INFRA 서비스 복원 (백업 시점의 권한/소유권 그대로 복구)

    절차:
      1) 백업 디렉터리 확인 (미지정 시 최신 백업 자동 선택)
      2) 컨테이너 중지
      3) rsync -a --numeric-ids 로 완전 복원
      4) generate_env() 재생성
      5) start_container()
    """
    
    # 1) 백업 디렉터리 결정
    if backup_dir is None:
        # 최신 백업 자동 선택
        backups_root = f"{BASE_DIR}/backups/{service}"
        if not os.path.exists(backups_root):
            log_error(f"[restore] 백업 디렉터리 없음: {backups_root}")
            return
        
        # 서비스명_타임스탬프 형식의 디렉터리 찾기
        backup_dirs = [
            d for d in os.listdir(backups_root)
            if os.path.isdir(os.path.join(backups_root, d)) and d.startswith(f"{service}_")
        ]
        
        if not backup_dirs:
            log_error(f"[restore] {service} 백업 없음: {backups_root}")
            return
        
        # 타임스탬프 기준 정렬 (최신순)
        backup_dirs.sort(reverse=True)
        backup_dir = os.path.join(backups_root, backup_dirs[0])
        log_info(f"[restore] 최신 백업 자동 선택: {backup_dir}")
    
    log_info(f"[restore] {service} 복원 시작: {backup_dir}")
    
    # 2) 백업 디렉터리 존재 확인
    if not os.path.exists(backup_dir):
        log_error(f"[restore] 백업 디렉터리 없음: {backup_dir}")
        return

    # 3) 컨테이너 중지
    stop_container(f"ai4infra-{service}")

    # 4) rsync로 백업 그대로 복원 (권한/소유자 포함)
    service_dir = f"{BASE_DIR}/{service}"
    cmd = ['sudo', 'rsync', '-a', '--numeric-ids', f"{backup_dir}/", f"{service_dir}/"]
    subprocess.run(cmd, check=True)
    log_info(f"[restore] 복원 완료 (권한 포함 그대로): {backup_dir} → {service_dir}")

    # 5) 환경파일(.env) 재생성
    env_path = generate_env(service)
    if env_path:
        log_info(f"[restore] {service}: .env 재생성 완료 → {env_path}")
    else:
        log_info(f"[restore] {service}: .env 생성 생략")

    # [Safe Guard] docker-compose.yml 누락 감지 (예: 오래된 백업 복원 시)
    service_dir = f"{BASE_DIR}/{service}"
    if not os.path.exists(f"{service_dir}/docker-compose.yml"):
        log_info(f"[restore] docker-compose.yml 누락 감지 → 템플릿 복사 수행")
        copy_template(service)
        # 템플릿 복사 후 권한 재설정
        apply_service_permissions(service)

    # 6) 컨테이너 재시작
    start_container(service)
    log_info(f"[restore] {service} 복원 완료")

    # -----------------------------
    # 설치 후 자동 점검 단계 추가
    # -----------------------------
    if service == "vault":
        check_container("vault", check_vault)
    elif service == "postgres":
        check_container("postgres", check_postgres)
    else:
        check_container(service)  # 기본 점검

    log_info(f"[install] {service} 설치 및 점검 완료")

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

    # 3) Vault init 실행
    # 3) Vault init 실행
    init_cmd = [
        'sudo', 'docker', 'exec', '-i', 
        '-e', 'VAULT_ADDR=https://127.0.0.1:8200',  # [Fix] TLS 인증서 IP 불일치 해결
        'ai4infra-vault',
        'vault', 'operator', 'init',
        '-key-shares=5',
        '-key-threshold=3',
        '-format=json'
    ]

    try:
        # JSON 캡처
        result = subprocess.run(init_cmd, capture_output=True, text=True, check=True)
        init_json = result.stdout
        
        # [Dev Simulation] Mock USB 저장
        mock_usb_dir = f"{PROJECT_ROOT}/mock_usb"
        os.makedirs(mock_usb_dir, exist_ok=True)
        key_file_path = f"{mock_usb_dir}/vault_keys.json"
        
        with open(key_file_path, "w") as f:
            f.write(init_json)
            
        # 사용자 출력
        print("\n-------------------------------------------------------------------")
        print(" 초기화가 정상적으로 완료되었습니다.")
        print(f" [SIMULATION] Key가 가상 USB에 저장되었습니다: {key_file_path}")
        print(" 이 파일은 .gitignore에 등록되어 버전 관리에서 제외됩니다.")
        print(" unseal-vault 실행 시 자동으로 감지되어 처리됩니다.")
        print("-------------------------------------------------------------------")
        
        # 보안상 화면 출력은 최소화 (필요시 주석 해제)
        # print("\n--- Init Output (JSON) ---\n")
        # print(init_json)
        # print("\n--------------------------\n")
        
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
        'sudo', 'docker', 'exec', 
        '-e', 'VAULT_ADDR=https://127.0.0.1:8200',  # [Fix] TLS 인증서 IP 불일치 해결
        'ai4infra-vault',
        'vault', 'status', '-format=json'
    ]

    # 1) Vault 상태 확인
    try:
        result = subprocess.run(status_cmd, capture_output=True, text=True, check=True)
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

    # [Dev Simulation] Mock USB 자동 언실 시도
    mock_usb_key_path = f"{PROJECT_ROOT}/mock_usb/vault_keys.json"
    
    if os.path.exists(mock_usb_key_path):
        log_info(f"[unseal_vault] 가상 USB 키 감지됨: {mock_usb_key_path}")
        try:
            with open(mock_usb_key_path, "r") as f:
                keys_data = json.load(f)
                unseal_keys = keys_data.get("unseal_keys_b64", [])
            
            if not unseal_keys:
                log_error("[unseal_vault] 키 파일에 unseal_keys_b64가 없습니다.")
            else:
                log_info(f"[unseal_vault] 자동 언실 시작 (Threshold: {threshold})")
                
                success_count = 0
                for i, key in enumerate(unseal_keys[:threshold]):
                    log_info(f"[unseal_vault] Key #{i+1} 입력 중...")
                    cmd = [
                        'sudo', 'docker', 'exec', 
                        '-e', 'VAULT_ADDR=https://127.0.0.1:8200',  # [Fix] TLS 인증서 IP 불일치 해결
                        'ai4infra-vault',
                        'vault', 'operator', 'unseal', key
                    ]
                    res = subprocess.run(cmd, capture_output=True, text=True)
                    if res.returncode == 0:
                        success_count += 1
                    else:
                        log_error(f"[unseal_vault] Key #{i+1} 실패: {res.stderr}")
                
                if success_count >= threshold:
                    log_info("[unseal_vault] 자동 언실 성공!")
                    print("Vault UI: https://localhost:8200")
                    return
                else:
                    log_error(f"[unseal_vault] 자동 언실 실패 (성공: {success_count}/{threshold})")
                    
        except Exception as e:
            log_error(f"[unseal_vault] 키 파일 읽기 오류: {e}")
            
    # -------------------------------------------------------------
    # 수동 모드 (USB 없음)
    # -------------------------------------------------------------
    print("\n===================================================================")
    print(" Vault 언실(Unseal) 절차 안내 (수동 방식)")
    print("===================================================================\n")
    print(" * 가상 USB 키 파일(mock_usb/vault_keys.json)을 찾을 수 없습니다.\n")

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

    log_info("[unseal_vault] 사용자에게 Vault 언실 명령 실행 안내 (수동)")

@app.command()
def install_rootca_windows():
    """
    Windows에 Root CA 자동 설치 (WSL2 환경 전용)
    """
    
    install_root_ca_windows()

if __name__ == "__main__":
    try:
        app()
    except Exception as e:
        log_error(str(e))
        sys.exit(1)