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
            log_debug(f"[create_user] id {username} -> result: {result.stdout.strip()}")
            log_info(f"[create_user] 사용자 '{username}' 이미 존재, 생성을 건너뜁니다.")
            return True

        # 사용자 생성
        cmd = ['sudo', 'useradd', '-m', '-s', '/bin/bash', username]
        subprocess.run(cmd, check=True)
        log_info(f"[create_user] useradd result -> '{username}' 생성 완료")

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

def backup_data(service: str, data_folder: str = None) -> str:
    """서비스 디렉터리 전체를 백업 (docker-compose.yml 제외)
    
    변경사항:
    - 기존: 특정 폴더(data/file/bwdata)만 백업
    - 개선: 서비스 디렉터리 전체 백업 (설정, 인증서 포함)
    - 제외: docker-compose.yml, logs/, .env.* (재생성 가능)
    
    변경이력:
    - 2025-11-16: 전체 백업으로 개선 (BenKorea)
    """
    src_dir = f"{BASE_DIR}/{service}"
    backup_dir = f"{BASE_DIR}/backups/{service}"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst_dir = f"{backup_dir}/{service}_{timestamp}"

    if not os.path.exists(src_dir):
        log_info(f"[backup_data] {service}: 백업할 디렉터리 없음 ({src_dir})")
        return ""

    try:
        # 백업 디렉터리 생성
        subprocess.run(['sudo', 'mkdir', '-p', backup_dir], check=True)
        
        # rsync로 선택적 백업 (제외 패턴 지정)
        cmd = [
            'sudo', 'rsync', '-a',
            '--exclude', 'docker-compose.yml',
            '--exclude', 'logs/',
            '--exclude', '.env',           # .env 파일 제외
            '--exclude', '*.log',
            f"{src_dir}/",
            f"{dst_dir}/"
        ]
        subprocess.run(cmd, check=True)
        
        # 소유권 변경 (bitwarden은 원본 소유권 유지, 나머지는 현재 사용자)
        if service == 'bitwarden':
            # Bitwarden은 원본 소유권(bitwarden:bitwarden) 유지
            log_debug(f"[backup_data] {service}: 원본 소유권 유지 (bitwarden:bitwarden)")
        else:
            # 다른 서비스는 현재 사용자 소유로 변경 (편의성)
            subprocess.run(['sudo', 'chown', '-R', f"{os.getenv('USER')}:{os.getenv('USER')}", dst_dir], check=True)
            log_debug(f"[backup_data] {service}: 소유권 변경 → {os.getenv('USER')}")
        
        log_info(f"[backup_data] {service}: 전체 백업 완료 → {dst_dir}")
        return dst_dir
        
    except subprocess.CalledProcessError as e:
        log_error(f"[backup_data] {service}: 백업 실패 - {e}")
        return ""

def copy_template(service: str) -> bool:
    """템플릿을 서비스 디렉터리로 복사 (멱등, root 권한)"""
    template_dir = f"{PROJECT_ROOT}/template/{service}"
    service_dir = f"{BASE_DIR}/{service}"

    try:
        # 대상 디렉터리 생성 (존재해도 오류 없음)
        cmd = ['sudo', 'mkdir', '-p', service_dir]
        subprocess.run(cmd, check=True)

        # 원본 템플릿 복사 (기존 파일은 유지)
        cmd = ['sudo', 'cp', '-a', '--update=none', f"{template_dir}/.", service_dir]
        subprocess.run(cmd, check=True)

        # 결과 로그
        cmd = ['sudo', 'ls', '-l', service_dir]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        log_debug(f"[copy_template] cp result -> {result.stdout.strip()}")
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
        log_info (f"[extract_config_vars] 설정 파일 없음: {config_path}")
        return {}

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        log_info(f"[extract_config_vars] YAML 파싱 실패: {e}")
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
    output_file = service_dir / f".env"

    if not service_dir.exists():
        log_info(f"[generate_env_file] 경로 없음: {service_dir}")
        return ""

    with open(output_file, "w", encoding="utf-8") as f:
        for k, v in merged.items():
            f.write(f"{k}={v}\n")

    log_info(f"[generate_env_file] {service.upper()} 환경파일 생성 완료 → {output_file}")
    return str(output_file)

