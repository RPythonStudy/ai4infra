"""
파일명: scripts/setup/backup.py
목적: data 폴더만 백업
설명: 프로젝트 루트의 data 폴더를 backup/<project-name>/data로 복사
변경이력:
  - 2025-09-24: data 폴더만 백업하도록 수정 (BenKorea)
"""

from dotenv import load_dotenv
from pathlib import Path
import shutil
import os
from common.logger import log_error, log_info


def backup_data(project_root: Path):
    data_dir = project_root / 'data'
    if not data_dir.exists():
        log_error(f"[backup.py] data 폴더가 존재하지 않습니다: {data_dir}")
        return
    project_name = project_root.name
    # 프로젝트 폴더의 상위 폴더가 projects라고 가정
    projects_root = project_root.parent
    backup_root = projects_root / 'backup' / project_name
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_dir = backup_root / "data"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    shutil.copytree(data_dir, backup_dir)
    log_info(f"[backup.py] data 폴더 백업 완료: {backup_dir}")

if __name__ == "__main__":
    load_dotenv()
    project_root_env = os.getenv('PROJECT_ROOT')
    if not project_root_env:
        log_error('[backup.py] PROJECT_ROOT 환경변수가 설정되어 있지 않습니다.')
    else:
        backup_data(Path(project_root_env))

