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
import yaml

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
        # 사용자 존재 여부 확인
        cmd = ['id', username]
        result = subprocess.run(cmd, capture_output=True, text=True)   # stdout이 출력되므로 result로 capture
        if result.returncode == 0:
            log_debug(f"[create_user] id -> result: {result.stdout.strip()}")
            log_info(f"[create_user] 사용자 '{username}' 이미 존재, 생성을 건너뜁니다.")
            return True

        # 사용자 생성
        cmd = ['sudo', 'useradd', '-m', '-s', '/bin/bash', username]
        subprocess.run(cmd, check=True)
        log_info(f"[create_user] 사용자 '{username}' 생성 완료")

        # 비밀번호 설정
        cmd = ['sudo', 'chpasswd']
        subprocess.run(cmd, input=f"{username}:{password}", text=True, check=True)
        log_info(f"[create_user] 사용자 '{username}' 비밀번호 설정 완료")

        return True

    except subprocess.CalledProcessError as e:
        log_error(f"[create_user] 실패: {e}")
        return False

def add_sudoer(username: str, sudoers_line: str) -> bool:
    """Sudoers 설정 (멱등성 보장)

    변경이력:
    - 2025-11-05: 최초 구현 (BenKorea)
    """
    sudoers_file = f"/etc/sudoers.d/{username}-docker"
    tmp_path = f"/tmp/{username}-sudoers.tmp"

    try:
        # 이미 설정된 sudoers 파일이 존재하는지 확인
        if Path(sudoers_file).exists():
            # 동일한 라인 존재 여부 검사
            cmd = ['sudo', 'grep', '-F', sudoers_line, sudoers_file]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                log_info(f"[add_sudoer] {sudoers_file}: 이미 동일한 항목이 존재합니다.")
                return True

            # 동일한 라인이 없으면 추가
            cmd = ['sudo', 'bash', '-c', f'echo "{sudoers_line}" | tee -a {sudoers_file}']
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            log_info(f"[add_sudoer] {sudoers_file}: 새 항목 추가 완료.")
            return True

        # 파일이 없으면 새로 생성
        with open(tmp_path, 'w') as f:
            f.write(f"{sudoers_line}\n")

        for cmd in [
            ['sudo', 'mv', tmp_path, sudoers_file],
            ['sudo', 'chmod', '440', sudoers_file]
        ]:
            subprocess.run(cmd, check=True, capture_output=True, text=True)

        log_info(f"[add_sudoer] {sudoers_file}: 새 파일 생성 및 권한 설정 완료.")
        return True

    except subprocess.CalledProcessError as e:
        log_error(f"[add_sudoer] 명령 실패: {e}")
        return False
    except Exception as e:
        log_error(f"[add_sudoer] 예외 발생: {e}")
        return False

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

    log_debug(f"[stop_container] {search_pattern}: 중지 대상 -> {', '.join(containers)}")

    for c in containers:
        res = subprocess.run(['sudo', 'docker', 'stop', c], capture_output=True, text=True)
        if res.returncode == 0:
            log_info(f"[stop_container] {c} 중지 완료")
        else:
            log_error(f"[stop_container] {c} 중지 실패: {res.stderr.strip()}")

    return True

def backup_data(service: str, data_folder: str = "data") -> str:
    """서비스 데이터 폴더를 그대로 복사하여 백업"""
    src_dir = f"{BASE_DIR}/{service}/{data_folder}"
    backup_dir = f"{BASE_DIR}/backups/{service}"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst_dir = f"{backup_dir}/{data_folder}_{timestamp}"

    if not os.path.exists(src_dir):
        log_info(f"[backup_data] {service}: 백업할 데이터 없음 ({src_dir})")
        return ""

    cmds = [
        ['sudo', 'mkdir', '-p', backup_dir],
        ['sudo', 'cp', '-a', src_dir, dst_dir],
        ['sudo', 'chown', '-R', f"{os.getenv('USER')}:{os.getenv('USER')}", dst_dir],
    ]
    for cmd in cmds:
        subprocess.run(cmd, check=True)

    log_info(f"[backup_data] {service}: 복사 백업 완료 → {dst_dir}")
    return dst_dir

def copy_template(service: str) -> bool:
    """템플릿을 서비스 디렉터리로 복사 (멱등, root 권한)"""
    template_dir = f"{PROJECT_ROOT}/template/{service}"
    service_dir = f"{BASE_DIR}/{service}"

    try:
        # 대상 디렉터리 생성 (존재해도 오류 없음)
        subprocess.run(['sudo', 'mkdir', '-p', service_dir], check=True)

        # 원본 템플릿 복사 (기존 파일은 유지)
        subprocess.run(['sudo', 'cp', '-an', f"{template_dir}/.", service_dir], check=True)

        # 결과 로그
        result = subprocess.run(['sudo', 'ls', '-ld', service_dir], capture_output=True, text=True, check=True)
        log_debug(f"[copy_template] {result.stdout.strip()}")

        log_info(f"[copy_template] {service} 템플릿 복사 완료 → {service_dir}")
        return True

    except subprocess.CalledProcessError as e:
        log_error(f"[copy_template] 명령 실패: {e}")
        return False

