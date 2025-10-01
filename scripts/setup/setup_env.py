"""
파일명: scripts/setup/setup_env.py
목적: .env 및 _environment 생성 스크립트
설명: .env 파일 생성 및 _environment 복사
변경이력:
  - 2025-09-24: 모듈 메타데이터 추가 (BenKorea)
  - 2025-09-07: 경로의 \ -> \\ 치환 추가 (BenKorea)
"""


import shutil
import re
from pathlib import Path
import platform

os_name = platform.system()
print(f"[setup_env] 운영체제: {os_name}")

ROOT = Path.cwd()
CUR_DIR_NAME = ROOT.name
src = ROOT / '.env.example'
dst = ROOT / '.env'
env_file = ROOT / '_environment'

if not src.is_file():
    print(f"[setup_env] .env.example 파일이 없습니다. 경로: {src}")
    exit(1)

shutil.copyfile(src, dst)

content = dst.read_text(encoding='utf-8')
content = re.sub(r'^PROJECT_NAME=.*', f'PROJECT_NAME={CUR_DIR_NAME}', content, flags=re.MULTILINE)
abs_path = str(ROOT)
content = re.sub(r'^PROJECT_ROOT=.*', f'PROJECT_ROOT={abs_path.replace("\\", r"\\\\")}', content, flags=re.MULTILINE)
content = content.replace('/home/ben/projects/rpy-quarto-template', abs_path)

if os_name == "Linux":
    log_path = "/var/log/{PROJECT_NAME}"
elif os_name == "Darwin":
    log_path = "$HOME/Library/Logs/{PROJECT_NAME}"
elif os_name == "Windows":
    log_path = "%USERPROFILE%\\AppData\\Local\\{PROJECT_NAME}"
else:
    log_path = "/var/log/{PROJECT_NAME}"
content = re.sub(r'^LOG_PATH=.*', f'LOG_PATH={log_path.replace("\\", r"\\\\")}', content, flags=re.MULTILINE)

dst.write_text(content, encoding='utf-8')
print("[setup_env] .env 파일이 생성되고, 경로 및 프로젝트명이 현재 폴더명으로 자동 치환되었습니다.")

try:
    shutil.copyfile(dst, env_file)
    print("[setup_env] _environment 파일이 .env로부터 복사 생성되었습니다.")
except Exception as e:
    print(f"[setup_env] _environment 복사 실패: {e}")