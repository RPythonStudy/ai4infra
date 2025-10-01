"""
파일명: scripts/setup/setup_venv.py
목적: 프로젝트 파이썬 가상환경 생성 및 패키지 설치
설명: 운영체제별 경로를 고려하여 subprocess로 구현
변경이력:
  - 2025-09-24: print(f"[setup_venv] ...") 표준 출력 포맷 적용
""" 

import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
VENV_PATH = ROOT / ".venv"
REQ_PATH = ROOT / "requirements.txt"

# 운영체제별 경로 설정
platform = sys.platform

if platform.startswith("win"):
    pip_path = VENV_PATH / "Scripts" / "pip.exe"
    python_path = VENV_PATH / "Scripts" / "python.exe"
    activate_cmds = {
        "CMD": f"{VENV_PATH}\\Scripts\\activate.bat",
        "PowerShell": f"{VENV_PATH}\\Scripts\\Activate.ps1",
        "Git Bash": f"source {VENV_PATH}/Scripts/activate",
    }
elif platform == "darwin":
    pip_path = VENV_PATH / "bin" / "pip"
    python_path = VENV_PATH / "bin" / "python"
    activate_cmds = {
        "bash/zsh": f"source {VENV_PATH}/bin/activate",
    }
else:  # Linux 및 기타
    pip_path = VENV_PATH / "bin" / "pip"
    python_path = VENV_PATH / "bin" / "python"
    activate_cmds = {
        "bash/zsh": f"source {VENV_PATH}/bin/activate",
    }

# 가상환경 생성
if not VENV_PATH.is_dir():
    print(f"[setup_venv] 가상환경 생성: {VENV_PATH}")
    subprocess.run([sys.executable, "-m", "venv", str(VENV_PATH)], check=True)
else:
    print(f"[setup_venv] 이미 가상환경 존재: {VENV_PATH}")

# requirements.txt 설치
if REQ_PATH.is_file():
    print(f"[setup_venv] requirements.txt 설치 중...")
    subprocess.run([str(pip_path), "install", "-r", str(REQ_PATH)], check=True)
else:
    print(f"[setup_venv] requirements.txt 파일이 없습니다.")

# 안내 메시지
print("\n[setup_venv] 가상환경 활성화 명령:")
for shell, cmd in activate_cmds.items():
    print(f"  {shell}: {cmd}")
print(f"[setup_venv] 가상환경 파이썬 경로: {python_path}")
