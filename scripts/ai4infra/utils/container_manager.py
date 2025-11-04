#!/usr/bin/env python3
"""
파일명: scripts/ai4infra/utils/container_manager.py
목적: 각 컨테이너를 설치/백업/복구에 필요한 기초 함수들을 정의하는 파일을 분리하여 ai4infra-cli.py의 가독성과 재활용을 높이기 위함.
설명:

변경이력:
  - 2025-10-30: 최초 구현 (BenKorea)
"""

import subprocess
from pathlib import Path
from typing import List, Callable
from datetime import datetime

import sys
import os
import re

from dotenv import load_dotenv

from common.load_config import load_config
from common.logger import log_debug, log_error, log_info

load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT")
BASE_DIR = os.getenv('BASE_DIR', '/opt/ai4infra')
SERVICES = ['postgres', 'vault', 'elk', 'ldap', 'bitwarden']

def setup_sudoers():
    """Sudoers 설정 (멱등성 보장)"""
    log_info("[setup-sudoers] 시작")
    
    bitwarden_dir = f"{BASE_DIR}/bitwarden"
    sudoers_file = "/etc/sudoers.d/bitwarden-docker"
    sudoers_line = f"bitwarden ALL=(ALL) NOPASSWD: /usr/bin/docker, {bitwarden_dir}/bitwarden.sh"
    
    # 파일 존재 및 내용 확인
    if Path(sudoers_file).exists():
        result = subprocess.run(['sudo', 'grep', '-F', sudoers_line, sudoers_file], 
                              capture_output=True)
        if result.returncode == 0:
            log_info("[setup-sudoers] 이미 설정되어 있음")
            result = subprocess.run(['sudo', '-u', 'bitwarden', 'sudo', '-l'], capture_output=True, text=True)
            log_info(f"[setup-sudoers] 완료 {result.stdout.strip()}")
            return
        else:
            log_info("[setup-sudoers] 기존 파일에 내용 추가")
            # 기존 파일에 추가
            subprocess.run(['sudo', 'bash', '-c', f'echo "{sudoers_line}" >> {sudoers_file}'])
    else:
        log_info("[setup-sudoers] 새 파일 생성")
        # 새 파일 생성
        with open('/tmp/bitwarden-docker', 'w') as f:
            f.write(f"{sudoers_line}\n")
        subprocess.run(['sudo', 'cp', '/tmp/bitwarden-docker', sudoers_file])
        subprocess.run(['rm', '/tmp/bitwarden-docker'])
    
    # 권한 설정 (항상 실행)
    subprocess.run(['sudo', 'chmod', '440', sudoers_file])
    result = subprocess.run(['sudo', '-u', 'bitwarden', 'sudo', '-l'], capture_output=True, text=True)
    log_info(f"[setup-sudoers] 완료 {result.stdout.strip()}")

