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
    """
    지정된 시스템 사용자를 생성합니다. 이미 존재하는 경우 아무 작업도 수행하지 않습니다.

    사용 흐름:
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
    - 이 함수는 내부 로깅을 수행하며, 반환값을 기반으로 호출자가 
    다음 단계를 진행할지 결정하는 구조입니다.
    - 사용자 계정은 홈 디렉터리(`/home/{username}`)와 Bash 셸(`/bin/bash`)을 기본 구성으로 생성합니다.
    - 보안 이유로 비밀번호 설정은 로컬 `chpasswd` 명령을 사용합니다.

    Future Considerations
    ---------------------
    - 타 컨테이너 서비스(PostgreSQL, ELK 등)도 독립 계정이 필요한 경우 
    uid/gid 매핑 전략을 추가 검토할 수 있습니다.
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
    try:
        subprocess.run(['sudo', 'usermod', '-aG', 'docker', user], check=True)
        log_info(f"[add_docker_group] {user} 사용자를 docker 그룹에 추가했습니다.")
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"[add_docker_group] 실패: {e.stderr}")
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

def backup_data(service: str, data_folder: str = None) -> str:
    """
    서비스 디렉터리를 권한/소유권 그대로 백업합니다.

    제외 항목:
    - docker-compose.yml
    - logs/
    - .env*
    - *.log

    백업 결과는 BASE_DIR/backups/{service}/{service}_{timestamp} 에 저장됩니다.

    Returns
    -------
    str
        백업이 저장된 디렉터리 경로. 실패 시 빈 문자열.
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

        # 권한/소유권을 그대로 보존한 채 백업
        cmd = [
            'sudo', 'rsync', '-a', '--numeric-ids',
            '--exclude', 'docker-compose.yml',
            '--exclude', 'logs/',
            '--exclude', '.env',
            '--exclude', '*.log',
            f"{src_dir}/", f"{dst_dir}/"
        ]
        subprocess.run(cmd, check=True)

        log_info(f"[backup_data] {service}: 전체 백업 완료 → {dst_dir}")
        return dst_dir

    except subprocess.CalledProcessError as e:
        log_error(f"[backup_data] {service}: 백업 실패 - {e}")
        return ""

def copy_template(service: str) -> bool:
    """
    템플릿 디렉터리를 서비스 디렉터리로 덮어쓰기합니다 (root 권한).
    Bitwarden의 경우 bwdata 전체 제외 (설치 스크립트가 생성해야 함).
    """
    template_dir = f"{PROJECT_ROOT}/template/{service}"
    service_dir = f"{BASE_DIR}/{service}"

    try:
        subprocess.run(['sudo', 'mkdir', '-p', service_dir], check=True)

        # Bitwarden 전용: bwdata 전체 제외 + override 제외
        exclude_args = []
        if service == "bitwarden":
            exclude_args = [
                '--exclude', 'bwdata/',
                '--exclude', 'bwdata/**',
                '--exclude', 'bwdata/*',
                '--exclude', 'bwdata/docker/docker-compose.override.yml',
            ]

        cmd = [
            'sudo', 'rsync', '-a', '-i',
        ] + exclude_args + [
            f"{template_dir}/",
            f"{service_dir}/"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        if result.stdout.strip():
            log_debug(f"[copy_template] 변경/복사된 파일:\n{result.stdout.strip()}")
        else:
            log_debug("[copy_template] 변경 사항 없음")

        # Bitwarden 소유권 처리
        if service == "bitwarden":
            install_script = f"{service_dir}/bitwarden.sh"
            if os.path.exists(install_script):
                subprocess.run(['sudo', 'chown', 'bitwarden:bitwarden', install_script], check=False)
                subprocess.run(['sudo', 'chmod', '+x', install_script], check=False)

            subprocess.run(['sudo', 'chown', 'bitwarden:bitwarden', service_dir], check=False)

        log_info(f"[copy_template] {service} 템플릿 복사 완료 → {service_dir}")
        return True

    except subprocess.CalledProcessError as e:
        log_error(f"[copy_template] 실패: {e.stderr}")
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
        "다른 터미널에서 bitwarden 사용자로 다음 명령을 실행해 설치하십시오:\n\n"
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
        "Bitwarden을 수동으로 시작해 주세요 (설치 시와 같은 터미널에서):\n"
        f"  ./bitwarden.sh start\n\n"
        "시작 후 원래 터미널로 돌아와 Enter를 눌러 계속하세요."
    )
    log_info(f"[bitwarden_start] 수동 시작 안내:\n{instructions}")

    try:
        input("수동 시작 후 Enter를 눌러 계속합니다...")
    except KeyboardInterrupt:
        log_info("[bitwarden_start] 사용자가 중단함")
        return False

    log_info("[bitwarden_start] 사용자가 Bitwarden을 수동으로 시작했다고 보고함")
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

