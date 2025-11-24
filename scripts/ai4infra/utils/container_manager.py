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

import json
import sys
import os
import re
import time
import yaml

from dotenv import load_dotenv
from common.load_config import load_config
from common.logger import log_debug, log_error, log_info, log_warn

load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT")
BASE_DIR = os.getenv('BASE_DIR', '/opt/ai4infra')
SERVICES = ['postgres', 'vault', 'elk', 'ldap', 'bitwarden']

def create_user(username: str, password: str = "bit") -> bool:
    """
    지정된 시스템 사용자 생성

    주요단계:
    1) `id {username}` 명령으로 사용자 존재 여부를 확인합니다.
    2) 사용자가 존재하지 않으면 `useradd -m -s /bin/bash {username}`으로 생성합니다.
    3) `chpasswd` 명령을 이용해 비밀번호를 설정합니다.

    Parameters
    ----------
    username : str
        생성할 사용자 계정 이름.
    password : str, optional
        새 계정에 설정할 초기 비밀번호. 기본값은 "bit"입니다.

    Returns
    -------
    bool
        생성 여부와 관계없이 사용자가 존재하는 경우 True를 반환하고,  
        생성 시도 후 성공한 경우에도 True를 반환합니다.  
        명령 실행 오류가 발생하면 False를 반환합니다.

    Raises
    ------
    None
        시스템 명령 실행 실패는 False 반환으로 처리하며 예외를 전달하지 않습니다.

    Notes
    -----
    - 이 함수는 내부 로깅을 수행하며, 반환값을 기반으로 호출자가 다음 단계를 진행할지 결정하는 구조입니다.
    - 사용자 계정은 홈 디렉터리(`/home/{username}`)와 Bash 셸(`/bin/bash`)을 기본 구성으로 생성합니다.
    - 보안 이유로 비밀번호 설정은 로컬 `chpasswd` 명령을 사용합니다.

    Future Considerations
    ---------------------
    - 타 컨테이너 서비스(PostgreSQL, ELK 등)도 독립 계정이 필요한 경우 uid/gid 매핑 전략을 추가 검토할 수 있습니다.
    - 외부에서 비밀번호를 안전하게 주입하기 위한 별도 인터페이스 또는 Vault 연동이 필요할 수 있습니다.

    History
    -------
    2025-11-18 : Doc-string 수정 (BenKorea)
    """

    try:
        # 1) 사용자 존재 여부 확인
        cmd = ['id', username]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            log_debug(f"[create_user] id {username} → result: {result.stdout.strip()}")
            log_info(f"[create_user] 동일한 id 존재, 이 단계를 건너뜁니다.")
            return True

        # 2) 존재하지 않으면 `useradd`로 사용자 생성
        cmd = ['sudo', 'useradd', '-m', '-s', '/bin/bash', username]
        subprocess.run(cmd, check=True)
        log_info(f"[create_user] useradd result → '{username}' 생성 완료")

        # 3) 비밀번호 설정
        cmd = ['sudo', 'chpasswd']
        subprocess.run(cmd, input=f"{username}:{password}", text=True, check=True)
        log_info(f"[create_user] 사용자 '{username}' 비밀번호 설정 완료")
        return True

    except subprocess.CalledProcessError as e:
        log_error(f"[create_user] 실패: {e}")
        return False

def add_docker_group(user: str):
    """사용자를 docker 그룹에 추가 (이미 속해 있으면 건너뜀)"""
    try:
        # 현재 그룹 확인
        cmd = ['groups', user]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        current_groups = result.stdout.strip()        
        if 'docker' in current_groups.split():
            log_info(f"[add_docker_group] {user} 사용자가 이미 docker 그룹에 속해 있습니다.")
            return True
        
        # docker 그룹에 추가
        subprocess.run(['sudo', 'usermod', '-aG', 'docker', user], check=True)
        log_info(f"[add_docker_group] {user} 사용자를 docker 그룹에 추가했습니다.")
        return True
    
    except subprocess.CalledProcessError as e:
        log_error(f"[add_docker_group] 실패: {e.stderr if e.stderr else str(e)}")
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

    for c in containers:
        result = subprocess.run(['sudo', 'docker', 'stop', c], capture_output=True, text=True)
        if result.returncode == 0:
            log_info(f"[stop_container] {c} 중지 완료")
        else:
            log_error(f"[stop_container] {c} 중지 실패: {result.stderr.strip()}")

    return True

