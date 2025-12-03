#!/usr/bin/env python3

import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

from common.logger import log_debug, log_error, log_info
from common.sudo_helpers import sudo_exists

load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT")
BASE_DIR = os.getenv('BASE_DIR', '/opt/ai4infra')


def handle_bitwarden_manual_install() -> bool:
    bitwarden_dir = f"{BASE_DIR}/bitwarden"
    bitwarden_script = f"{bitwarden_dir}/bitwarden.sh"
    compose_file = f"{bitwarden_dir}/bwdata/docker/docker-compose.yml"

    # 1) 이미 설치되어 있는지 검사 (bitwarden.sh + compose 파일, sudo로 확인)
    if sudo_exists(bitwarden_script) and sudo_exists(compose_file):
        log_info("[install_bitwarden] Bitwarden이 이미 설치되어 다음단계를 진행합니다.")
        return True

    # 2) 권한 설정은 apply_service_permissions()에서 이미 완료됨
    # 여기서는 설치 안내만 수행
    log_info("[install_bitwarden] Bitwarden 수동 설치 대기 중...")   

    # 3) 사용자에게 설치 안내 (설치스크립트 존재 여부는 체크하지 않음)
    instructions = (
        "Bitwarden이 설치되어 있지 않으므로 수동설치를 진행하세요.\n\n"
        "다른 터미널에서 다음 명령을 실행해 설치하십시오:\n\n"
        f"   sudo -su bitwarden\n"
        f"   cd {bitwarden_dir}\n"
        f"   ./bitwarden.sh install\n\n"
        "설치 중 domain name은 반드시 다음을 입력하세요.\n"    
        "bitwarden.ai4infra.internal\n"
        "Installation ID:는 다음을 입력하셔도 됩니다.\n"    
        "9430bf8f-2e8e-4819-89cf-b3a501117d6a\n"
        "Installation Key::는 다음을 입력하셔도 됩니다.\n"    
        "32QrtRae5lWV2GNWZBuP\n"    
    )
    log_info(instructions)
    input("설치 완료 후 Enter 키를 눌러 계속합니다...")

    # 4) 설치 완료 여부 확인 (sudo로 권한 우회)
    result = subprocess.run(
        ["sudo", "test", "-f", compose_file],
        capture_output=True
    )
    
    if result.returncode == 0:
        log_info("[install_bitwarden] Bitwarden 설치가 완료되었습니다.")
        return True
    else:
        log_error("[install_bitwarden] 설치가 완료되지 않았습니다. 수동 확인이 필요합니다.")
        return False

def apply_override(service: str) -> bool:
    if service != "bitwarden":
        log_debug(f"[apply_override] {service}: override 적용 대상 아님")
        return True

    src = Path(f"{PROJECT_ROOT}/template/bitwarden/bwdata/docker/docker-compose.override.yml")
    dst = Path(f"{BASE_DIR}/bitwarden/bwdata/docker/docker-compose.override.yml")

    if not src.exists():
        log_info(f"[apply_override] Bitwarden override 템플릿 없음: {src}")
        return True

    # Bitwarden 설치가 정상적으로 완료되었을 때만 bwdata/docker 경로가 생성됨 (sudo로 확인)
    result = subprocess.run(
        ["sudo", "test", "-d", str(dst.parent)],
        capture_output=True
    )
    
    if result.returncode != 0:
        log_debug("[apply_override] Bitwarden 설치 전이므로 override 적용 생략")
        return True

    # override 파일 존재 여부 확인 (sudo로 확인)
    result = subprocess.run(
        ["sudo", "test", "-f", str(dst)],
        capture_output=True
    )
    
    if result.returncode == 0:
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

        # override 파일 소유권 및 권한 설정
        subprocess.run(
            ["sudo", "chown", "bitwarden:bitwarden", str(dst)],
            check=True, capture_output=True, text=True
        )
        subprocess.run(
            ["sudo", "chmod", "644", str(dst)],
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
