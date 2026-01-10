#!/usr/bin/env python3

import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv

from common.logger import log_debug, log_error, log_info



load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT")
BASE_DIR = os.getenv('BASE_DIR', '/opt/ai4infra')


def stop_container(search_pattern: str) -> bool:
    """name 필터 패턴으로 일치하는 Docker 컨테이너를 중지"""

    cmd = [
        'sudo', 'docker', 'ps',
        '--filter', f'name={search_pattern}',
        '--format', '{{.Names}}'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log_error(f"[stop_container] docker ps 실패: {result.stderr.strip()}")
        return False

    containers = [c for c in result.stdout.strip().split('\n') if c]
    if not containers:
        log_info(f"[stop_container] {search_pattern}: 실행 중인 컨테이너 없음")
        return True

    for c in containers:
        result = subprocess.run(['sudo', 'docker', 'stop', c], capture_output=True, text=True)
        if result.returncode == 0:
            log_info(f"[stop_container] {c} 컨테이너 중지함")
        else:
            log_error(f"[stop_container] {c} 중지 실패: {result.stderr.strip()}")

    return True

def copy_template(service: str) -> bool:
    template_dir = f"{PROJECT_ROOT}/templates/{service}"
    service_dir = f"{BASE_DIR}/{service}"

    try:
        subprocess.run(['sudo', 'mkdir', '-p', service_dir], check=True)

        exclude_args = []



        # Postgres override 제외
        # 이유: 2-Step Initialization (GEMINI.md 참조)
        #       - 1단계: 기본 템플릿만으로 DB 초기화 및 볼륨 생성 (이때 override가 있으면 인증서 부재로 crash)
        #       - 2단계: 인증서 발급 후 override 파일 수동 복사하여 TLS 적용 재기동
        if service == "postgres":
            exclude_args.extend([
                '--exclude', 'docker-compose.override.yml',
            ])

        dry_cmd = [
            'sudo', 'rsync',
            '-a',       # Archive 모드 (권한/속성 등 유지)
            '-i',       # Itemize (변경 내역 상세 출력)
            '--no-t',   # Time: 수정 시간 변경은 무시 (실질적 내용 변경만 감지)
            '--no-o',   # Owner: 소유자 변경 안 함 (타겟 폴더 권한 존중)
            '--no-g',   # Group: 그룹 변경 안 함
            '--dry-run' # 실제 실행 안 함 (시뮬레이션)
        ] + exclude_args + [
            f"{template_dir}/",
            f"{service_dir}/"
        ]

        dry_run = subprocess.run(dry_cmd, capture_output=True, text=True, check=True)
        changed = dry_run.stdout.strip()

        if not changed:
            log_info(f"[copy_template] {service_dir}: 변경 사항 없음")
            return True

        log_debug(f"[copy_template] (dry-run 결과):\n{changed}")

        real_cmd = [
            'sudo', 'rsync',
            '-a',       # Archive 모드
            '--no-t',   # Time 변경 무시
            '--no-o',   # Owner 변경 무시 (기존 권한 유지)
            '--no-g'    # Group 변경 무시
        ] + exclude_args + [
            f"{template_dir}/",
            f"{service_dir}/"
        ]

        subprocess.run(real_cmd, check=True)

        log_info(f"[copy_template] 완료 → {service_dir}")
        return True

    except subprocess.CalledProcessError as e:
        log_error(f"[copy_template] 실패: {e.stderr}")
        return False
    except Exception as e:
        log_error(f"[copy_template] 예외 발생: {e}")
        return False

def ensure_network():
    """ai4infra 네트워크 생성 - 극단적 간결 버전"""
    cmd = ['sudo', 'docker', 'network', 'ls', '--filter', 'name=ai4infra', '--format', '{{.Name}}']
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if 'ai4infra' not in result.stdout:
        subprocess.run(['sudo', 'docker', 'network', 'create', 'ai4infra'])
        log_info("[ensure_network] ai4infra 네트워크 생성됨")
    else:
        log_debug("[ensure_network] ai4infra 네트워크 이미 존재")

def start_container(service: str):
    """단일 서비스 컨테이너 시작 - 디버깅 강화 버전"""


    service_dir = f"{BASE_DIR}/{service}"
    compose_file = f"{service_dir}/docker-compose.yml"
    
    log_debug(f"[start_container] 구동시작: service_dir={service_dir}")
    log_debug(f"[start_container] compose_file={compose_file}")

    if not os.path.exists(compose_file):
        log_error(f"[start_container] {service} docker-compose.yml 없음: {compose_file}")
        return

    ensure_network()

    cmd = ['sudo', 'ls', '-l', compose_file]
    result = subprocess.run(cmd, capture_output=True, text=True)
    log_debug(f"[start_container] 파일 권한: {result.stdout.strip()}")

    cmd = ['sudo', 'docker', 'compose', 'up', '-d']
    log_debug(f"[start_container] 실행 명령: {' '.join(cmd)} (Auto-merge overrides)")
    log_debug(f"[start_container] 작업 디렉터리: {service_dir}")

    result = subprocess.run(cmd, cwd=service_dir, capture_output=True, text=True)
    log_debug(f"[start_container] 반환코드: {result.returncode}")

    if result.returncode == 0:
        log_info(f"[start_container] {service} 컨테이너 시작됨")
    else:
        log_error(f"[start_container] {service} 시작 실패")
        log_error(f"[start_container] 오류 내용: {result.stderr}")
        log_error(f"[start_container] 출력 내용: {result.stdout}")