def get_service_data_dir(service: str) -> str:
    """
    config/<service>.yml에서 데이터 디렉터리 경로를 추출합니다.
    
    추출 규칙:
      - postgres: PG_DATA_DIR
      - vault: VAULT_FILE_DIR
      - ldap: LDAP_DATA_DIR
      - bitwarden: {BASE_DIR}/bitwarden/bwdata (설정 파일 없음)
      - 기타: {BASE_DIR}/{service}/data (기본값)
    
    Returns
    -------
    str
        데이터 디렉터리 절대 경로
    """
    
    # Bitwarden은 설정 파일이 없으므로 하드코딩
    if service == "bitwarden":
        return f"{BASE_DIR}/{service}/bwdata"
    
    # config/<service>.yml에서 추출
    config_vars = extract_config_vars(service)
    
    # 서비스별 데이터 디렉터리 키 매핑
    data_dir_keys = {
        'postgres': 'PG_DATA_DIR',
        'vault': 'VAULT_FILE_DIR',
        'ldap': 'LDAP_DATA_DIR',
        'elk': 'ELK_DATA_DIR',
    }
    
    key = data_dir_keys.get(service)
    if key and key in config_vars:
        return config_vars[key]
    
    # 기본값: {BASE_DIR}/{service}/data
    log_debug(f"[get_service_data_dir] {service}: 설정 없음, 기본 경로 사용")
    return f"{BASE_DIR}/{service}/data"

def backup_data(service: str, data_folder: str = None) -> str:
    """
    서비스의 data 디렉터리만 백업합니다.
    
    데이터 경로는 config/<service>.yml에서 자동 추출:
      - postgres: PG_DATA_DIR
      - vault: VAULT_FILE_DIR
      - ldap: LDAP_DATA_DIR
      - bitwarden: {BASE_DIR}/bitwarden/bwdata
      - 기타: {BASE_DIR}/{service}/data
    
    백업 결과는 BASE_DIR/backups/{service}/{service}_{timestamp} 에 저장됩니다.

    Returns
    -------
    str
        백업이 저장된 디렉터리 경로. 실패 시 빈 문자열.
    """
    
    # config/<service>.yml에서 데이터 디렉터리 추출
    src_dir = get_service_data_dir(service)
    
    backup_dir = f"{BASE_DIR}/backups/{service}"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst_dir = f"{backup_dir}/{service}_{timestamp}"

    if not os.path.exists(src_dir):
        log_info(f"[backup_data] {service}: 백업할 data 디렉터리 없음 ({src_dir})")
        return ""

    try:
        # 백업 디렉터리 생성
        subprocess.run(['sudo', 'mkdir', '-p', backup_dir], check=True)

        # 권한/소유권을 그대로 보존하여 data 디렉터리만 백업
        cmd = [
            'sudo', 'rsync', '-a', '--numeric-ids',
            f"{src_dir}/", f"{dst_dir}/"
        ]
        subprocess.run(cmd, check=True)

        log_info(f"[backup_data] {service}: data 백업 완료 → {dst_dir}")
        return dst_dir

    except subprocess.CalledProcessError as e:
        log_error(f"[backup_data] {service}: 백업 실패 - {e}")
        return ""