def stop_container(
    service: str,
    search_pattern: str,
    stop_function: Callable[[List[str]], None],
    verify_pattern: str = None
):
    """
    서비스 컨테이너 중지 로직
    
    컨테이너 검색 → 중지 실행 → 결과 검증의 공통 워크플로우를 제공하며,
    실제 중지 방법은 서비스별로 다른 stop_function을 통해 위임합니다.
    
    Args:
        service: 서비스 이름 (로깅용)
        search_pattern: 컨테이너 검색 패턴 (docker ps --filter name= 에 사용)
        stop_function: 실제 중지를 수행하는 함수
            - docker_stop_function: 일반적인 docker stop 명령 사용
            - bitwarden_stop_function: bitwarden.sh stop 스크립트 사용
            - 기타 서비스별 맞춤 중지 로직 가능
        verify_pattern: 검증용 패턴 (없으면 search_pattern 사용)
    
    Examples:
        # 일반 Docker 컨테이너 중지
        stop_container(
            service="postgres",
            search_pattern="ai4infra-postgres", 
            stop_function=docker_stop_function
        )
        
        # Bitwarden 전용 스크립트 사용
        stop_container(
            service="bitwarden",
            search_pattern="bitwarden",
            stop_function=bitwarden_stop_function("/opt/bitwarden")
        )
    
    Note:
        이 함수는 전략 패턴(Strategy Pattern)을 구현하여 서비스별로 다른 
        중지 메커니즘을 지원합니다. 공통 로직(검색, 검증, 로깅)은 여기서 
        처리하고, 실제 중지 방법만 stop_function으로 분리했습니다.
    """
    # 1. 컨테이너 검색
    result = subprocess.run([
        'sudo', 'docker', 'ps', '--filter', f'name={search_pattern}',
        '--format', '{{.Names}}'
    ], capture_output=True, text=True)

    log_debug(f"[stop_container] result.stdout={result.stdout}")

    containers = [container for container in result.stdout.strip().split('\n') if container]
    
    # 2. 빈 결과 처리
    if not containers:
        log_info(f"[stop_container] {service} 실행 중인 컨테이너 없음")
        return
    
    # 3. 중지 대상 로깅
    log_debug(f"[stop_container] {service} 중지 대상: {', '.join(containers)}")
    
    # 4. 실제 중지 실행 (서비스별 구현)
    stop_function(containers)
    
    # 5. 결과 검증
    verify_pattern = verify_pattern or search_pattern
    verify_result = subprocess.run([
        'sudo', 'docker', 'ps', '--filter', f'name={verify_pattern}',
        '--format', '{{.Names}}'
    ], capture_output=True, text=True)
    
    remaining_containers = [container for container in verify_result.stdout.strip().split('\n') if container]
    
    # 6. 성공/실패 로깅
    if not remaining_containers:
        log_info(f"[stop_container] {service} → 컨테이너 중지 완료: {', '.join(containers)}")
    else:
        log_error(f"[stop_container] {service} → 중지 실패, 여전히 실행 중: {', '.join(remaining_containers)}")

def docker_stop_function(containers: List[str]):
    """Docker 명령어로 직접 중지"""
    for container in containers:
        subprocess.run(['sudo', 'docker', 'stop', container])

def bitwarden_stop_function(bitwarden_dir: str):
    """Bitwarden 스크립트로 중지"""
    def _stop(containers: List[str]):
        subprocess.run([
            'sudo', '-u', 'bitwarden', f'{bitwarden_dir}/bitwarden.sh', 'stop'
        ], cwd=bitwarden_dir)
    return _stop

def create_bitwarden_user(password: str = "bitwarden2024!") -> bool:
    """bitwarden 시스템 사용자 생성"""
    log_info("[create_bitwarden_user] 시작")
    
    try:
        # 사용자가 이미 존재하는지 확인
        result = subprocess.run(['id', 'bitwarden'], capture_output=True, text=True)
        if result.returncode == 0:
            log_info("[create_bitwarden_user] 사용자 'bitwarden'이 이미 존재합니다")
            return True
        else:
            # 사용자 생성 (비대화형)
            subprocess.run(['sudo', 'useradd', '-m', '-s', '/bin/bash', 'bitwarden'], check=True)
            # 비밀번호 설정
            subprocess.run(f'echo "bitwarden:{password}" | sudo chpasswd', 
                          shell=True, check=True)
            log_info("[create_bitwarden_user] 사용자 bitwarden 생성 및 비밀번호 설정 완료")
            return True
    except subprocess.CalledProcessError as e:
        log_error(f"[create_bitwarden_user] 사용자 생성 실패: {e}")
        return False

def create_directory(service: str):
    """단일 서비스 디렉터리 생성 - root 소유권으로 생성"""
    # 유효성 검사
    if service not in SERVICES:
        log_error(f"[create_directory] 알 수 없는 서비스: {service}")
        return
    
    service_dir = f"{BASE_DIR}/{service}"
    subprocess.run(['sudo', 'mkdir', '-p', service_dir])
    
    # 실제 권한 확인 및 로그
    result = subprocess.run(['ls', '-ld', service_dir], capture_output=True, text=True)
    log_debug(f"[create_directory] {result.stdout.strip()}")

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

        # 모든 서비스 임시 파일로 처리 (통일된 방식)
        temp_file = f"/tmp/{service}_{os.path.basename(target_file)}"
        with open(temp_file, 'w') as f:
            f.write(content)
        
        # sudo로 복사
        subprocess.run(['sudo', 'cp', temp_file, target_file])
        subprocess.run(['rm', temp_file])
    
    # 서비스별 권한 설정 (마지막 단계)
    if service == 'bitwarden':
        owner = 'bitwarden:bitwarden'
    else:
        owner = f"{os.getenv('USER')}:{os.getenv('USER')}"
    
    subprocess.run(['sudo', 'chown', '-R', owner, target_dir])
    
    log_info(f"[copy_template] {service} → {len(files)}개 파일 복사 완료 (소유자: {owner})")

