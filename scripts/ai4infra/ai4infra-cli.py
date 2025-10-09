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
from common.load_config import load_config
from common.logger import log_debug, log_error, log_info
from utils.container_manager import docker_stop_function, stop_container, backup_data
from utils.generate_certificates import generate_certificates

load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT")
BASE_DIR = os.getenv('BASE_DIR', '/opt/ai4infra')

app = typer.Typer(help="AI4INFRA 서비스 관리")

SERVICES = ['postgres', 'vault', 'elk', 'ldap']





def ensure_network():
    """ai4infra 네트워크 생성 - 극단적 간결 버전"""
    result = subprocess.run(['sudo', 'docker', 'network', 'ls', '--filter', 'name=ai4infra', '--format', '{{.Name}}'], 
                           capture_output=True, text=True)
    
    if 'ai4infra' not in result.stdout:
        subprocess.run(['sudo', 'docker', 'network', 'create', 'ai4infra'])
        log_info("[ensure_network] ai4infra 네트워크 생성됨")
    else:
        log_debug("[ensure_network] ai4infra 네트워크 이미 존재")


def start_container(service: str):
    """단일 서비스 컨테이너 시작 - 디버깅 강화 버전"""
    service_dir = f"{BASE_DIR}/{service}"
    compose_file = f"{service_dir}/docker-compose.yml"
    
    log_debug(f"[start_container] 시작: service_dir={service_dir}")
    log_debug(f"[start_container] compose_file={compose_file}")
    
    # docker-compose.yml 존재 확인
    if not os.path.exists(compose_file):
        log_error(f"[start_container] {service} docker-compose.yml 없음: {compose_file}")
        return
    
    # 네트워크 생성 확인
    ensure_network()
    
    # 파일 권한 및 내용 확인
    result = subprocess.run(['ls', '-la', compose_file], capture_output=True, text=True)
    log_debug(f"[start_container] 파일 권한: {result.stdout.strip()}")
    
    # docker compose 버전 확인 (sudo 사용)
    result = subprocess.run(['sudo', 'docker', 'compose', 'version'], capture_output=True, text=True)
    # log_debug(f"[start_container] docker compose 버전: {result.stdout.strip()}")

    # 실행 명령어 로깅 (sudo 추가)
    cmd = ['sudo', 'docker', 'compose', '-f', compose_file, 'up', '-d']
    log_debug(f"[start_container] 실행 명령: {' '.join(cmd)}")
    log_debug(f"[start_container] 작업 디렉터리: {service_dir}")
    
    # 컨테이너 시작 (sudo 사용)
    result = subprocess.run(cmd, cwd=service_dir, capture_output=True, text=True)
    
    # 상세한 결과 로깅
    log_debug(f"[start_container] 반환코드: {result.returncode}")
    log_debug(f"[start_container] stdout: {result.stdout}")
    log_debug(f"[start_container] stderr: {result.stderr}")
    
    if result.returncode == 0:
        log_info(f"[start_container] {service} 컨테이너 시작됨")
    else:
        log_error(f"[start_container] {service} 시작 실패")
        log_error(f"[start_container] 오류 내용: {result.stderr}")
        log_error(f"[start_container] 출력 내용: {result.stdout}")


def create_directory(service: str):
    """단일 서비스 디렉터리 생성 - 극단적 간결 버전"""
    # 유효성 검사
    if service not in SERVICES:
        log_error(f"[create_directory] 알 수 없는 서비스: {service}")
        return
    
    service_dir = f"{BASE_DIR}/{service}"
    subprocess.run(['sudo', 'mkdir', '-p', service_dir])
    subprocess.run(['sudo', 'chown', '-R', f"{os.getenv('USER')}:{os.getenv('USER')}", service_dir])
    
    # 실제 권한 확인 및 로그
    result = subprocess.run(['ls', '-ld', service_dir], capture_output=True, text=True)
    log_debug(f"[create_directory] {result.stdout.strip()}")
    log_info(f"[create_directory] {service} 디렉터리 생성 완료: {service_dir}")






