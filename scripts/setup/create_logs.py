"""
파일명: scripts/setup/create_logs.py
목적: 로그 파일 및 폴더 생성
설명: .env 파일에서 LOG_PATH를 읽어 logs 폴더 및 로그 파일을 생성
변경이력:
  - 2025-09-24: 새로 생성 (BenKorea)
"""

from pathlib import Path
import os
import platform
from dotenv import load_dotenv
import getpass
import shutil

ROOT = Path.cwd()
ENV_FILE = ROOT / '.env'
if not ENV_FILE.is_file():
    print("[create_logs] .env 파일이 없습니다. 먼저 .env를 복사하세요.")
    exit(1)

load_dotenv(ENV_FILE)

log_path = os.getenv('LOG_PATH')
project_name = os.getenv('PROJECT_NAME', 'default')
os_name = platform.system()
print(f"[create_logs] OS: {os_name}")
if log_path:
    log_path = log_path.replace('{PROJECT_NAME}', project_name)
    if os_name == "Windows":
        log_path = log_path.replace('%USERPROFILE%', os.environ.get('USERPROFILE', ''))
    elif os_name == "Darwin":
        log_path = log_path.replace('$HOME', os.environ.get('HOME', ''))

print(f"[create_logs] log_path: {log_path}")
if not log_path:
    print("[create_logs] .env에 LOG_PATH가 정의되어 있지 않습니다.")
    exit(1)

# log_path를 Path 객체로 변환
log_dir = Path(log_path)

if not log_dir.is_dir():
    log_dir.mkdir(parents=True, exist_ok=True)
    print(f"[create_logs] logs 폴더 생성: {log_dir}")
    if os_name != "Windows":
        try:
            user = os.getenv("SUDO_USER") or getpass.getuser()
            shutil.chown(str(log_dir), user=user, group=user)
            os.chmod(str(log_dir), 0o755)
            print(f"[create_logs] 소유자 및 권한 변경: {user}:{user}, 755")
        except Exception as e:
            print(f"[create_logs] 소유자/권한 변경 실패: {e}")
else:
    print(f"[create_logs] 이미 폴더 존재: {log_dir}")
