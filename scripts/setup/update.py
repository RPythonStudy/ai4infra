"""
파일명: scripts/setup/update.py
목적: template에서 갱신된 script들을 갱신함
설명: 
  - config, scripts, src, tests, Makefile을 template에서 복사
  - 같은 파일을 덮어쓰기방식, 다른 파일이 존재하면 보관하는 방식
변경이력:
  - 2025-09-25: 최초 생성 (BenKorea)
"""

import shutil
import os
from pathlib import Path
from dotenv import load_dotenv
from common.logger import log_info, log_error

def update_from_template(template_path: Path, target_path: Path, update_list=None):
    if not template_path.exists():
        log_error(f"[update.py] 템플릿 경로가 존재하지 않습니다: {template_path}")
        return
    if not target_path.exists():
        log_error(f"[update.py] 타겟 경로가 존재하지 않습니다: {target_path}")
        return
    if update_list is None:
        update_list = ["src", "config", "scripts", "tests"]
    for item in update_list:
        src_item = template_path / item
        dst_item = target_path / item
        if not src_item.exists():
            log_info(f"[update.py] 템플릿에 {item}이(가) 없어 건너뜀.")
            continue
        if src_item.is_dir():
            dst_item.mkdir(parents=True, exist_ok=True)
            for src_file in src_item.rglob("*"):
                if src_file.is_file():
                    rel_path = src_file.relative_to(src_item)
                    dst_file = dst_item / rel_path
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dst_file)
                    log_info(f"[update.py] 파일 복사 완료: {item}/{rel_path}")
        else:
            shutil.copy2(src_item, dst_item)
            log_info(f"[update.py] 파일 복사 완료: {item}")

if __name__ == "__main__":
    load_dotenv()
    project_root = os.getenv('PROJECT_ROOT')
    if not project_root:
        log_error('[update.py] PROJECT_ROOT 환경변수가 설정되어 있지 않습니다.')
        sys.exit(1)
    script_path = Path(__file__).resolve()
    projects_root = script_path.parent.parent.parent.parent
    template_path = projects_root / 'rpy-quarto-template'
    target_path = Path(project_root)
    update_list = ["config", "scripts", "src", "tests"]
    log_info(f"[update.py] template_path: {template_path}")
    log_info(f"[update.py] target_path: {target_path}")
    log_info(f"[update.py] update_list: {update_list}")
    update_from_template(template_path, target_path, update_list)