"""
파일명: scripts/setup/restore_backup.py
목적: data 폴더만 복원
설명: backup/<project-name>/data를 프로젝트 루트의 data로 복사
변경이력:
  - 2025-09-24: data 폴더만 복원하도록 수정 (BenKorea)
"""

from pathlib import Path
import shutil
import os
from dotenv import load_dotenv
from common.logger import log_error, log_info

def restore_data(project_root: Path):
    project_name = project_root.name
    projects_root = project_root.parent
    backup_data_dir = projects_root / 'backup' / project_name / 'data'
    data_dir = project_root / 'data'
    # 디버깅: 경로 및 파일 리스트 로깅
    log_info(f"[DEBUG] project_root: {project_root}")
    log_info(f"[DEBUG] projects_root: {projects_root}")
    log_info(f"[DEBUG] backup_data_dir: {backup_data_dir}")
    log_info(f"[DEBUG] data_dir: {data_dir}")
    log_info(f"[DEBUG] backup_data_dir.exists(): {backup_data_dir.exists()}")
    if backup_data_dir.exists():
        log_info(f"[DEBUG] backup_data_dir 파일 목록: {list(backup_data_dir.iterdir())}")
    else:
        log_info(f"[DEBUG] backup_data_dir가 존재하지 않습니다.")
    if not backup_data_dir.exists():
        log_error(f'[restore_backup.py] 백업 데이터 폴더가 존재하지 않습니다: {backup_data_dir}')
        return
    if data_dir.exists():
        log_info(f"[DEBUG] 기존 data_dir 삭제: {data_dir}")
        shutil.rmtree(data_dir)
    shutil.copytree(backup_data_dir, data_dir)
    log_info(f'[restore_backup.py] data 폴더 복원 완료: {data_dir}')
    log_info(f"[DEBUG] 복원 후 data_dir 파일 목록: {list(data_dir.iterdir()) if data_dir.exists() else '존재하지 않음'}")

if __name__ == "__main__":
    load_dotenv()
    project_root = os.getenv('PROJECT_ROOT')
    if not project_root:
        log_error('[restore_backup.py] PROJECT_ROOT 환경변수가 설정되어 있지 않습니다.')
    else:
        restore_data(Path(project_root))
