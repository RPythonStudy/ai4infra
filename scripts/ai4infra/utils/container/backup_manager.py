#!/usr/bin/env python3

import os
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

from common.load_config import load_config
from common.logger import log_debug, log_error, log_info, log_warn
from common.sudo_helpers import sudo_exists
from utils.container.installer import discover_services
from utils.container.crypto_manager import encrypt_file, decrypt_file

load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT")
BASE_DIR = os.getenv('BASE_DIR', '/opt/ai4infra')

# 백업 암호화 키 (없으면 경고 후 암호화 건너뜀 또는 에러 처리)
BACKUP_PASSWORD = os.getenv("BACKUP_PASSWORD")

def _run_hook_postgres(service: str, backup_root: str) -> str:
    """Postgres 전용 백업 훅: pg_dump 실행"""
    dump_file = f"{backup_root}/{service}_dump.sql"
    
    # 컨테이너 실행 중이어야 함
    log_info(f"[backup_hook] Postgres 덤프 시작...")
    
    # docker exec로 pg_dump 실행
    # (주의: 컨테이너 내부 유저는 postgres여야 함)
    cmd = [
        'sudo', 'docker', 'exec', 'ai4infra-postgres',
        'pg_dump', '-U', 'postgres', 'postgres'
    ]
    
    try:
        with open(dump_file, "w") as f:
            subprocess.run(cmd, stdout=f, check=True)
        log_info(f"[backup_hook] Postgres 덤프 완료: {dump_file}")
        return dump_file
    except subprocess.CalledProcessError:
        log_error("[backup_hook] pg_dump 실패")
        return ""
    except Exception as e:
        log_error(f"[backup_hook] pg_dump 예외: {e}")
        return ""

def _run_hook_vault(service: str, backup_root: str) -> str:
    """Vault 전용 백업 훅: Raft Snapshot 실행"""
    snapshot_file = f"{backup_root}/{service}_raft.snap"
    
    log_info(f"[backup_hook] Vault Raft 스냅샷 시작...")
    
    # docker exec로 vault operator raft snapshot save 실행
    # (Vault 토큰이 환경변수나 파일에 있어야 함. 여기서는 로컬 루트 토큰 가정 또는 에러 처리 필요)
    # 실제 운영 환경에서는 별도 인증 처리가 필요할 수 있음.
    cmd = [
        'sudo', 'docker', 'exec', '-e', 'VAULT_ADDR=https://127.0.0.1:8200', 'ai4infra-vault',
        'vault', 'operator', 'raft', 'snapshot', 'save', 
        f"/tmp/vault.snap"  # 컨테이너 내부 경로
    ]
    
    try:
        subprocess.run(cmd, check=True)
        
        # 컨테이너 내부 파일을 호스트로 복사
        cp_cmd = ['sudo', 'docker', 'cp', 'ai4infra-vault:/tmp/vault.snap', snapshot_file]
        subprocess.run(cp_cmd, check=True)
        
        log_info(f"[backup_hook] Vault 스냅샷 완료: {snapshot_file}")
        return snapshot_file
    except subprocess.CalledProcessError:
        log_error("[backup_hook] Vault 스냅샷 실패 (Unsealed 상태 및 권한 확인 필요)")
        return ""
    except Exception as e:
        log_error(f"[backup_hook] Vault 스냅샷 예외: {e}")
        return ""

def _run_restore_hook_postgres(service: str, extract_dir: str) -> bool:
    """Postgres 복원 훅: psql로 덤프 로드"""
    dump_file = f"{extract_dir}/{service}_dump.sql"
    if not os.path.exists(dump_file):
        return False
        
    log_info(f"[restore_hook] Postgres 덤프 리스토어 시작...")
    
    # 컨테이너가 켜져 있어야 함 (복원 시점 유의)
    # DB 초기화 후 데이터 로드
    # 여기서는 간단히 psql < dump_file 실행
    cmd = [
        'sudo', 'docker', 'exec', '-i', 'ai4infra-postgres',
        'psql', '-U', 'postgres', 'postgres'
    ]
    
    try:
        with open(dump_file, "r") as f:
            subprocess.run(cmd, stdin=f, check=True)
        log_info("[restore_hook] Postgres 리스토어 완료")
        return True
    except Exception as e:
        log_error(f"[restore_hook] 리스토어 실패: {e}")
        return False

