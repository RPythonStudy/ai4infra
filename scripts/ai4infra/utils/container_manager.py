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

def create_bitwarden_user(password: str = "bit") -> bool:
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

def stop_container(service: str):
    search_pattern = f'ai4infra-{service}'
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
    if service == "bitwarden":
        """간결한 Bitwarden 설치:

        - `/opt/ai4infra/bitwarden` 디렉터리로 이동하여 설치 스크립트를 실행합니다
        - 실행 권한 및 소유권을 보장한 뒤, bitwarden 사용자로 설치 명령을 실행합니다
        """
        log_info("[install_bitwarden] 시작")

        bitwarden_dir = f"{BASE_DIR}/bitwarden"
        bitwarden_script = f"{bitwarden_dir}/bitwarden.sh"

        if not os.path.exists(bitwarden_dir):
            log_error(f"[install_bitwarden] 디렉터리 없음: {bitwarden_dir}")
            return False

        if not os.path.exists(bitwarden_script):
            log_error(f"[install_bitwarden] 설치 스크립트 없음: {bitwarden_script}")
            return False

        try:
            # 실행 권한 및 소유권 보장
            subprocess.run(['sudo', 'chmod', '+x', bitwarden_script], check=True)
            subprocess.run(['sudo', 'chown', '-R', 'bitwarden:bitwarden', bitwarden_dir], check=True)

            # bitwarden 사용자로 전환하여 설치 스크립트 실행
            # (sudoers에 의해 비밀번호 없이 실행 가능해야 함)
            cmd = f'cd {bitwarden_dir} && sudo ./bitwarden.sh install'
            subprocess.run(['sudo', '-u', 'bitwarden', 'bash', '-c', cmd], check=True)

            log_info("[install_bitwarden] 설치 명령 실행 완료")
            return True

        except subprocess.CalledProcessError as e:
                log_error(f"[install_bitwarden] 실패: {e}")
                return False
    
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

def prepare_service(service: str) -> str:

    """템플릿을 서비스 디렉터리로 재귀 복사(항상 덮어쓰기)하고 소유권을 보장합니다.

    동작:
    - `template/{service}`가 존재하는지 확인
    - `service_dir`가 존재하는지 확인(서비스 준비 전 `create_directory`가 호출되었어야 함)
    - 항상 `service_dir` 내부를 제거한 뒤(template 내용을 덮어씀)
    - `cp -a template/. service_dir`로 재귀 복사
    - 서비스별 소유자로 `chown -R` 수행(항상 보장)

    반환: 서비스 디렉터리 경로(성공) 또는 빈 문자열(실패)
    """
    template_dir = f"{PROJECT_ROOT}/template/{service}"
    service_dir = f"{BASE_DIR}/{service}"

    # 템플릿 존재 확인
    if not os.path.exists(template_dir):
        log_error(f"[prepare_service] 템플릿 없음: {template_dir}")
        return ""


    try:
        # 항상 덮어쓰기: 서비스 디렉터리 내부 삭제
        subprocess.run(['sudo', 'bash', '-c', f'rm -rf "{service_dir}"/*'], check=True)

        # 재귀 복사 (퍼미션/소유권 유지 시도)
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
    """Manual-first installation flow for Bitwarden.

    This function does not attempt automated installs. It prints clear manual
    steps for the operator to run in a separate terminal, then blocks on Enter.
    After Enter it calls `bitwarden_start()` to try to start the service.
    """
    bitwarden_dir = f"{BASE_DIR}/bitwarden"
    bitwarden_script = f"{bitwarden_dir}/bitwarden.sh"

    # 사전 체크
    if not os.path.exists(bitwarden_dir):
        log_error(f"[install_bitwarden] 디렉터리 없음: {bitwarden_dir}")
        return False

    if not os.path.exists(bitwarden_script):
        log_error(f"[install_bitwarden] 설치 스크립트 없음: {bitwarden_script}")
        return False

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
    return bitwarden_start()

def bitwarden_start ():  # 함수명 수정
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

