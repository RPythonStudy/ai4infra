#!/usr/bin/env python3
"""
파일명: scripts/ai4infra/utils/container_manager.py
목적: 각 컨테이너를 설치/백업/복구에 필요한 기초 함수들을 정의하는 파일을 분리하여 ai4infra-cli.py의 가독성과 재활용을 높이기 위함.
설명:

변경이력:
  - 2025-10-30: 최초 구현 (BenKorea)
"""

import subprocess
from typing import List, Callable
from datetime import datetime

import sys
import os

from dotenv import load_dotenv
    
from common.logger import log_debug, log_error, log_info

load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT")
BASE_DIR = os.getenv('BASE_DIR', '/opt/ai4infra')


def stop_container(
    service: str,
    search_pattern: str,
    stop_function: Callable[[List[str]], None],
    verify_pattern: str = None
):
    """
    서비스 컨테이너 중지 로직
    
    Args:
        service: 서비스 이름 (로깅용)
        search_pattern: 컨테이너 검색 패턴
        stop_function: 실제 중지를 수행하는 함수
        verify_pattern: 검증용 패턴 (없으면 search_pattern 사용)
    """
    # 1. 컨테이너 검색
    result = subprocess.run([
        'sudo', 'docker', 'ps', '--filter', f'name={search_pattern}',
        '--format', '{{.Names}}'
    ], capture_output=True, text=True)
    
    containers = [c for c in result.stdout.strip().split('\n') if c]
    
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
    
    remaining_containers = [c for c in verify_result.stdout.strip().split('\n') if c]
    
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