def restore_data(service: str, backup_path: str) -> bool:
    """
    백업된 데이터를 서비스 디렉터리로 복원합니다.
    
    복원 경로는 config/<service>.yml에서 자동 추출:
      - postgres: PG_DATA_DIR
      - vault: VAULT_FILE_DIR
      - ldap: LDAP_DATA_DIR
      - bitwarden: {BASE_DIR}/bitwarden/bwdata
      - 기타: {BASE_DIR}/{service}/data
    
    Parameters
    ----------
    service : str
        복원할 서비스 이름
    backup_path : str
        백업 디렉터리 경로
    
    Returns
    -------
    bool
        복원 성공 시 True, 실패 시 False
    """
    
    # 백업 경로 존재 확인
    if not os.path.exists(backup_path):
        log_error(f"[restore_data] 백업 경로 없음: {backup_path}")
        return False
    
    # config/<service>.yml에서 복원 대상 디렉터리 추출
    restore_target = get_service_data_dir(service)
    
    try:
        # 복원 대상 디렉터리 생성
        subprocess.run(['sudo', 'mkdir', '-p', restore_target], check=True)
        
        # rsync로 복원 (권한/소유권 완전 보존)
        cmd = [
            'sudo', 'rsync', '-a', '--numeric-ids',
            f"{backup_path}/", f"{restore_target}/"
        ]
        subprocess.run(cmd, check=True)
        
        log_info(f"[restore_data] {service}: 데이터 복원 완료 → {backup_path} → {restore_target}")
        return True
        
    except subprocess.CalledProcessError as e:
        log_error(f"[restore_data] {service}: 복원 실패 - {e}")
        return False

