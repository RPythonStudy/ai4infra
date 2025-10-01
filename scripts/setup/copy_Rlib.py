"""
파일명: scripts/setup/copy_Rlib.py
목적: Rlib 폴더를 R 폴더로 복사
설명: src/Rlib의 내용을 src/R로 복사S
변경이력:
  - 2025-09-24: 새로 생성 (BenKorea)
"""


from pathlib import Path
import shutil

root = Path.cwd()
src_dir = root / 'src' / 'Rlib'
dst_dir = root / 'src' / 'R'

dst_dir.mkdir(parents=True, exist_ok=True)
for src_path in src_dir.iterdir():
    if src_path.is_file():
        shutil.copy2(src_path, dst_dir / src_path.name)