def bitwarden_start():  # 함수명 수정
    """Bitwarden 시작"""
    log_info("[bitwarden_start] 시작")
    
    bitwarden_dir = f"{BASE_DIR}/bitwarden"
    bitwarden_script = f"{bitwarden_dir}/bitwarden.sh"
    
    # 1. 파일 존재 확인
    if not os.path.exists(bitwarden_script):
        log_error(f"[bitwarden_start] bitwarden.sh 파일 없음: {bitwarden_script}")
        return False
    
    # 2. 실행 권한 설정 (sudo 사용)
    try:
        subprocess.run(['sudo', 'chmod', '+x', bitwarden_script], check=True)
        log_debug(f"[bitwarden_start] 실행 권한 설정 완료: {bitwarden_script}")
    except subprocess.CalledProcessError as e:
        log_error(f"[bitwarden_start] 권한 설정 실패: {e}")
        return False
    
    # 3. Bitwarden 설치 (실시간 출력 + 타임아웃)
    try:
        log_info("[bitwarden_start] Bitwarden 설치 중... (최대 10분 소요)")
        result = subprocess.run([
            'sudo', '-u', 'bitwarden', bitwarden_script, 'install'
        ], cwd=bitwarden_dir, timeout=600, check=True)  # 10분 타임아웃, 실시간 출력
        
        log_info("[bitwarden_start] 설치 완료")
        
    except subprocess.TimeoutExpired:
        log_error("[bitwarden_start] 설치 타임아웃 (10분 초과)")
        return False
    except subprocess.CalledProcessError as e:
        log_error(f"[bitwarden_start] 설치 실패: {e}")
        return False
    
    # 4. Bitwarden 시작
    try:
        log_info("[bitwarden_start] Bitwarden 시작 중...")
        result = subprocess.run([
            'sudo', '-u', 'bitwarden', bitwarden_script, 'start'
        ], cwd=bitwarden_dir, capture_output=True, text=True, check=True)
        
        log_info(f"[bitwarden_start] 시작 완료")
        log_debug(f"[bitwarden_start] 시작 출력: {result.stdout}")
        return True
        
    except subprocess.CalledProcessError as e:
        log_error(f"[bitwarden_start] 시작 실패: {e}")
        log_error(f"[bitwarden_start] 시작 stderr: {e.stderr}")
        return False

def backup_data(service: str) -> str:
    """서비스 데이터 백업 - 극단적 간결 버전"""
    if service == "bitwarden":
        data_folder = "bwdata"
    else:
        data_folder = "data"
    data_dir = f"{BASE_DIR}/{service}/{data_folder}"
    backup_dir = f"{BASE_DIR}/{service}/backups"
    
    # 백업할 데이터가 없으면 건너뛰기
    if not os.path.exists(data_dir):
        log_info(f"[backup_data] {service} 백업할 데이터 없음: {data_dir}")
        return ""
    
    # 백업 파일 경로
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{backup_dir}/backup_{timestamp}.tar.gz"
    
    # 백업 실행
    subprocess.run(['sudo', 'mkdir', '-p', backup_dir])
    subprocess.run(['sudo', 'tar', '-czf', backup_file, '-C', f"{BASE_DIR}/{service}", data_folder])
    subprocess.run(['sudo', 'chown', f"{os.getenv('USER')}:{os.getenv('USER')}", backup_file])

    log_info(f"[backup_data] {service} 백업: {backup_file}")
    return backup_file
