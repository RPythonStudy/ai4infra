"""
파일명: src/common/sudo_helpers.py
목적: sudo 권한 필요 작업 유틸리티
설명:
  - sudo 권한으로 파일/디렉토리 존재 확인
  - sudo 권한으로 디렉토리 생성
  - 크로스 플랫폼 호환성 고려
변경이력:
  - 2025-12-03: 최초 작성 (BenKorea)
"""

import subprocess
from pathlib import Path
from typing import Union


def sudo_exists(path: Union[str, Path]) -> bool:
    """
    sudo 권한으로 파일/디렉토리 존재 확인
    
    Parameters
    ----------
    path : str | Path
        확인할 경로
        
    Returns
    -------
    bool
        경로가 존재하면 True, 아니면 False
        
    Notes
    -----
    - Permission denied 오류 없이 안전하게 존재 여부 확인
    - /opt/ai4infra와 같은 root 소유 디렉토리에 유용
    - os.path.exists()는 Permission denied 시 False 반환
    - Path.exists()는 Permission denied 시 PermissionError 발생
    """
    result = subprocess.run(
        ["sudo", "test", "-e", str(path)],
        capture_output=True
    )
    return result.returncode == 0


def sudo_mkdir(path: Union[str, Path], parents: bool = True) -> bool:
    """
    sudo 권한으로 디렉토리 생성
    
    Parameters
    ----------
    path : str | Path
        생성할 디렉토리 경로
    parents : bool
        상위 디렉토리도 함께 생성할지 여부 (기본값: True)
        
    Returns
    -------
    bool
        성공 시 True, 실패 시 False
    """
    try:
        cmd = ["sudo", "mkdir"]
        if parents:
            cmd.append("-p")
        cmd.append(str(path))
        
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def sudo_find_files(directory: Union[str, Path], pattern: str) -> list[Path]:
    """
    sudo find로 파일 검색
    
    Parameters
    ----------
    directory : str | Path
        검색할 디렉토리
    pattern : str
        파일명 패턴 (예: "*.key", "*.crt")
        
    Returns
    -------
    list[Path]
        찾은 파일 경로 리스트
        
    Notes
    -----
    - Permission denied 없이 파일 목록 수집
    - Path.glob()는 권한 문제로 실패할 수 있음
    """
    result = subprocess.run(
        ["sudo", "find", str(directory), "-maxdepth", "1", "-name", pattern, "-type", "f"],
        capture_output=True,
        text=True,
        check=False
    )
    if result.returncode == 0:
        return [Path(p.strip()) for p in result.stdout.strip().split('\n') if p.strip()]
    return []
