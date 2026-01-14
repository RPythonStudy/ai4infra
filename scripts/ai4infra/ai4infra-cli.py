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
from common.logger import log_debug, log_error, log_info, log_warn

# base manager
from utils.container.base_manager import stop_container
from utils.container.base_manager import copy_template
from utils.container.base_manager import start_container
from utils.container.base_manager import ensure_network

# backup & restore
from utils.container.backup_manager import backup_data
from utils.container.backup_manager import restore_data

# USB secrets
from utils.container.usb_secrets import setup_usb_secrets

# healthcheck modules
from utils.container.healthcheck import check_container
from utils.container.health_vault import check_vault
from utils.container.health_postgres import check_postgres

# service discovery
from utils.container.installer import discover_services, is_hot_backup_service
from common.load_config import load_config

# env manager
from utils.container.env_manager import generate_env
from utils.container.nginx_manager import setup_nginx_for_service
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

def _ensure_postgres_db(db_name="keycloak", db_user="keycloak", env_password_key="KEYCLOAK_DB_PASSWORD"):
    """
    운영 중인 Postgres에 DB/User가 없으면 자동 생성.
    (비밀번호는 .env의 env_password_key 참조)
    """
    log_info(f"[_ensure_postgres_db] {db_name} 데이터베이스 확인 중...")
    
    # 1. Postgres 컨테이너 실행 여부 확인
    if not check_container("postgres"):
        log_error("[_ensure_postgres_db] Postgres 컨테이너가 실행 중이지 않습니다.")
        return

    # 2. DB 존재 여부 확인
    check_db_cmd = [
        "docker", "exec", "ai4infra-postgres",
        "psql", "-U", "postgres", "-lqt"
    ]
    try:
        res = subprocess.run(check_db_cmd, capture_output=True, text=True, check=True)
        if f" {db_name} " in res.stdout:
            log_info(f"[_ensure_postgres_db] {db_name} DB가 이미 존재합니다.")
            return
    except subprocess.CalledProcessError:
        log_error("[_ensure_postgres_db] DB 목록 조회 실패")
        return

    # 3. DB 및 User 생성
    log_info(f"[_ensure_postgres_db] {db_name} DB 생성 시작...")
    pw = os.getenv(env_password_key, db_user)
    
    # 3-1. User 생성 (이미 존재할 수 있음 -> 에러 무시)
    cmd_user = [
        "docker", "exec", "ai4infra-postgres",
        "psql", "-U", "postgres", "-c", f"CREATE USER {db_user} WITH PASSWORD '{pw}';"
    ]
    try:
        subprocess.run(cmd_user, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        # 이미 존재하는 경우 등은 경고 후 진행
        log_warn(f"[_ensure_postgres_db] 사용자({db_user}) 생성 스킵 (이미 존재 가능성)")

    # 3-2. DB 생성 및 권한 부여
    create_cmds = [
        f"CREATE DATABASE {db_name};",
        f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {db_user};",
        f"ALTER DATABASE {db_name} OWNER TO {db_user};"
    ]
    
    for sql in create_cmds:
        cmd = [
            "docker", "exec", "ai4infra-postgres",
            "psql", "-U", "postgres", "-c", sql
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            # DB 이미 존재함은 위에서 체크했으므로, 여기서 에러나면 진짜 문제임.
            # 단, CREATE DATABASE는 Transaction Block 안에서 실행 불가라 가끔 까다로움.
            stderr = e.stderr.decode() if e.stderr else ""
            if "already exists" in stderr:
                 log_warn(f"[_ensure_postgres_db] {db_name} 이미 존재 (진행)")
                 continue
            
            log_error(f"[_ensure_postgres_db] SQL 실행 실패: {sql}... ({stderr})")
            return

    log_info(f"[_ensure_postgres_db] {db_name} DB 및 User 생성 완료")


@app.command()
def install(
    service: str = typer.Argument("all", help="설치할 서비스 이름"),
    reset: bool = typer.Option(False, "--reset", help="기존 데이터/컨테이너 삭제 후 완전 재설치 (개발용)")
):
    
    # discover_services() 함수로 서비스 목록을 가져옴
    
    # [Design Strategy] Core vs Add-on Separation
    # Core services must be installed in strict dependency order.
    # Add-ons can be installed afterwards.
    CORE_ORDER = ["postgres", "vault", "ldap", "keycloak", "nginx"]
    
    if service == "all":
        discovered = set(discover_services())
        
        # 1. Filter Core services present in discovery
        core_to_install = [s for s in CORE_ORDER if s in discovered]
        
        # 2. Add-ons are everything else
        addons_to_install = [s for s in discovered if s not in CORE_ORDER]
        
        # 3. Final ordered list
        services = core_to_install + addons_to_install
        
        log_info(f"[install|all] Installation Order: {services}")
    else:
        services = [service]
        
    for svc in services:
        service_dir = f"{BASE_DIR}/{svc}"

        # [Keycloak 전처리] DB 준비
        if svc == "keycloak":
             _ensure_postgres_db(db_name="keycloak", db_user="keycloak", env_password_key="KEYCLOAK_DB_PASSWORD")
        # [Orthanc Family 전처리] DB 준비 (orthanc, orthanc-mock, orthanc-research...)
        elif svc.startswith("orthanc"):
             # 예: "orthanc-mock" -> "orthanc_mock"
             db_name = svc.replace("-", "_")
             # User는 공통 "orthanc" 사용
             _ensure_postgres_db(db_name=db_name, db_user="orthanc", env_password_key="ORTHANC_DB_PASSWORD")

        # 1) 컨테이너 중지
        stop_container(f"ai4infra-{svc}")

        # 2) 데이터 처리
        if reset:
            log_info(f"[install] --reset 모드: {svc} 서비스폴더 삭제진행")
            subprocess.run(["rm", "-rf", service_dir], capture_output=True, text=True)
            log_info(f"[install] {service_dir} 삭제 완료")

        else:
            # 멱등성 모드
            log_info(f"[install] 옵션 없음 = 멱등성 모드: {svc} 기존 데이터∙설정 유지")

        # 3) 템플릿 복사
        copy_template(svc)

        # 4) 서비스별 권한 설정 (복사 직후 실행)
        apply_service_permissions(svc)

        # 5) 서비스별 인증서 생성
        create_service_certificate(service=svc, san=None)

        # 6) 환경파일 생성 (.env)
        env_path = generate_env(svc)
        if not env_path:
            log_info(f"[install] {svc}: .env 생성 생략")

        # 7) 컨테이너 시작
        start_container(svc)

        # [Post-Install] Nginx 통합 (인증서, 설정, 리로드)
        setup_nginx_for_service(svc)

        # -----------------------------
        # 설치 후 자동 점검 단계 추가
        # -----------------------------
        if svc == "vault":
            # [Auto-Unseal Integration] 설치 직후 언실 시도
            _execute_unseal_vault(interactive=False)
            check_container("vault", check_vault)
        elif svc == "postgres":
            check_container("postgres", check_postgres)
        elif svc == "elk":
            check_container("elasticsearch")
            check_container("kibana")
            check_container("logstash")
            check_container("filebeat")
        elif svc == "keycloak":
             check_container("keycloak")
        elif svc == "orthanc":
             check_container("orthanc")
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
                    ["cp", "-a", override_src, override_dst],
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
def backup(
    service: str = typer.Argument(..., help="백업할 서비스 (postgres, all)"),
    cold: bool = typer.Option(False, "--cold", help="콜드 백업 모드 (컨테이너 중지 후 백업)")
):
    """
    서비스 데이터 백업
    - 기본: Hot Backup (운영 중 백업, 중단 없음) -> Cron/Daily용
    - --cold: Cold Backup (중지 후 백업) -> 점검/마이그레이션용
    """

    services = list(discover_services()) if service == "all" else [service]
    backup_files = []

    for svc in services:
        log_info(f"[backup] {svc} 백업 시작 (Mode: {'COLD' if cold else 'HOT'})")

        # Cold Backup Mode
        if cold:
            stop_container(f"ai4infra-{svc}")
            try:
                backup_file = backup_data(svc)
                if backup_file:
                    backup_files.append(backup_file)
            finally:
                # Cold Backup은 반드시 재시작
                start_container(svc)
        
        # Hot Backup Mode (Default)
        else:
            # 컨테이너가 실행 중이어야 함
            # backup_data 내부에서 docker exec 사용
            backup_file = backup_data(svc)
            if backup_file:
                backup_files.append(backup_file)

    if backup_files:
        log_info(f"[backup] {len(backup_files)}개 백업 완료")
    else:
        log_warn("[backup] 백업된 파일이 없습니다 (실패 또는 데이터 없음)")

@app.command()
@app.command()
def restore(
    service: str = typer.Argument(..., help="복원할 서비스"),
    backup_file: str = typer.Argument(None, help="복원할 백업 파일 경로 (.gpg) (생략 시 최신 백업 자동 선택)")
):
    """
    AI4INFRA 서비스 복원
    - 암호화된 백업 파일(.gpg)을 복호화하여 복원합니다.
    - Postgres/Vault: 서비스가 켜진 상태에서 API/CLI로 데이터 주입
    - 기타: 서비스 중지 후 데이터 파일 덮어쓰기
    """
    
    # 1. 백업 파일 결정
    if backup_file is None:
        backups_root = f"{BASE_DIR}/backups/{service}"
        if not os.path.exists(backups_root):
            log_error(f"[restore] 백업 디렉터리 없음: {backups_root}")
            return
        
        # 파일 찾기
        files = [
            f for f in os.listdir(backups_root) 
            if f.startswith(f"{service}_") and f.endswith(".gpg")
        ]
        
        if not files:
            log_error(f"[restore] {service} 백업 파일(.gpg)이 없습니다: {backups_root}")
            return
        
        # 최신순 정렬
        files.sort(reverse=True)
        backup_file = os.path.join(backups_root, files[0])
        log_info(f"[restore] 최신 백업 자동 선택: {backup_file}")
    
    if not os.path.exists(backup_file):
        log_error(f"[restore] 파일 없음: {backup_file}")
        return

    # 2. 서비스별 복원 전략 확인
    # (backup_manager와 동일한 로직으로 판단)
    hot_restore_services = ["postgres", "vault"]
    is_hot = service in hot_restore_services

    if is_hot:
        log_info(f"[restore] {service}: Hot Restore 모드 (컨테이너 실행 상태 유지)")
        # 컨테이너가 켜져 있는지 확인
        if not check_container(service):
            log_warn(f"[restore] {service} 컨테이너가 실행 중이지 않습니다. 복원을 위해 시작합니다.")
            start_container(service)
            # 잠시 대기
            import time
            time.sleep(5)
    else:
        log_info(f"[restore] {service}: Cold Restore 모드 (컨테이너 중지)")
        stop_container(f"ai4infra-{service}")

    # 3. 복원 실행 (backup_manager 위임)
    try:
        success = restore_data(service, backup_file)
        
        if success:
            log_info(f"[restore] {service} 복원 성공")
            
            # Post-Restore Actions
            if not is_hot:
                # Cold Restore인 경우 재시작
                generate_env(service)
                # 권한 재설정 (파일 덮어쓰기로 인해 틀어졌을 수 있음)
                apply_service_permissions(service)
                start_container(service)
            
            # 서비스별 사후 점검
            if service == "postgres":
                 check_container("postgres", check_postgres)
            elif service == "vault":
                 check_container("vault", check_vault)
            else:
                 check_container(service)

        else:
            log_error(f"[restore] {service} 복원 실패")
            
    except Exception as e:
        log_error(f"[restore] 예외 발생: {e}")

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
        ['docker', 'ps', '--filter', 'name=ai4infra-vault', '--format', '{{.Names}}'],
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
        'docker', 'exec', '-i', 
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


def _execute_unseal_vault(interactive: bool = False):
    """
    Vault 언씰 로직 (내부 함수)
    interactive=True일 경우 사용자에게 수동 입력 안내 메시지를 출력합니다.
    """
    status_cmd = [
        'docker', 'exec', 
        '-e', 'VAULT_ADDR=https://127.0.0.1:8200',
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
        msg = "Vault가 초기화되지 않았습니다. 먼저 init-vault 실행하십시오."
        if interactive:
            log_error(f"[unseal_vault] {msg}")
        else:
            log_info(f"[install|unseal] {msg}")
        return

    # 3) 언실 여부 확인
    if not sealed:
        if interactive:
            log_info("[unseal_vault] Vault는 이미 언실되어 있습니다.")
            print("Vault UI: https://localhost:8200")
        else:
            log_info("[install|unseal] Vault는 이미 언실되어 있습니다.")
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
                        'docker', 'exec', 
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
                    if interactive:
                        print("Vault UI: https://localhost:8200")
                    return
                else:
                    log_error(f"[unseal_vault] 자동 언실 실패 (성공: {success_count}/{threshold})")
                    
        except Exception as e:
            log_error(f"[unseal_vault] 키 파일 읽기 오류: {e}")
            
    # -------------------------------------------------------------
    # 수동 모드 안내 (Interactive True일 때만)
    # -------------------------------------------------------------
    if interactive:
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
        print("   docker exec -it ai4infra-vault /bin/sh\n")

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
    else:
        log_warn("[install|unseal] 자동 언실 실패 (USB 키 없음) → 수동 언실 필요: 'make unseal-vault' 실행")

@app.command()
def unseal_vault():
    """Vault 언씰 - 사용자가 직접 터미널에서 vault operator unseal 명령을 실행하도록 안내합니다."""
    log_info("[unseal_vault] Vault 언씰 절차 시작")
    _execute_unseal_vault(interactive=True)

@app.command()
def setup_vault_base():
    """
    Vault 기본 인프라 구성 (Common Infrastructure)
    - KV Engine (v2) 활성화: secret/
    - AppRole Auth 활성화: auth/approle/
    - Audit Log 활성화: file (/vault/logs/audit.log)
    """
    log_info("[setup_vault_base] Vault 기본 구성 시작")

    base_cmd = [
        'docker', 'exec', 
        '-e', 'VAULT_ADDR=https://127.0.0.1:8200', 
        'ai4infra-vault',
        'vault'
    ]
    
    # 1. 상태 점검
    try:
        res = subprocess.run(base_cmd + ['status', '-format=json'], capture_output=True, text=True)
        status = json.loads(res.stdout)
        if not status.get('initialized') or status.get('sealed'):
            log_error("[setup_vault_base] Vault가 초기화되지 않았거나 Sealed 상태입니다.")
            return
    except Exception:
        log_error("[setup_vault_base] Vault 상태 확인 실패. 컨테이너가 실행 중인지 확인하세요.")
        return

    # 2. KV Engine (v2) 활성화
    try:
        log_info("1) KV Engine (secret/) 활성화 확인...")
        subprocess.run(
            base_cmd + ['secrets', 'enable', '-path=secret', '-version=2', 'kv'],
            capture_output=True, text=True
        ) # 이미 있으면 에러나지만 무시 (멱등성)
        log_info("   → 완료 (또는 이미 존재)")
    except Exception as e:
        log_warn(f"   → 확인 필요: {e}")

    # 3. AppRole Auth 활성화
    try:
        log_info("2) AppRole Auth (auth/approle/) 활성화 확인...")
        subprocess.run(
            base_cmd + ['auth', 'enable', 'approle'], 
            capture_output=True, text=True
        )
        log_info("   → 완료 (또는 이미 존재)")
    except Exception as e:
        log_warn(f"   → 확인 필요: {e}")

    # 4. Audit Device 활성화
    try:
        log_info("3) Audit Device (file) 활성화 확인...")
        # 로그 파일 권한 문제 방지를 위해 먼저 파일 생성 시도 (optional)
        subprocess.run(['docker', 'exec', 'ai4infra-vault', 'touch', '/vault/logs/audit.log'], check=False)
        subprocess.run(['docker', 'exec', 'ai4infra-vault', 'chmod', '666', '/vault/logs/audit.log'], check=False)

        subprocess.run(
            base_cmd + ['audit', 'enable', 'file', 'file_path=/vault/logs/audit.log'],
            capture_output=True, text=True
        )
        log_info("   → 완료 (또는 이미 존재)")
    except Exception as e:
        log_warn(f"   → 확인 필요: {e}")

    log_info("[setup_vault_base] 기본 구성 완료. (세부 정책은 각 서비스 프로젝트에서 설정하십시오)")

@app.command()
def clean_backups(service: str = typer.Argument("all", help="백업을 삭제할 서비스 (all 또는 서비스명)")):
    """서비스의 모든 백업 데이터를 삭제합니다."""
    
    backups_root = f"{BASE_DIR}/backups"
    if not os.path.exists(backups_root):
        log_info("[clean_backups] 백업 디렉터리가 존재하지 않습니다.")
        return

    # Determine targets
    if service == "all":
        # 백업 폴더 내의 모든 하위 폴더/파일 대상
        targets = os.listdir(backups_root)
    else:
        # 특정 서비스만
        targets = [service]

    # Filter targets to ensure they are items in backups_root
    valid_targets = []
    for t in targets:
        path = os.path.join(backups_root, t)
        if os.path.exists(path):
            valid_targets.append(t)
    
    if not valid_targets:
        log_warn(f"[clean_backups] '{service}'에 대한 백업을 찾을 수 없습니다.")
        return

    print("\n===================================================================")
    print(f" [주의] 다음 항목의 백업 데이터가 영구적으로 삭제됩니다: {', '.join(valid_targets)}")
    print("===================================================================\n")
    
    confirm = typer.confirm("정말로 삭제하시겠습니까?", default=False)
    if not confirm:
        log_info("[clean_backups] 삭제 취소됨")
        return

    for t in valid_targets:
        target_path = os.path.join(backups_root, t)
        log_info(f"[clean_backups] 삭제 중: {target_path}")
        try:
            # 디렉터리 자체를 삭제 (backup 시 mkdir -p로 재생성됨)
            subprocess.run(['rm', '-rf', target_path], check=True)
            log_info(f"[clean_backups] {t} 삭제 완료")
        except subprocess.CalledProcessError as e:
            log_error(f"[clean_backups] {t} 삭제 실패: {e}")

@app.command()
def install_rootca_windows():
    """
    Windows에 Root CA 자동 설치 (WSL2 환경 전용)
    """
    
    install_root_ca_windows()

@app.command()
def setup_cron():
    """
    모든 서비스의 설정(backup.schedule)을 읽어 Crontab에 자동 백업 작업 등록
    """
    log_info("[setup_cron] Cron 백업 스케줄 설정 시작")
    
    # 1. 설정 수집
    cron_lines = []
    # ai4infra-cli.py 절대 경로
    cli_path = os.path.abspath(__file__)
    # python 인터프리터 (venv) 경로
    python_path = sys.executable

    services = discover_services()
    for svc in services:
        cfg = load_config(f"{BASE_DIR}/{svc}/config/config.yml") # config 파일 위치는 환경변수 로딩 방식에 따름
        # [Note] discover_services는 config/*.yml을 읽지만, 여기선 상세 설정(schedule) 확인 필요
        # load_config는 경로를 인자로 받음. 프로젝트 루트 기준 config/{svc}.yml 로드
        cfg = load_config(f"{PROJECT_ROOT}/config/{svc}.yml") or {}
        
        schedule = cfg.get("backup", {}).get("schedule")
        if schedule:
            log_info(f" - {svc}: {schedule} detected")
            # Cron Line: {schedule} {user} {command}
            # 주의: user cron에 등록하므로 user 필드는 생략 (system cron 아님)
            # Log 리다이렉션 포함
            cmd = f"{python_path} {cli_path} backup {svc} >> /var/log/ai4infra/cron_backup.log 2>&1"
            line = f"{schedule} {cmd} # AI4INFRA-BACKUP:{svc}"
            cron_lines.append(line)
    
    if not cron_lines:
        log_info("[setup_cron] 등록할 백업 스케줄이 없습니다.")
        return

    # 2. 기존 Crontab 로드
    try:
        # crontab -l 실행 (없으면 fail)
        current_cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    except Exception:
        current_cron = ""

    # 3. 기존 AI4INFRA 항목 제거 (Idempotency)
    new_cron = []
    for line in current_cron.splitlines():
        if "# AI4INFRA-BACKUP" not in line:
            new_cron.append(line)
    
    # 4. 신규 항목 추가
    new_cron.extend(cron_lines)
    
    # 마지막 줄바꿈
    if new_cron and new_cron[-1] != "":
        new_cron.append("")
        
    final_cron_content = "\n".join(new_cron) + "\n"

    # 5. 등록
    try:
        subprocess.run(
            ["crontab", "-"], 
            input=final_cron_content, 
            text=True, 
            check=True
        )
        log_info(f"[setup_cron] Crontab 업데이트 완료 ({len(cron_lines)}개 등록)")
        for l in cron_lines:
            log_debug(f" [+] {l}")
            
        # 로그 파일 권한 확인 (User가 쓸 수 있도록)
        log_dir = "/var/log/ai4infra"
        if not os.path.exists(log_dir):
            subprocess.run(["mkdir", "-p", log_dir])
            subprocess.run(["chmod", "777", log_dir]) # 임시 (실 운영시 더 정교한 권한 필요)
            
    except subprocess.CalledProcessError as e:
        log_error(f"[setup_cron] Crontab 등록 실패: {e.stderr}")


if __name__ == "__main__":
    try:
        app()
    except Exception as e:
        log_error(str(e))
        sys.exit(1)