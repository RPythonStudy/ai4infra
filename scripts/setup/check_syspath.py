"""
파일명: scripts/setup/check_syspath.py
목적: Python 모듈 검색 경로 및 현재 작업 디렉토리 확인
설명: sys.path와 현재 작업 디렉토리를 로그로 출력
변경이력:
  - 2025-09-24: 새로 생성 (BenKorea)
"""
import sys
from pathlib import Path
from common.logger import log_info

log_info("=== Python 모듈 검색 경로 (sys.path) ===")
for i, path in enumerate(sys.path):
    log_info(f"{i}: {path}")

log_info("=== 현재 작업 디렉토리 ===")
log_info(str(Path.cwd()))