def _run_restore_hook_vault(service: str, extract_dir: str) -> bool:
    """Vault 복원 훅: Raft Snapshot Restore"""
    snapshot_file = f"{extract_dir}/{service}_raft.snap"
    if not os.path.exists(snapshot_file):
        return False

    log_info(f"[restore_hook] Vault 스냅샷 리스토어 시작 (Force)...")
    
    # 컨테이너 내부로 파일 복사
    subprocess.run(['sudo', 'docker', 'cp', snapshot_file, 'ai4infra-vault:/tmp/restore.snap'], check=True)
    
    # Force Restore
    cmd = [
        'sudo', 'docker', 'exec', 'ai4infra-vault',
        'vault', 'operator', 'raft', 'snapshot', 'restore', '-force',
        '/tmp/restore.snap'
    ]
    
    try:
        subprocess.run(cmd, check=True)
        log_info("[restore_hook] Vault 스냅샷 리스토어 성공. (Vault 재시작 필요할 수 있음)")
        return True
    except Exception as e:
        log_error(f"[restore_hook] Vault 리스토어 실패: {e}")
        return False


def backup_data(service: str) -> str:
    """
    서비스 백업 (암호화 + 압축)
    1. 임시 디렉터리에 데이터 수집 (Hook 또는 파일 복사)
    2. tar.gz 압축
    3. gpg 암호화
    4. 임시 파일 삭제
    """
    
    if not BACKUP_PASSWORD:
        log_error("[backup_data] .env에 BACKUP_PASSWORD가 설정되지 않았습니다. 백업 중단.")
        return ""

    backup_dir = f"{BASE_DIR}/backups/{service}"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 임시 작업 공간
    temp_root = f"/tmp/ai4infra_backup_{service}_{timestamp}"
    subprocess.run(['mkdir', '-p', temp_root], check=True)
    
    # ---------------------------------------------
    # 1. 데이터 수집 (Hook or File Copy)
    # ---------------------------------------------
    data_collected = False

    # Config 로드
    cfg_path = f"{PROJECT_ROOT}/config/{service}.yml"
    cfg = load_config(cfg_path) or {}
    backup_cfg = cfg.get("backup", {})
    method = backup_cfg.get("method", "copy")  # default: copy

    log_debug(f"[backup_data] {service} backup method: {method}")

    if method == "pg_dump":
        if _run_hook_postgres(service, temp_root):
            data_collected = True
            
    elif method == "raft_snapshot":
        if _run_hook_vault(service, temp_root):
            data_collected = True
            
    else:
        # 일반 서비스: 데이터 디렉터리 복사 (method="copy" or others)
        src_dir = f"{BASE_DIR}/{service}/data"
        
        # Config Override 확인 (already loaded cfg)
        try:
            path_cfg = cfg.get("path", {})
            dirs = path_cfg.get("directories", {})
            if dirs.get("data"):
                src_dir = dirs.get("data")
        except:
            pass
            
        if sudo_exists(src_dir):
            subprocess.run(['sudo', 'cp', '-a', src_dir, f"{temp_root}/data"], check=True)
            data_collected = True
        else:
            log_info(f"[backup_data] {service}: 데이터 디렉터리 없음 (Skip)")

    if not data_collected:
        log_error(f"[backup_data] {service}: 백업할 데이터가 없습니다.")
        subprocess.run(['rm', '-rf', temp_root])
        return ""

    # ---------------------------------------------
    # 2. 압축 (tar.gz)
    # ---------------------------------------------
    tar_file = f"/tmp/{service}_{timestamp}.tar.gz"
    # temp_root 내용을 압축
    try:
        subprocess.run(
            ['sudo', 'tar', '-czf', tar_file, '-C', temp_root, '.'],
            check=True
        )
    except Exception as e:
        log_error(f"[backup_data] 압축 실패: {e}")
        subprocess.run(['rm', '-rf', temp_root])
        return ""
        
    # ---------------------------------------------
    # 3. 암호화 (GPG)
    # ---------------------------------------------
    final_file = f"{backup_dir}/{service}_{timestamp}.tar.gz.gpg"
    subprocess.run(['sudo', 'mkdir', '-p', backup_dir], check=True)
    
    log_info(f"[backup_data] 암호화 진행 중...")
    success = encrypt_file(tar_file, final_file, BACKUP_PASSWORD)
    
    # ---------------------------------------------
    # 4. 정리
    # ---------------------------------------------
    subprocess.run(['sudo', 'rm', '-rf', temp_root], check=True)
    subprocess.run(['sudo', 'rm', '-f', tar_file], check=True)
    
    if success:
        log_info(f"[backup_data] {service} 보안 백업 완료: {final_file}")
        return final_file
    else:
        log_error(f"[backup_data] 암호화 실패")
        return ""


