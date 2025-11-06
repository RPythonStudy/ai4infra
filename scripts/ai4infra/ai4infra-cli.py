#!/usr/bin/env python3
"""
파일명: scripts/ai4infra/ai4infra-cli.py
목적: ai4infra 통합관리 스크립트 진입점
기능: 
- 설치, 설정, 상태 확인 등
변경이력:
  - 2025-10-04: 최초 구현 (BenKorea)
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
from utils.container_manager import create_user, add_sudoer, stop_container, copy_template, generate_env_file, install_bitwarden, ensure_network, start_container, backup_data
from utils.generate_certificates import generate_certificates

load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT")
BASE_DIR = os.getenv('BASE_DIR', '/opt/ai4infra')
app = typer.Typer(help="AI4INFRA 서비스 관리")
SERVICES = ('postgres', 'vault', 'elk', 'ldap', 'bitwarden') # 튜플로 선언하어 변경 방지


@app.command()
def install(service: str = typer.Argument("all", help="설치할 서비스 이름")):
    services = list(SERVICES) if service == "all" else [service]

    # bitwarden 사용자 생성
    if 'bitwarden' in services:
        result = create_user(username='bitwarden')
        if not result:
            log_error("[install] bitwarden 사용자 생성 실패 — 설치 중단")
            raise typer.Exit(code=1)
        result = add_sudoer(username='bitwarden',
                                  sudoers_line=f"bitwarden ALL=(ALL) NOPASSWD: /usr/bin/docker, {BASE_DIR}/bitwarden/bitwarden.sh")
        if not result:
            log_error("[install] bitwarden sudoers 설정 실패 — 설치 중단")
            raise typer.Exit(code=1)

    # 각 서비스별 처리
    for service in services:

        print("####################################################################################")
        log_info(f"[install] {service} 설치 시작")

        # 1. 컨테이너 중지
        if service == 'bitwarden':
            search_pattern = 'bitwarden'
        else:
            search_pattern = f'ai4infra-{service}'
        stop_container(search_pattern)

        # 2. 기존 데이터 백업
        if service == 'bitwarden':
            backup_data(service, 'bwdata')
        else:
            backup_data(service)
        
        # 3. 템플릿 복사
        copy_template(service)

        # 4. 환경 파일 생성
        generate_env_file(service)

        #5. bitwarden 설치
        if service == "bitwarden":
            install_bitwarden()
        
        # 6. 인증서 생성 (Vault 프로덕션 모드용)
        if service == "vault":
            log_info(f"[install] {service} SSL 인증서 생성 중...")
            generate_certificates([service], overwrite=False)

        # 7. 컨테이너 시작
        start_container(service)
        
        log_info(f"[install] {service} 설치 완료")
    
    # 서비스별로 Docker 컨테이너 구동
    # 8. 서비스별로 헬스체크 확인
  
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
    backup_file: str = typer.Argument(..., help="백업 파일 경로")
):
    """서비스 데이터 복원 - 극단적 간결 버전"""
    log_info(f"[restore] {service} 복원 시작: {backup_file}")
    
    # 1. 백업 파일 존재 확인
    if not os.path.exists(backup_file):
        log_error(f"[restore] 백업 파일 없음: {backup_file}")
        return
    
    # 2. 컨테이너 중지
    stop_container(service)
    
    # 3. 기존 데이터 삭제
    data_dir = f"{BASE_DIR}/{service}/data"
    subprocess.run(['sudo', 'rm', '-rf', data_dir])
    
    # 4. 백업 복원
    subprocess.run(['sudo', 'tar', '-xzf', backup_file, '-C', f"{BASE_DIR}/{service}"])
    subprocess.run(['sudo', 'chown', '-R', f"{os.getenv('USER')}:{os.getenv('USER')}", data_dir])
    
    # 5. 컨테이너 시작
    start_container(service)
    
    log_info(f"[restore] {service} 복원 완료: {backup_file}")

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
    
    # Vault 컨테이너 상태 확인
    result = subprocess.run(['sudo', 'docker', 'ps', '--filter', 'name=ai4infra-vault', 
                           '--format', '{{.Names}}'], capture_output=True, text=True)
    
    if 'ai4infra-vault' not in result.stdout:
        log_error("[init_vault] Vault 컨테이너가 실행되지 않음. 먼저 'install vault' 실행")
        return
    
    # Vault 초기화 (한 번만)
    init_cmd = [
        'sudo', 'docker', 'exec', 'ai4infra-vault', 
        'vault', 'operator', 'init', '-key-shares=1', '-key-threshold=1', '-format=json'
    ]
    
    try:
        result = subprocess.run(init_cmd, capture_output=True, text=True, check=True)
        init_data = result.stdout
        
        # 초기화 정보를 파일로 저장
        init_file = f"{BASE_DIR}/vault/vault_init.json"
        subprocess.run(['sudo', 'tee', init_file], input=init_data, text=True, check=True)
        subprocess.run(['sudo', 'chmod', '600', init_file])
        
        log_info(f"[init_vault] Vault 초기화 완료. 키 정보: {init_file}")
        log_info("[init_vault] 다음 단계: unseal 명령으로 Vault 언씰하세요")
        
    except subprocess.CalledProcessError as e:
        if "Vault is already initialized" in e.stderr:
            log_info("[init_vault] Vault가 이미 초기화됨")
        else:
            log_error(f"[init_vault] 초기화 실패: {e.stderr}")

@app.command()
def unseal_vault():
    """Vault 언씰 - 재시작 시마다 필요"""
    log_info("[unseal_vault] Vault 언씰 시작")
    
    init_file = f"{BASE_DIR}/vault/vault_init.json"
    if not os.path.exists(init_file):
        log_error("[unseal_vault] 초기화 파일 없음. 먼저 'init-vault' 실행")
        return
    
    # 초기화 파일에서 unseal key 추출
    result = subprocess.run(['sudo', 'cat', init_file], capture_output=True, text=True)
    import json
    init_data = json.loads(result.stdout)
    unseal_key = init_data['unseal_keys_b64'][0]
    
    # Vault 언씰
    unseal_cmd = [
        'sudo', 'docker', 'exec', 'ai4infra-vault',
        'vault', 'operator', 'unseal', unseal_key
    ]
    
    try:
        subprocess.run(unseal_cmd, check=True, capture_output=True)
        log_info("[unseal_vault] Vault 언씰 완료")
        
        # Root 토큰 정보 표시
        root_token = init_data['root_token']
        log_info(f"[unseal_vault] Root 토큰: {root_token}")
        log_info("[unseal_vault] Vault 웹 UI: https://localhost:8200")
        
    except subprocess.CalledProcessError as e:
        log_error(f"[unseal_vault] 언씰 실패: {e.stderr}")


if __name__ == "__main__":
    try:
        app()
    except Exception as e:
        log_error(str(e))
        sys.exit(1)