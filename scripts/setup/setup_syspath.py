"""
파일명: scripts/setup/setup_syspath.py
목적: 프로젝트 전체에서 파이썬 import 경로(src)를 일관되게 설정
설명: 가상환경의 site-packages에 .pth 파일을 생성하여 src 경로를 sys.path에 추가
변경이력:
  - 2025-09-24: print(f"[setup_syspath] ...") 표준 출력 포맷 적용
"""

import os
import sys
import sysconfig
from pathlib import Path

# 가상환경 확인
if os.environ.get('VIRTUAL_ENV') is None:
    print(f"[setup_syspath] 가상환경이 아닙니다. 스크립트를 중단합니다.")
    sys.exit(1)

# 현재 파이썬 site-packages 위치
site_packages = Path(sysconfig.get_paths()["purelib"])

# 프로젝트 루트와 src 경로 (프로젝트 루트 기준)
project_root = Path.cwd()
src_path = project_root / "src"

# src 경로 검증
if not src_path.is_dir():
    sys.exit(f"[setup_syspath] src 경로 없음: {src_path}")

# .pth 파일 생성
pth_file = site_packages / "project_paths.pth"
pth_file.write_text(str(src_path) + "\n", encoding="utf-8")

# 확인 메시지
print(f"[setup_syspath] .pth 생성: {pth_file}")
print(f"[setup_syspath] 추가 경로: {src_path}")
