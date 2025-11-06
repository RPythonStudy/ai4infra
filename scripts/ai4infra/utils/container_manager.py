#!/usr/bin/env python3
"""
파일명: scripts/ai4infra/utils/container_manager.py
목적: 각 컨테이너를 설치/백업/복구에 필요한 기초 함수들을 정의하는 파일을 분리하여 ai4infra-cli.py의 가독성과 재활용을 높이기 위함.
설명:

변경이력:
  - 2025-11-05: create_user 구현 (BenKorea)
  - 2025-10-30: 최초 구현 (BenKorea)
"""

import subprocess
from pathlib import Path
from typing import List, Callable, Optional
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

def create_user(username: str, password: str = "bit") -> bool:
    """지정된 시스템 사용자를 생성합니다(이미 존재하면 생성하지 않음).

    동작:
    - 함수 내부에서 진행 상황과 오류를 `log_info` / `log_error`로 기록합니다.
    - 사용자가 이미 존재하면 True를 반환하고, 생성이 성공하면 True를 반환합니다.
    - 생성이 실패하면 False를 반환합니다.

    호출자 주의사항:
    - 이 헬퍼는 내부 로깅과 불린 반환을 모두 수행하므로 호출자는 반환값을 검사하여
      계속 진행할지 중단할지 결정해야 합니다.

    미래 검토사항:
    - 다른 컨테이너들도 uid/gid 변경이 가능하다면 사용자 생성 검토 필요
    - password 매개변수를 외부에서 받도록 변경 검토  

    변경이력:
    - 2025-11-05: 최초 구현 (BenKorea)
    """
    try:
        # 사용자가 이미 존재하는지 확인
        result = subprocess.run(['id', username], capture_output=True, text=True)
        if result.returncode == 0:
            log_debug(f"[create_user] id {username} -> stdout={result.stdout.strip()}")            
            log_info(f"[create_user] 사용자 '{username}'이 이미 존재하므로 생성하지 않고 계속 진행합니다")
            return True

        # 사용자 생성 (비대화형)
        subprocess.run(['sudo', 'useradd', '-m', '-s', '/bin/bash', username], check=True)
        # 비밀번호 설정
        subprocess.run(f'echo "{username}:{password}" | sudo chpasswd', shell=True, check=True)
        log_info(f"[create_user] 사용자 {username} 생성 및 비밀번호 설정 완료")
        return True

    except subprocess.CalledProcessError as e:
        log_error(f"[create_user] 사용자 생성 실패: {e}")
        return False

def register_sudoers(username: str, sudoers_line: str) -> bool:
    """Sudoers 설정 (멱등성 보장)

    변경이력:
    - 2025-11-05: 최초 구현 (BenKorea)
    """
    sudoers_file = f"/etc/sudoers.d/{username}-docker"
    tmp_path = f"/tmp/{username}-sudoers.tmp"

    try:
        # 파일이 이미 존재하는지 확인
        if Path(sudoers_file).exists():
            # 해당라인이 이미 존재하는지 확인
            result = subprocess.run(['sudo', 'grep', '-F', sudoers_line, sudoers_file], capture_output=True)
            if result.returncode == 0:         
                log_debug(f"[register_sudoers] grep -> stdout={result.stdout.strip()}")
                log_info("[register_sudoers] 이미 설정되어 있어 등록 및 설정 없이 진행합니다.")
                return True
            # 해당라인을 추가
            result = subprocess.run(['sudo', 'bash', '-c', f'echo "{sudoers_line}" | sudo tee -a {sudoers_file}'], check=True, capture_output=True)
            if result.returncode == 0:    
                log_debug(f"[register_sudoers] sudoers_line -> stdout={result.stdout.strip()}")
                log_info("[register_sudoers] 해당 라인을 추가하였습니다.")
                return True
                
        else:
            # 파일을 생성
            with open(tmp_path, 'w') as f:
                f.write(f"{sudoers_line}\n")
            result = subprocess.run(['sudo', 'mv', tmp_path, sudoers_file], check=True, capture_output=True)
            if result.returncode == 0:    
                log_debug(f"[register_sudoers] sudoers_file 생성 -> stdout={result.stdout.strip()}")
                log_info("[register_sudoers] sudoers_file 생성 하였습니다.")
            result = subprocess.run(
                ['sudo', 'chmod', '440', sudoers_file],
                capture_output=True,
                text=True,
                check=True
                )
            if result.returncode == 0:    
                log_debug(f"[register_sudoers] chmod -> stdout={result.stdout.strip()}")
                log_info("[register_sudoers] sudoers_file 읽기로만 권한을 부여 하였습니다.")
            return True

    except subprocess.CalledProcessError as e:
        log_error(f"[register_sudoers] 명령 실패: {e}")
        return False
    except Exception as e:
        log_error(f"[register_sudoers] 예외 발생: {e}")
        return False

def stop_container(service: str) -> bool:
    if service == 'bitwarden':
        search_pattern = service
    else:
        search_pattern = f'ai4infra-{service}'

    # 컨테이너 검색
    result = subprocess.run([
        'sudo', 'docker', 'ps', '--filter', f'name={search_pattern}',
        '--format', '{{.Names}}'
    ], capture_output=True, text=True)
    if result.returncode == 0:    
        log_debug(f"[stop_container] docker ps -> result.stdout={result.stdout.strip()}")

    containers = [container for container in result.stdout.strip().split('\n') if container]
    
    # 빈 결과 처리
    if not containers:
        log_info(f"[stop_container] {service} 실행 중인 컨테이너 없음")
        return True
    
    # 중지 대상 
    log_debug(f"[stop_container] {service} 중지 대상: {', '.join(containers)}")

    # 중단
    result = docker_stop_function(containers)

