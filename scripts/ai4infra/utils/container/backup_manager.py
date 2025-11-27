#!/usr/bin/env python3

import os
import subprocess
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

from common.load_config import load_config
from common.logger import log_debug, log_error, log_info, log_warn

load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT")
BASE_DIR = os.getenv('BASE_DIR', '/opt/ai4infra')


def backup_data(service: str, data_folder: str = None) -> str:
    """
    서비스의 data 디렉터리만 백업합니다.
    
    경로 규칙:
      1) config/<service>.yml 의 path.data 가 있으면 그 값을 100% 사용
      2) 없으면 fallback: BASE_DIR/<service>/data
      3) bitwarden 역시 bitwarden.yml 에 path.data 를 넣어 통일할 수 있음

    백업 경로:
      BASE_DIR/backups/{service}/{service}_{timestamp}
    """

    # ------------------------------------------------------
    # 1) config에서 path.data 로드
    # ------------------------------------------------------
    cfg_path = f"{PROJECT_ROOT}/config/{service}.yml"

    try:
        cfg = load_config(cfg_path) or {}
    except Exception:
        log_error(f"[backup_data] 설정 로드 실패: {cfg_path}")
        return ""

    path_cfg = cfg.get("path", {})
    data_path = path_cfg.get("data")

    # ------------------------------------------------------
    # 2) data_dir 결정 (config 우선)
    # ------------------------------------------------------
    if data_path:
        src_dir = data_path
    else:
        # fallback — 거의 사용되지 않도록 path.data를 설정하는 것이 권장됨
        src_dir = f"{BASE_DIR}/{service}/data"

    # ------------------------------------------------------
    # 3) data_dir 존재 여부 확인
    # ------------------------------------------------------
    if not os.path.exists(src_dir):
        log_info(f"[backup_data] {service}: 백업할 data 디렉터리 없음 ({src_dir})")
        return ""

    # ------------------------------------------------------
    # 4) 백업 경로 구성
    # ------------------------------------------------------
    backup_dir = f"{BASE_DIR}/backups/{service}"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst_dir = f"{backup_dir}/{service}_{timestamp}"

    try:
        subprocess.run(['sudo', 'mkdir', '-p', backup_dir], check=True)

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
    백업된 데이터를 서비스의 data 디렉터리에 복원합니다.

    경로 규칙:
      1) config/<service>.yml 의 path.data 가 있으면 그대로 사용
      2) 없으면 fallback: BASE_DIR/<service>/data
      3) bitwarden.yml 에 path.data 를 추가하면 bitwarden도 일반 서비스처럼 처리 가능

    복원 방식:
      - rsync -a --numeric-ids 로 권한 및 소유자까지 그대로 복원
    """

    # -----------------------------------------
    # 1) 백업 경로 존재 확인
    # -----------------------------------------
    if not os.path.exists(backup_path):
        log_error(f"[restore_data] 백업 경로 없음: {backup_path}")
        return False

    # -----------------------------------------
    # 2) config/<service>.yml 에서 path.data 로드
    # -----------------------------------------
    cfg_path = f"{PROJECT_ROOT}/config/{service}.yml"

    try:
        cfg = load_config(cfg_path) or {}
    except Exception:
        log_error(f"[restore_data] 설정 로드 실패: {cfg_path}")
        return False

    path_cfg = cfg.get("path", {})
    data_path = path_cfg.get("data")

    # -----------------------------------------
    # 3) data_dir 결정 (bitwarden 예외는 config에서 해결 가능)
    # -----------------------------------------
    if data_path:
        restore_target = data_path
    else:
        restore_target = f"{BASE_DIR}/{service}/data"

    # -----------------------------------------
    # 4) 복원 대상 디렉터리 생성
    # -----------------------------------------
    try:
        subprocess.run(['sudo', 'mkdir', '-p', restore_target], check=True)

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