def extract_env_vars(env_path: str, section: str) -> dict:
    """지정된 섹션(# SECTION) 아래 key=value 쌍을 추출"""
    section_header = f"# {section.upper()}"
    env_vars, in_section = {}, False

    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                in_section = False
                continue
            if line.startswith("#"):
                in_section = (line == section_header)
                continue
            if in_section and "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()
    return env_vars

def extract_config_vars(service: str) -> dict:
    """./config/{service}.yml 읽고 ${PROJECT_ROOT}, ${BASE_DIR} 치환"""
    config_path = Path(f"./config/{service}.yml")
    if not config_path.exists():
        print(f"[extract_config_vars] 설정 파일 없음: {config_path}")
        return {}

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        print(f"[extract_config_vars] YAML 파싱 실패: {e}")
        return {}

    def sub_vars(v):
        if isinstance(v, str):
            return v.replace("${PROJECT_ROOT}", PROJECT_ROOT).replace("${BASE_DIR}", BASE_DIR)
        if isinstance(v, dict):
            return {k: sub_vars(val) for k, val in v.items()}
        if isinstance(v, list):
            return [sub_vars(val) for val in v]
        return v

    return sub_vars(data)


def generate_env(service: str) -> str:
    """
    .env와 config/*.yml에서 변수 추출 후 병합하여
    BASE_DIR/service/.env.{service} 생성
    """
    env_vars = extract_env_vars(".env", service)
    config_vars = extract_config_vars(service)
    merged = {**env_vars, **config_vars}

    service_dir = Path(f"{BASE_DIR}/{service}")
    output_file = service_dir / f".env.{service}"

    if not service_dir.exists():
        print(f"[generate_env_file] 경로 없음: {service_dir}")
        return ""

    with open(output_file, "w", encoding="utf-8") as f:
        for k, v in merged.items():
            f.write(f"{k}={v}\n")

    print(f"[generate_env_file] {service.upper()} 환경파일 생성 완료 → {output_file}")
    return str(output_file)
    



def install_bitwarden() -> bool:
    """Bitwarden 설치 여부 확인 후 필요 시 수동 설치 안내"""
    bitwarden_dir = f"{BASE_DIR}/bitwarden"
    bitwarden_script = f"{bitwarden_dir}/bitwarden.sh"
    compose_file = f"{bitwarden_dir}/bwdata/docker/docker-compose.yml"

    try:
        # 1️⃣ 설치 여부 점검
        if Path(bitwarden_script).exists() and Path(compose_file).exists():
            log_info("[install_bitwarden] Bitwarden이 이미 설치되어 있습니다. 다음 단계로 진행합니다.")
            return True

        # 2️⃣ 설치 스크립트 존재 여부 확인
        if not Path(bitwarden_script).exists():
            log_error(f"[install_bitwarden] 설치 스크립트를 찾을 수 없습니다: {bitwarden_script}")
            return False

        # 3️⃣ 설치 스크립트 실행권한 부여
        subprocess.run(['sudo', 'chmod', '+x', bitwarden_script], check=True)

        # 4️⃣ 사용자 수동 설치 안내
        instructions = (
            "Bitwarden이 설치되어 있지 않습니다.\n\n"
            "수동 설치 절차를 다른 터미널에서 실행한 뒤, 이 터미널로 돌아와 Enter를 눌러 계속하세요:\n\n"
            "1) 권장(권한 보존): bitwarden 계정으로 전환하여 설치\n"
            "   sudo -i -u bitwarden\n"
            f"   cd {bitwarden_dir}\n"
            "   sudo ./bitwarden.sh install\n\n"
            "2) 간단(루트로 직접 실행):\n"
            f"   sudo {bitwarden_script} install\n\n"
            "설치 후 파일 소유권이 root로 생성된 경우 소유자 복구:\n"
            f"   sudo chown -R bitwarden:bitwarden {bitwarden_dir}\n\n"
            "설치를 완료한 뒤 이 터미널로 돌아와 Enter를 눌러 계속하세요."
        )
        log_info(f"[install_bitwarden] 수동 설치 안내:\n{instructions}")

        input("설치 완료 후 Enter를 눌러 계속합니다...")

        # 5️⃣ 설치 완료 여부 재확인
        if Path(compose_file).exists():
            log_info("[install_bitwarden] Bitwarden 설치 완료가 감지되었습니다. 다음 단계로 진행합니다.")
            return True
        else:
            log_error("[install_bitwarden] 설치 완료가 확인되지 않았습니다. 수동 확인이 필요합니다.")
            return False

    except KeyboardInterrupt:
        log_info("[install_bitwarden] 사용자가 설치 절차를 중단함")
        return False
    except subprocess.CalledProcessError as e:
        log_error(f"[install_bitwarden] 명령 실패: {e}")
        return False
    except Exception as e:
        log_error(f"[install_bitwarden] 예외 발생: {e}")
        return False

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