def replace_env_vars(content: str, service: str) -> str:
    """환경변수 치환 - config + .env 기반 극단적 간결 버전"""
    config = load_config(f"{PROJECT_ROOT}/config/{service}.yml", service)
    
    # .env 환경변수 추가 로딩 (보안 민감 정보)
    env_vars = {
        'POSTGRES_USER': os.getenv('POSTGRES_USER', 'postgres'),
        'POSTGRES_PASSWORD': os.getenv('POSTGRES_PASSWORD', 'postgres'),
        'POSTGRES_DB': os.getenv('POSTGRES_DB', 'ai4infra'),
        'VAULT_DEV_ROOT_TOKEN_ID': os.getenv('VAULT_DEV_ROOT_TOKEN_ID', 'myroot'),
        'VAULT_DEV_LISTEN_ADDRESS': os.getenv('VAULT_DEV_LISTEN_ADDRESS', '0.0.0.0:8200')
    }
    
    # config 설정 치환
    for key, value in config.items():
        if isinstance(value, str) and "${BASE_DIR}" in value:
            value = value.replace("${BASE_DIR}", BASE_DIR)
        content = content.replace(f"${{{key}}}", str(value))
        content = re.sub(rf'\${{{re.escape(key)}:-[^}}]*}}', str(value), content)
    
    # .env 환경변수 치환
    for key, value in env_vars.items():
        content = content.replace(f"${{{key}}}", str(value))
        content = re.sub(rf'\${{{re.escape(key)}:-[^}}]*}}', str(value), content)
    
    return content


def copy_template(service: str):
    """템플릿 복사 및 환경변수 치환 - 극단적 간결 버전"""
    template_dir = f"{PROJECT_ROOT}/template/{service}"
    target_dir = f"{BASE_DIR}/{service}"
    
    if not os.path.exists(template_dir):
        return
    
    # 템플릿 파일들 찾기
    result = subprocess.run(['find', template_dir, '-type', 'f'], capture_output=True, text=True)
    files = [f for f in result.stdout.strip().split('\n') if f.strip()]
    
    # 파일별 복사 및 치환
    for file_path in files:
        rel_path = file_path.replace(f"{template_dir}/", "")
        target_file = f"{target_dir}/{rel_path}"
        
        # 디렉터리 생성 및 파일 처리
        subprocess.run(['sudo', 'mkdir', '-p', os.path.dirname(target_file)])
        
        with open(file_path, 'r') as f:
            content = replace_env_vars(f.read(), service)
        
        with open(target_file, 'w') as f:
            f.write(content)
    
    # 권한 설정
    subprocess.run(['sudo', 'chown', '-R', f"{os.getenv('USER')}:{os.getenv('USER')}", target_dir])
    
    log_info(f"[copy_template] {service} → {len(files)}개 파일 복사 완료")


@app.command()
def install(service: str = typer.Argument("all", help="설치할 서비스 이름 (또는 'all' 전체)")):
    services_to_install = SERVICES if service == "all" else [service]
    
    # 각 서비스별 처리
    for svc_name in services_to_install:
        print(f"####################################################################")
        log_info(f"[install] {svc_name} 설치 시작")
        
        # 1. 컨테이너 중지
        stop_container(
            service=svc_name,
            search_pattern=f'ai4infra-{svc_name}',
            stop_function=docker_stop_function
        )
        
        # 2. 기존 데이터 백업
        backup_file = backup_data(svc_name)
        if backup_file:
            log_info(f"[install] {svc_name} 백업 완료: {backup_file}")
        
        # 3. 디렉터리 생성
        create_directory(svc_name)
        
        # 4. 템플릿 복사
        copy_template(svc_name)
        
        # 5. 인증서 생성 (Vault 프로덕션 모드용)
        if svc_name == "vault":
            log_info(f"[install] {svc_name} SSL 인증서 생성 중...")
            generate_certificates([svc_name], overwrite=False)
        
        # 6. 컨테이너 시작
        start_container(svc_name)
        
        log_info(f"[install] {svc_name} 설치 완료")
    
    # 서비스별로 Docker 컨테이너 구동
    # 8. 서비스별로 헬스체크 확인
    

@app.command()
def backup(service: str = typer.Argument(..., help="백업할 서비스 (postgres, all)")):
    """서비스 데이터 백업"""
    services = SERVICES if service == "all" else [service]
    
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
    stop_container(
        service=service,
        search_pattern=f'ai4infra-{service}',
        stop_function=docker_stop_function
    )
    
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