"""
파일명: scripts/setup/setup_pyenv.py
목적: 프로젝트 파이썬 버전을 인식하여 버전 설정
설명: .python-version 파일을 읽어 pyenv local 명령으로 버전 설정
변경이력:
  - 2025-09-24: print(f"[setup_pyenv] ...") 표준 출력 포맷 적용
""" 

import subprocess
from pathlib import Path


version_file = Path(".python-version")
if version_file.exists():
    version = version_file.read_text(encoding="utf-8").strip()
    if version:
        subprocess.run(["pyenv", "local", version], check=True)
        print(f"[setup-pyenv] pyenv local {version} 실행 완료")
    else:
        print("[setup-pyenv] .python-version 파일이 비어 있습니다.")
else:
    print("[setup-pyenv] .python-version 파일이 없습니다.")