def docker_stop_function(containers: List[str]):
    """Docker 명령어로 직접 중지"""
    for container in containers:
        result = subprocess.run(['sudo', 'docker', 'stop', container], capture_output=True)
        log_debug(f"[docker_stop_function] sudo docker stop -> stdout={result.stdout.strip()} stderr={result.stderr.strip()} rc={result.returncode}")

def bitwarden_stop_function(bitwarden_dir: str) -> bool:
    """Bitwarden 중지 스크립트 실행. 성공 시 True, 실패 시 False 반환."""
    cmd = ['sudo', '-u', 'bitwarden', f'{bitwarden_dir}/bitwarden.sh', 'stop']
    try:
        result = subprocess.run(cmd, cwd=bitwarden_dir, capture_output=True, text=True)
        log_debug(f"[bitwarden_stop] stdout={result.stdout.strip()} stderr={result.stderr.strip()} rc={result.returncode}")
        return result.returncode == 0
    except Exception as e:
        log_error(f"[bitwarden_stop] 예외 발생: {e}")
        return False

def create_directory(service: str):
    """단일 서비스 디렉터리 생성 - root 소유권으로 생성""" 
    service_dir = f"{BASE_DIR}/{service}"
    result = subprocess.run(['sudo', 'mkdir', '-p', service_dir], capture_output=True)
    log_debug(f"[create_directory] mkdir stdout = {result.stdout.strip()}")
    
    # 실제 권한 확인 및 로그
    result = subprocess.run(['ls', '-ld', service_dir], capture_output=True, text=True)
    log_debug(f"[create_directory] {result.stdout.strip()}")

def prepare_service(service: str) -> str:
    template_dir = f"{PROJECT_ROOT}/template/{service}"
    service_dir = f"{BASE_DIR}/{service}"

    try:
        # subprocess.run(['sudo', 'bash', '-c', f'rm -rf "{service_dir}"/*'], check=True)
        subprocess.run(['sudo', 'cp', '-a', f"{template_dir}/.", service_dir], check=True)

        # 소유자 설정: 항상 수행하여 소유권 보장
        if service == 'bitwarden':
            owner = 'bitwarden:bitwarden'
        else:
            owner = f"{os.getenv('USER')}:{os.getenv('USER')}"
        subprocess.run(['sudo', 'chown', '-R', owner, service_dir], check=True)

        log_info(f"[prepare_service] {service} 준비 완료: {service_dir}")
        return service_dir

    except subprocess.CalledProcessError as e:
        log_error(f"[prepare_service] 실패: {e}")
        return ""

def install_bitwarden():
    bitwarden_dir = f"{BASE_DIR}/bitwarden"
    bitwarden_script = f"{bitwarden_dir}/bitwarden.sh"

    # 실행가능하도록 설정
    subprocess.run(['sudo', 'chmod', '+x', bitwarden_script], check=True)

    # 설치
    # subprocess.run(['sudo', '-u','bitwarden', '/opt/ai4infra/bitwarden/bitwarden.sh','install'], check=True)



    # 사용자에게 수동 실행 안내 및 블로킹 대기
    instructions = (
        "수동 설치가 필요합니다. 아래 절차를 다른 터미널에서 실행한 뒤, 이 터미널로 돌아와 Enter를 눌러 계속하세요:\n\n"
        "1) 권장(권한 보존): bitwarden 계정으로 전환하여 설치\n"
        "   sudo -i -u bitwarden\n"
        "   cd /opt/ai4infra/bitwarden\n"
        "   sudo ./bitwarden.sh install\n\n"
        "2) 간단(루트로 직접 실행):\n"
        "   sudo /opt/ai4infra/bitwarden/bitwarden.sh install\n\n"
        "설치 후 파일 소유권이 root로 생성된 경우 소유자 복구:\n"
        "   sudo chown -R bitwarden:bitwarden /opt/ai4infra/bitwarden\n\n"
        "설치를 완료한 뒤 이 터미널로 돌아와 Enter를 눌러 계속하세요."
    )
    log_info(f"[install_bitwarden] 수동 설치 안내:\n{instructions}")

    try:
        input("설치 완료 후 Enter를 눌러 계속합니다...")
    except KeyboardInterrupt:
        log_info("[install_bitwarden] 사용자가 중단함")
        return False

    # 사용자가 설치를 완료했다고 표시하면 비트워든 시작 시도
    log_info("[install_bitwarden] 사용자가 설치를 완료했다고 표시함 — 시작 시도")
    return True

def bitwarden_start():
    bitwarden_dir = f"{BASE_DIR}/bitwarden"
    bitwarden_script = f"{bitwarden_dir}/bitwarden.sh"

    instructions = (
            "Bitwarden을 수동으로 시작해 주세요 (다른 터미널에서):\n"
            f"  sudo -i -u bitwarden\n"
            f"  cd {bitwarden_dir}\n"
            f"  sudo ./bitwarden.sh start\n\n"
            "시작 후 원래 터미널로 돌아와 Enter를 눌러 계속하세요."
        )
    log_info(f"[bitwarden_start] 수동 시작 안내:\n{instructions}")

    try:
        input("수동 시작 후 Enter를 눌러 계속합니다...")
    except KeyboardInterrupt:
        log_info("[bitwarden_start] 사용자가 중단함")
        return False

    log_info("[bitwarden_start] 사용자가 수동 시작을 수행했다고 표시함 — 자동 재시도 없음")
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

    if service == "bitwarden":
        bitwarden_start()
        return
    else:
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