def restore_data(service: str, backup_path: str) -> bool:
    """
    서비스 복원 (복호화 + 압축해제 + Hook/Copy)
    """
    if not BACKUP_PASSWORD:
        log_error("[restore_data] .env에 BACKUP_PASSWORD가 없습니다.")
        return False
        
    if not os.path.exists(backup_path):
        log_error(f"[restore_data] 파일 없음: {backup_path}")
        return False

    # ---------------------------------------------
    # 1. 복호화
    # ---------------------------------------------
    temp_tar = f"/tmp/restore_{datetime.now().timestamp()}.tar.gz"
    log_info(f"[restore_data] 복호화 진행 중...")
    
    if not decrypt_file(backup_path, temp_tar, BACKUP_PASSWORD):
        return False
        
    # ---------------------------------------------
    # 2. 압축 해제
    # ---------------------------------------------
    temp_extract_root = f"/tmp/restore_extract_{datetime.now().timestamp()}"
    os.makedirs(temp_extract_root, exist_ok=True)
    
    try:
        subprocess.run(['tar', '-xzf', temp_tar, '-C', temp_extract_root], check=True)
    except Exception as e:
        log_error(f"[restore_data] 압축 해제 실패: {e}")
        return False
        
    # ---------------------------------------------
    # 3. 데이터 복원 (Hook or File Copy)
    # ---------------------------------------------
    success = False

    # Config 로드 (복원 시에도 method 확인 필요)
    cfg_path = f"{PROJECT_ROOT}/config/{service}.yml"
    cfg = load_config(cfg_path) or {}
    backup_cfg = cfg.get("backup", {})
    method = backup_cfg.get("method", "copy")

    log_debug(f"[restore_data] {service} restore method: {method}")
    
    if method == "pg_dump":
        success = _run_restore_hook_postgres(service, temp_extract_root)
        
    elif method == "raft_snapshot":
        success = _run_restore_hook_vault(service, temp_extract_root)
        
    else:
        # 일반 파일 복원
        src_data = f"{temp_extract_root}/data"
        if os.path.exists(src_data):
            # 타겟 경로 계산
            dst_dir = f"{BASE_DIR}/{service}/data"
            try:
                # cfg already loaded
                path_cfg = cfg.get("path", {})
                dirs = path_cfg.get("directories", {})
                if dirs.get("data"):
                    dst_dir = dirs.get("data")
            except:
                pass
            
            subprocess.run(['sudo', 'mkdir', '-p', dst_dir], check=True)
            # rsync로 내용물 동기화
            subprocess.run(['sudo', 'rsync', '-a', f"{src_data}/", f"{dst_dir}/"], check=True)
            log_info(f"[restore_data] 데이터 파일 복원 완료")
            success = True
        else:
            log_error(f"[restore_data] 백업 내 data 폴더를 찾을 수 없습니다.")

    # ---------------------------------------------
    # 4. 정리
    # ---------------------------------------------
    subprocess.run(['sudo', 'rm', '-f', temp_tar], check=True)
    subprocess.run(['sudo', 'rm', '-rf', temp_extract_root], check=True)
    
    return success
