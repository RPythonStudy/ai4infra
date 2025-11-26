"""
파일명: scripts/setup/setup_pyenv.py
목적: 프로젝트 파이썬 버전을 인식하여 버전 설정
설명: .python-version 파일을 읽어 pyenv local 명령으로 버전 설정
변경이력:
  - 2025-10-27: 크로스 플랫폼 호환성 개선 (BenKorea)
  - 2025-09-24: print(f"[setup_pyenv] ...") 표준 출력 포맷 적용
"""

import subprocess
import platform
from pathlib import Path


def main():
    # .python-version 파일 읽기
    try:
        version = Path(".python-version").read_text().strip()
    except FileNotFoundError:
        print("[setup-pyenv] .python-version 파일이 없습니다.")
        return
    
    if not version:
        print("[setup-pyenv] .python-version 파일이 비어있습니다.")
        return
    
    # 플랫폼별 pyenv 실행 방식 결정
    system = platform.system().lower()
    
    # pyenv local 실행
    try:
        if system == "windows":
            # Windows: shell=True 필요 (pyenv-win은 .bat 스크립트)
            subprocess.run(f"pyenv local {version}", check=True, shell=True)
        else:
            # Linux/macOS/WSL2: shell=False 권장
            subprocess.run(["pyenv", "local", version], check=True)
        
        print(f"[setup-pyenv] Python {version} 설정 완료")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"[setup-pyenv] 실패 - 수동 실행: pyenv local {version}")


if __name__ == "__main__":
    main()