def setup_usb_secrets() -> bool:
    """USB 경로에 암호화된 비밀번호 파일 배포
    
    동작:
    - /mnt/usb 디렉터리 생성
    - template/usb의 *.enc 파일을 /mnt/usb로 복사 (비어있을 경우만)
    - 파일 권한을 600으로 설정 (소유자만 읽기 가능)
    
    반환:
    - True: 성공
    - False: 실패
    
    변경이력:
    - 2025-11-15: 최초 구현 (BenKorea)
    """
    usb_dir = "/mnt/usb"
    template_usb = f"{PROJECT_ROOT}/template/usb"
    
    try:
        # 마운트 포인트 생성
        cmd = ['sudo', 'mkdir', '-p', usb_dir]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        log_debug(f"[setup_usb_secrets] {usb_dir} 디렉터리 생성 완료")
        
        # USB 디렉터리가 비어있는지 확인
        cmd = ['sudo', 'ls', '-A', usb_dir]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        is_empty = not result.stdout.strip()
        
        if is_empty:
            # 템플릿 복사 (실제 USB 미마운트 시)
            cmd = ['sudo', 'cp', '-a', f"{template_usb}/.", usb_dir]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            log_info(f"[setup_usb_secrets] USB 템플릿 복사 완료 → {usb_dir}")
            
            # 권한 설정 (600: 소유자만 읽기/쓰기)
            cmd = ['sudo', 'find', usb_dir, '-name', '*.enc', '-exec', 'chmod', '600', '{}', ';']
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            log_info(f"[setup_usb_secrets] *.enc 파일 권한 설정 완료 (600)")
        else:
            log_info(f"[setup_usb_secrets] {usb_dir}에 이미 파일이 존재하므로 복사를 건너뜁니다.")
        
        # 파일 목록 확인
        cmd = ['sudo', 'ls', '-lh', usb_dir]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        log_debug(f"[setup_usb_secrets] {usb_dir} 내용:\n{result.stdout.strip()}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        log_error(f"[setup_usb_secrets] 명령 실패: {e}")
        if e.stderr:
            log_error(f"[setup_usb_secrets] stderr: {e.stderr}")
        return False
    except Exception as e:
        log_error(f"[setup_usb_secrets] 예외 발생: {e}")
        return False
    
def install_bitwarden() -> bool:
    """Bitwarden 설치 여부 확인 후 필요 시 수동 설치 안내"""
    bitwarden_dir = f"{BASE_DIR}/bitwarden"
    bitwarden_script = f"{bitwarden_dir}/bitwarden.sh"
    compose_file = f"{bitwarden_dir}/bwdata/docker/docker-compose.yml"
    bwdata_dir = f"{bitwarden_dir}/bwdata"
    bwdata_tmp = f"{bitwarden_dir}/bwdata.template"

    try:
        # 설치 여부 점검
        if Path(bitwarden_script).exists() and Path(compose_file).exists():
            log_info("[install_bitwarden] {bitwarden_script} & {compose_file}이 존재하므로 Bitwarden이 이미 설치되어 있다 판단하고, 다음 단계 start로 진행합니다.")
            return True

        # 설치 스크립트 존재 여부 확인
        if not Path(bitwarden_script).exists():
            log_error(f"[install_bitwarden] 설치 스크립트를 찾을 수 없습니다: {bitwarden_script}")
            return False

        # 설치 스크립트 실행권한 부여
        cmd = ['sudo', 'chmod', '+x', bitwarden_script]
        subprocess.run(cmd, check=True)
        cmd = ['sudo', 'ls', '-l', bitwarden_script]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            log_debug(f"[install_bitwarden] chmod -> result: {result.stdout.strip()}")

        # bitwarden 폴더 전체 권한 bitwarden 계정으로 소유권 변경
        cmd = ['sudo', 'chown', '-R', 'bitwarden:bitwarden', bitwarden_dir]
        subprocess.run(cmd, check=False)
        log_info(f"[install_bitwarden] {bitwarden_dir} 소유권을 bitwarden:bitwarden 으로 변경")
        cmd = ['sudo', 'ls', '-l', bitwarden_dir]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        log_debug(f"[install_bitwarden] {bitwarden_dir} chown -> {result.stdout.strip()}")

        # 기존 bwdata 폴더를 임시로 이동 (설치 중 충돌 방지)
        if Path(bwdata_dir).exists():
            cmd = ['sudo', 'mv', bwdata_dir, bwdata_tmp]
            result = subprocess.run(cmd, check=True)
            if result.returncode == 0:
                log_info(f"[install_bitwarden] 기존 bwdata 디렉터리를 임시로 이동: {bwdata_tmp}")

        # 사용자 수동 설치 안내
        instructions = (
            "Bitwarden이 설치되어 있지 않습니다.\n\n"
            "다른 터미널에서 다음 명령을 bitwarden 계정으로 실행하세요:\n\n"
            f"   sudo -su bitwarden\n"
            f"   cd {bitwarden_dir}\n"
            f"   sudo ./bitwarden.sh install\n\n"
            "설치가 완료되면 이 터미널로 돌아와 Enter를 눌러 계속합니다.\n"
        )
        log_info(f"[install_bitwarden] 수동 설치 안내:\n{instructions}")
        input("설치 완료 후 Enter를 눌러 계속합니다...")

        # 설치 완료 후 compose 파일 존재 확인
        if Path(compose_file).exists():
            log_info("[install_bitwarden] bitwarden.sh 스크립트가 설치되었으므로 다음 단계를 진행합니다.")

            # 기존 템플릿의 bwdata 파일 복원 (override 등)
            if Path(bwdata_tmp).exists():
                cmd = ['sudo', 'cp', '-a', '--update=none', f"{bwdata_tmp}/.", bwdata_dir]
                subprocess.run(cmd, check=False)
                cmd = ['sudo', 'ls', '-lR', bwdata_dir]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                log_debug(f"[install_bitwarden] bwdata 복원 -> result: {result.stdout.strip()}")
                log_debug(f"[install_bitwarden] 템플릿 bwdata 복원 완료")
                
                cmd = ['sudo', 'rm', '-rf', bwdata_tmp]
                subprocess.run(cmd, check=False)
                log_info(f"[install_bitwarden] 템플릿 임시 디렉터리 제거 완료")

            # 소유권 재조정 (nobody → bitwarden 변경)
            log_info(f"[install_bitwarden] {bitwarden_dir} 전체 소유권을 bitwarden:bitwarden 으로 재조정 시작")
            cmd = ['sudo', 'chown', '-R', 'bitwarden:bitwarden', bitwarden_dir]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            cmd = ['sudo', 'ls', '-lR', bitwarden_dir]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                log_debug(f"[install_bitwarden] chown 재조정 -> result: {result.stdout.strip()}")
                log_info(f"[install_bitwarden] 소유권 재조정 완료")
                
            else:
                log_error(f"[install_bitwarden] 소유권 재조정 실패: {result.stderr}")

            return True
            
        else:
            log_error("[install_bitwarden] bitwarden.sh 파일이 확인되지 않았습니다. 수동 확인이 필요합니다.")
            # 실패 시 임시폴더 원복
            if Path(bwdata_tmp).exists() and not Path(bwdata_dir).exists():
                cmd = ['sudo', 'mv', bwdata_tmp, bwdata_dir]
                subprocess.run(cmd, check=False)
                log_info(f"[install_bitwarden] bwdata 디렉터리를 원래 위치로 복구했습니다.")
            return False

    except KeyboardInterrupt:
        log_info("[install_bitwarden] 사용자가 설치 절차를 중단함")
        # 복구 처리
        if Path(bwdata_tmp).exists() and not Path(bwdata_dir).exists():
            cmd = ['sudo', 'mv', bwdata_tmp, bwdata_dir]
            subprocess.run(cmd, check=False)
        return False

    except subprocess.CalledProcessError as e:
        log_error(f"[install_bitwarden] 명령 실패: {e}")
        if Path(bwdata_tmp).exists() and not Path(bwdata_dir).exists():
            cmd = ['sudo', 'mv', bwdata_tmp, bwdata_dir]
            subprocess.run(cmd, check=False)
        return False

    except Exception as e:
        log_error(f"[install_bitwarden] 예외 발생: {e}")
        if Path(bwdata_tmp).exists() and not Path(bwdata_dir).exists():
            cmd = ['sudo', 'mv', bwdata_tmp, bwdata_dir]
            subprocess.run(cmd, check=False)
        return False

def bitwarden_start():
    bitwarden_dir = f"{BASE_DIR}/bitwarden"
    bitwarden_script = f"{bitwarden_dir}/bitwarden.sh"

    instructions = (
            "Bitwarden을 수동으로 시작해 주세요 (설치 시와 같은 터미널에서):\n"
            f"  sudo ./bitwarden.sh start\n\n"
            "시작 후 원래 터미널로 돌아와 Enter를 눌러 계속하세요."
        )
    log_info(f"[bitwarden_start] 수동 시작 안내:\n{instructions}")

    try:
        input("수동 시작 후 Enter를 눌러 계속합니다...")
    except KeyboardInterrupt:
        log_info("[bitwarden_start] 사용자가 중단함")
        return False

    log_info("[bitwarden_start] 사용자가 수동 시작함")

    # 소유권 재조정 (nobody → bitwarden 변경)
    log_info(f"[install_bitwarden] {bitwarden_dir} 전체 소유권을 bitwarden:bitwarden 으로 재조정 시작")
    cmd = ['sudo', 'chown', '-R', 'bitwarden:bitwarden', bitwarden_dir]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    cmd = ['sudo', 'ls', '-lR', bitwarden_dir]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        log_debug(f"[install_bitwarden] chown 재조정 -> result: {result.stdout.strip()}")
        log_info(f"[install_bitwarden] 소유권 재조정 완료")
                
        # nobody 소유 파일 남았는지 확인
        cmd = ['sudo', 'find', bitwarden_dir, '-user', 'nobody', '-o', '-user', 'root']
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.stdout.strip():
            log_debug(f"[install_bitwarden] ⚠️ 비정상 소유 파일 발견:\n{result.stdout[:500]}")
        else:
            log_debug(f"[install_bitwarden] ✓ 모든 파일이 bitwarden 소유로 변경됨")


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
        cmd = ['sudo', 'ls', '-l', compose_file]
        result = subprocess.run(cmd, capture_output=True, text=True)
        log_debug(f"[start_container] 파일 권한: {result.stdout.strip()}")
    
        # docker compose 버전 확인 (sudo 사용)
        cmd = ['sudo', 'docker', 'compose', 'version']
        result = subprocess.run(cmd, capture_output=True, text=True)
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