def copy_template(service: str) -> bool:
    """
    템플릿을 BASE_DIR/<service>로 복사한다.
    owner/group/timestamp 차이는 무시하고
    파일 내용 기반으로만 변경 여부를 판단한다.
    """
    template_dir = f"{PROJECT_ROOT}/template/{service}"
    service_dir = f"{BASE_DIR}/{service}"

    try:
        subprocess.run(['sudo', 'mkdir', '-p', service_dir], check=True)

        exclude_args = []

        # Bitwarden bwdata 제외
        if service == "bitwarden":
            exclude_args.extend([
                '--exclude', 'bwdata/',
                '--exclude', 'bwdata/**',
                '--exclude', 'bwdata/*',
            ])

        # Postgres override 제외
        if service == "postgres":
            exclude_args.extend([
                '--exclude', 'docker-compose.override.yml',
            ])

        # -------------------------------------
        # dry-run 명령 (real_cmd와 동일 + --dry-run)
        # -------------------------------------
        dry_cmd = [
            'sudo', 'rsync',
            '-a', '-i',
            '--no-t', '--no-o', '--no-g',
            '--dry-run'
        ] + exclude_args + [
            f"{template_dir}/",
            f"{service_dir}/"
        ]

        dry_run = subprocess.run(dry_cmd, capture_output=True, text=True, check=True)
        changed = dry_run.stdout.strip()

        if not changed:
            log_info(f"[copy_template] {service_dir}: 변경 사항 없음")
            return True

        log_debug(f"[copy_template] 변경 감지됨 (dry-run 결과):\n{changed}")

        # -------------------------------------
        # 실제 복사 명령 (dry-run과 동일 + --dry-run 제거)
        # -------------------------------------
        real_cmd = [
            'sudo', 'rsync',
            '-a',
            '--no-t', '--no-o', '--no-g'
        ] + exclude_args + [
            f"{template_dir}/",
            f"{service_dir}/"
        ]

        subprocess.run(real_cmd, check=True)

        log_info(f"[copy_template] 변경 반영 완료 → {service_dir}")
        return True

    except subprocess.CalledProcessError as e:
        log_error(f"[copy_template] 실패: {e.stderr}")
        return False
    except Exception as e:
        log_error(f"[copy_template] 예외 발생: {e}")
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
        log_info (f"[extract_config_vars] 해당서비스명.yml 파일 없음: {config_path}")
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
    BASE_DIR/service/.env 생성.

    개선 사항:
    - merged 내용이 비어 있으면 .env 생성하지 않음
    - 소유권은 bitwarden만 bitwarden:bitwarden
      그 외 서비스는 root 소유 유지
    """
    # 변수 추출
    env_vars = extract_env_vars(".env", service)
    config_vars = extract_config_vars(service)
    merged = {**env_vars, **config_vars}

    service_dir = Path(f"{BASE_DIR}/{service}")
    output_file = service_dir / ".env"

    if not service_dir.exists():
        log_info(f"[generate_env] 경로 없음: {service_dir}")
        return ""

    # merged가 비어 있으면 파일 생성할 필요 없음
    if not merged:
        log_info(f"[generate_env] {service} 환경변수 없음 → .env 생성 생략")
        return ""

    # 임시 파일에 작성
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as tmp:
        for k, v in merged.items():
            tmp.write(f"{k}={v}\n")
        tmp_path = tmp.name

    try:
        # sudo로 이동
        subprocess.run(
            ["sudo", "mv", tmp_path, str(output_file)],
            check=True,
            capture_output=True,
            text=True
        )

        # 소유권 결정
        # 비트워든만 bitwarden 사용자, 나머지는 root
        owner = "bitwarden" if service == "bitwarden" else "root"

        subprocess.run(
            ["sudo", "chown", f"{owner}:{owner}", str(output_file)],
            check=True,
            capture_output=True,
            text=True
        )

        # 권한 설정
        subprocess.run(
            ["sudo", "chmod", "600", str(output_file)],
            check=True,
            capture_output=True,
            text=True
        )

        log_info(
            f"[generate_env] {service.upper()} .env 생성 완료 → {output_file} "
            f"(소유자: {owner})"
        )

    except subprocess.CalledProcessError as e:
        log_error(f"[generate_env] 파일 이동/권한 설정 실패: {e.stderr}")
        if Path(tmp_path).exists():
            os.unlink(tmp_path)
        return ""

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
    """
    Bitwarden 설치 여부만 확인하고,
    설치되지 않은 경우 사용자에게 수동 설치를 안내하는 최소 버전.

    - 이미 설치되어 있으면 바로 True 반환
    - 설치되지 않았으면 bitwarden 계정으로 설치 안내
    - 설치 완료 여부만 확인 후 종료
    """
    bitwarden_dir = f"{BASE_DIR}/bitwarden"
    bitwarden_script = f"{bitwarden_dir}/bitwarden.sh"
    compose_file = f"{bitwarden_dir}/bwdata/docker/docker-compose.yml"

    # 1) 이미 설치되어 있는지 검사 (bitwarden.sh + compose 파일)
    if Path(bitwarden_script).exists() and Path(compose_file).exists():
        log_info("[install_bitwarden] Bitwarden이 이미 설치되어 있습니다.")
        return True

    # 2) 사용자에게 설치 안내 (설치스크립트 존재 여부는 체크하지 않음)
    instructions = (
        "Bitwarden이 설치되어 있지 않으므로 수동설치를 진행하세요.\n\n"
        "다른 터미널에서 다음 명령을 실행해 설치하십시오:\n\n"
        f"   sudo -su bitwarden\n"
        f"   cd {bitwarden_dir}\n"
        f"   ./bitwarden.sh install\n\n"
        "설치가 완료되면 이 터미널로 돌아와 Enter 키를 눌러 계속합니다.\n"
    )
    log_info(instructions)
    input("설치 완료 후 Enter 키를 눌러 계속합니다...")

    # 3) 설치 완료 여부 확인
    if Path(compose_file).exists():
        log_info("[install_bitwarden] Bitwarden 설치가 완료되었습니다.")
        return True
    else:
        log_error("[install_bitwarden] 설치가 완료되지 않았습니다. 수동 확인이 필요합니다.")
        return False

def apply_override(service: str) -> bool:
    """
    Bitwarden용 docker-compose.override.yml 적용.

    동작:
      - 템플릿이 없으면 패스
      - Bitwarden이 설치 완료된 경우(bwdata/docker 존재)만 적용
      - 기존 override가 있으면 덮어쓰지 않음
      - 소유권/권한은 Bitwarden 설치 스크립트 정책 그대로 유지
    """
    if service != "bitwarden":
        log_debug(f"[apply_override] {service}: override 적용 대상 아님")
        return True

    src = Path(f"{PROJECT_ROOT}/template/bitwarden/bwdata/docker/docker-compose.override.yml")
    dst = Path(f"{BASE_DIR}/bitwarden/bwdata/docker/docker-compose.override.yml")

    if not src.exists():
        log_info(f"[apply_override] Bitwarden override 템플릿 없음: {src}")
        return True

    # Bitwarden 설치가 정상적으로 완료되었을 때만 bwdata/docker 경로가 생성됨
    if not dst.parent.exists():
        log_debug("[apply_override] Bitwarden 설치 전이므로 override 적용 생략")
        return True

    if dst.exists():
        log_info(f"[apply_override] override 이미 존재, 유지함: {dst}")
        return True

    try:
        subprocess.run(
            ["sudo", "mkdir", "-p", str(dst.parent)],
            check=True, capture_output=True, text=True
        )

        subprocess.run(
            ["sudo", "cp", "-a", str(src), str(dst)],
            check=True, capture_output=True, text=True
        )

        log_info(f"[apply_override] override 적용 완료 → {dst}")
        return True

    except subprocess.CalledProcessError as e:
        log_error(f"[apply_override] override 적용 실패: {e.stderr}")
        return False

def bitwarden_start():
    bitwarden_dir = f"{BASE_DIR}/bitwarden"
    bitwarden_script = f"{bitwarden_dir}/bitwarden.sh"

    instructions = (
        "Bitwarden 계정에서 설치폴더에서 다음 명령어로 수동 시작하세요:\n\n"
        f"   ./bitwarden.sh start\n"
    )
    log_info(f"[bitwarden_start] 수동 시작 안내:\n{instructions}")

    try:
        input("수동 시작 후 Enter를 눌러 계속합니다...")
    except KeyboardInterrupt:
        log_info("[bitwarden_start] 사용자가 중단함")
        return False

    log_info("[bitwarden_start] Enter 키가 입력 되었으며 다음 단계로 진행합니다.")
    return True

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
    
        # 실행 명령어 로깅 (sudo 추가)
        cmd = ['sudo', 'docker', 'compose', '-f', compose_file, 'up', '-d']
        log_debug(f"[start_container] 실행 명령: {' '.join(cmd)}")
        log_debug(f"[start_container] 작업 디렉터리: {service_dir}")
    
        # 컨테이너 시작 (sudo 사용)
        result = subprocess.run(cmd, cwd=service_dir, capture_output=True, text=True)
        log_debug(f"[start_container] 반환코드: {result.returncode}")

    
        if result.returncode == 0:
            log_info(f"[start_container] {service} 컨테이너 시작됨")
        else:
            log_error(f"[start_container] {service} 시작 실패")
            log_error(f"[start_container] 오류 내용: {result.stderr}")
            log_error(f"[start_container] 출력 내용: {result.stdout}")

def check_container(service: str, custom_check=None) -> bool:
    """
    AI4INFRA 간결 체크 버전
    - Bitwarden: ai4infra-bitwarden-* 모든 컨테이너 health 종합 판단
    - Vault:    health 없음 → Up 이면 PASS
    - 기타:     Up 상태면 PASS
    """

    # 1) Bitwarden만 prefix 매칭 필요
    if service == "bitwarden":
        filter_name = "ai4infra-bitwarden-"
    else:
        filter_name = f"ai4infra-{service}"

    log_info(f"[check_container] 점검 시작 → {service} ({filter_name}*)")

    # 최대 120초(초기화 대기)
    for attempt in range(120):
        ps = subprocess.run(
            f"sudo docker ps --filter name={filter_name} --format '{{{{.Status}}}}'",
            shell=True, text=True, capture_output=True
        )
        statuses = ps.stdout.strip().splitlines()

        # 1) 컨테이너 없음
        if not statuses:
            log_warn(f"[check_container] 컨테이너 없음 → 재시도 ({attempt+1}/120)")
            time.sleep(1)
            continue

        # ------------------------------------------------------------------
        # Bitwarden: 여러 컨테이너의 health를 종합적으로 판단
        # ------------------------------------------------------------------
        if service == "bitwarden":
            low = ps.stdout.lower()

            if "unhealthy" in low:
                log_error("[check_container] Bitwarden unhealthy 감지 → 실패")
                return False
            if "starting" in low:
                log_info(f"[check_container] Bitwarden 초기화 중 → 재시도 ({attempt+1}/120)")
                time.sleep(1)
                continue

            # starting 없음 + unhealthy 없음 = 정상
            log_info("[check_container] Bitwarden health 정상")
            break

        # ------------------------------------------------------------------
        # Vault: 단순히 Up 상태면 PASS
        # ------------------------------------------------------------------
        elif service == "vault":
            if any("up" in s.lower() for s in statuses):
                break
            log_info(f"[check_container] Vault 대기중 → 재시도 ({attempt+1}/120)")
            time.sleep(1)
            continue

        # ------------------------------------------------------------------
        # 기타 서비스: 단일 컨테이너 Up 확인
        # ------------------------------------------------------------------
        else:
            if any("up" in s.lower() for s in statuses):
                break
            log_info(f"[check_container] {service} 준비중 → 재시도 ({attempt+1}/120)")
            time.sleep(1)
            continue

    else:
        log_error(f"[check_container] {service}: 상태 정상화 실패")
        return False

    # ----------------------------------------------------------------------
    # 로그 검사 (간결)
    # ----------------------------------------------------------------------
    logs = subprocess.run(
        f"sudo docker logs {filter_name}",
        shell=True, text=True, capture_output=True
    )
    lowlog = logs.stdout.lower()

    if "error" in lowlog or "failed" in lowlog:
        log_warn("[check_container] 로그에서 error/failed 감지됨")
    else:
        log_info("[check_container] 로그 정상(Log clean)")

    # custom_check (Vault/Postgres 등)
    if custom_check:
        return custom_check(service)

    log_info(f"[check_container] 기본 점검 완료(PASS) → {service}")
    return True

VAULT_HEALTH_MAP = {
    200: "OK (initialized, unsealed, active)",
    429: "Standby (initialized, unsealed, standby)",
    472: "DR Secondary",
    473: "Performance Standby",
    474: "Standby but active node unreachable",
    501: "Not initialized",
    503: "Sealed (unsealed required)",
    530: "Node removed from cluster",
}

def check_vault(service: str) -> bool:
    container = f"ai4infra-{service}"
    url = "https://localhost:8200/v1/sys/health"

    success_attempt = None
    status_code = None
    response_body = None

    # --------------------------------------------
    # Retry loop (HTTP Status + JSON)
    # --------------------------------------------
    for attempt in range(20):
        result = subprocess.run(
            f"curl -sk -o /tmp/vault_health.json -w '%{{http_code}}' {url}",
            shell=True, text=True, capture_output=True
        )

        status_str = result.stdout.strip()

        # status_code만 먼저 파싱
        if status_str.isdigit():
            status_code = int(status_str)

        # JSON 본문 로드
        try:
            with open("/tmp/vault_health.json", "r") as f:
                response_body = f.read().strip()
        except:
            response_body = ""

        if status_code and response_body:
            success_attempt = attempt
            break

        log_warn(f"[check_vault] API healthcheck 실패 → 재시도 ({attempt+1}/20)")
        time.sleep(1)

    if success_attempt is None:
        log_error("[check_vault] 20회 실패 → Vault API 응답 없음")
        return False

    # --------------------------------------------
    # 성공 attempt 출력
    # --------------------------------------------
    log_info(f"[check_vault] API healthcheck 성공 → {success_attempt+1}번째 시도")

    # --------------------------------------------
    # Debug 모드일 때: HTTP Code 의미를 상세 표시
    # --------------------------------------------
    meaning = VAULT_HEALTH_MAP.get(status_code, "Unknown status")

    log_debug(f"[check_vault] HTTP Code: {status_code} → {meaning}")

    # --------------------------------------------
    # Info 모드용 간결한 status 출력
    # --------------------------------------------
    try:
        data = json.loads(response_body)
    except Exception as e:
        log_error(f"[check_vault] API JSON 파싱 실패: {e}")
        return False

    log_info(f" initialized: {data.get('initialized')}")
    log_info(f" sealed     : {data.get('sealed')}")
    log_info(f" standby    : {data.get('standby')}")
    log_info(f" version    : {data.get('version')}")

    return True

def check_postgres(service: str) -> bool:
    """
    PostgreSQL healthcheck + TLS 심층 점검(5단계)
    1) Docker health (healthy)
    2) SELECT 1
    3) TLS 기본 상태 점검 (SHOW ssl)
    4) TLS 비활성 원인 자동 분석 (5가지 전부)
    """

    container = f"ai4infra-{service}"

    # ========================================
    # 1) Docker health 확인
    # ========================================
    for attempt in range(60):
        ps = subprocess.run(
            f"sudo docker ps --filter name={container} --format '{{{{.Status}}}}'",
            shell=True, text=True, capture_output=True
        )
        status = ps.stdout.strip().lower()

        if "healthy" in status:
            log_info(f"[check_postgres] Docker healthcheck 통과 (healthy) → {attempt+1}번째 시도")
            break

        if "unhealthy" in status:
            log_error("[check_postgres] Docker healthcheck: unhealthy")
            return False

        log_info(f"[check_postgres] PostgreSQL 준비중... 상태={status} → 재시도 ({attempt+1}/60)")
        time.sleep(1)
    else:
        log_error("[check_postgres] 60초 동안 healthy 상태가 되지 않음")
        return False

    # ========================================
    # 2) SELECT 1 확인
    # ========================================
    result = subprocess.run(
        f"sudo docker exec {container} psql -U postgres -c 'SELECT 1;'",
        shell=True, text=True, capture_output=True
    )
    if "1 row" in result.stdout:
        log_info("[check_postgres] SELECT 1 성공 → PostgreSQL 정상 동작")
    else:
        log_warn("[check_postgres] SELECT 1 실패 (그러나 healthcheck는 정상입니다)")

    # ========================================
    # 3) TLS 기본 상태 확인
    # ========================================
    log_info("[check_postgres] TLS 설정 점검 시작")

    tls_status = subprocess.run(
        f"sudo docker exec {container} psql -U postgres -t -c \"SHOW ssl;\"",
        shell=True, text=True, capture_output=True
    )
    ssl_value = tls_status.stdout.strip().lower()

    if ssl_value == "on":
        log_info("[check_postgres] TLS 활성화 확인됨 (ssl=on)")
    else:
        log_warn(f"[check_postgres] TLS 비활성화 (ssl={ssl_value}) → 자동 원인 분석 시작")
        return check_postgres_tls_diagnostics(container)


    # TLS가 실제 "on"이면 기본 인증 파일 경로와 존재 여부는 별도 점검
    return check_postgres_tls_diagnostics(container, tls_must_be_on=True)

def check_postgres_tls_diagnostics(container: str, tls_must_be_on: bool=False) -> bool:
    """
    PostgreSQL TLS 비활성(ssl=off) 또는 TLS 오류 원인 자동 분석

    자동 분석 항목 5개:
      1) 실제 적용 중인 postgresql.conf 파일 경로 검증(SHOW config_file)
      2) 설정파일(postgresql.conf)에 ssl=on이 존재하는지 확인
      3) SHOW ssl_cert_file / ssl_key_file / ssl_ca_file 값 확인
      4) 인증서/키 파일 존재 여부 확인
      5) key 파일 권한/소유자(postgres, 600) 검증
    """

    log_info("[TLS-DIAG] PostgreSQL TLS 진단 시작")

    # ---------------------------
    # ① 실제 config_file 경로 확인
    # ---------------------------
    cfg = run_psql_show(container, "config_file")
    data_dir = run_psql_show(container, "data_directory")

    log_info(f"[TLS-DIAG] config_file = {cfg}")
    log_info(f"[TLS-DIAG] data_directory = {data_dir}")

    if "postgresql.conf" not in cfg:
        log_error("[TLS-DIAG] postgresql.conf 파일 경로 비정상 → override 적용 안됨 가능성이 매우 높습니다.")


    # ---------------------------
    # ② 설정파일 내부에서 SSL 항목 확인
    # ---------------------------
    grep_ssl = subprocess.run(
        f"sudo docker exec {container} grep -iE '^[ ]*ssl' {cfg}",
        shell=True, text=True, capture_output=True
    )

    if grep_ssl.returncode != 0:
        log_error("[TLS-DIAG] postgresql.conf에서 ssl 관련 항목을 찾을 수 없습니다.")
    else:
        log_info(f"[TLS-DIAG] postgresql.conf 내 SSL 항목:\n{grep_ssl.stdout.strip()}")


    # ---------------------------
    # ③ SHOW ssl_* 파라미터 확인
    # ---------------------------
    ssl_cert = run_psql_show(container, "ssl_cert_file")
    ssl_key  = run_psql_show(container, "ssl_key_file")
    ssl_ca   = run_psql_show(container, "ssl_ca_file")

    log_info(f"[TLS-DIAG] ssl_cert_file = {ssl_cert}")
    log_info(f"[TLS-DIAG] ssl_key_file  = {ssl_key}")
    log_info(f"[TLS-DIAG] ssl_ca_file   = {ssl_ca}")

    # ---------------------------
    # ④ 파일 존재 여부 테스트
    # ---------------------------
    missing = False
    for p in [ssl_cert, ssl_key, ssl_ca]:
        if not file_exists_in_container(container, p):
            log_error(f"[TLS-DIAG] 파일 없음 → {p}")
            missing = True
        else:
            log_info(f"[TLS-DIAG] 파일 존재 확인 → {p}")

    # ---------------------------
    # ⑤ key 파일 권한 및 소유자 검증
    # ---------------------------
    if file_exists_in_container(container, ssl_key):
        perm = run_stat(container, ssl_key)
        log_info(f"[TLS-DIAG] key 파일 권한 = {perm}")

        if not perm.startswith("600"):
            log_error(f"[TLS-DIAG] key 파일 권한 오류 → 600 이어야 합니다: {ssl_key}")
            missing = True
        
        owner = run_owner(container, ssl_key)
        log_info(f"[TLS-DIAG] key 파일 소유자 = {owner}")

        if "postgres:postgres" not in owner:
            log_error(f"[TLS-DIAG] key 파일 소유자 오류 → postgres:postgres 이어야 합니다.")
            missing = True

    # ---------------------------
    # TLS가 반드시 켜져야 하는 모드일 때
    # ---------------------------
    if tls_must_be_on:
        ssl_state = run_psql_show(container, "ssl")
        if ssl_state != "on":
            log_error("[TLS-DIAG] TLS가 켜져 있어야 하는데 ssl=off 입니다.")
            return False

    if missing:
        log_error("[TLS-DIAG] TLS 설정 오류 감지됨")
        return False

    log_info("[TLS-DIAG] TLS 설정 및 파일 검증 완료 (모두 OK)")
    return True

def run_psql_show(container: str, name: str) -> str:
    cmd = f"sudo docker exec {container} psql -U postgres -t -c \"SHOW {name};\""
    res = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return res.stdout.strip()

def file_exists_in_container(container: str, path: str) -> bool:
    test = subprocess.run(f"sudo docker exec {container} test -f '{path}'", shell=True)
    return test.returncode == 0

def run_stat(container: str, path: str) -> str:
    cmd = f"sudo docker exec {container} stat -c '%a' '{path}'"
    res = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return res.stdout.strip()

def run_owner(container: str, path: str) -> str:
    cmd = f"sudo docker exec {container} stat -c '%U:%G' '{path}'"
    res = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return res.stdout.strip()
