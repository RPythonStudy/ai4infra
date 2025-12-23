#!/usr/bin/env python3

import os
import subprocess
from pathlib import Path
from common.logger import log_debug, log_error, log_info

def encrypt_file(input_file: str, output_file: str, passphrase: str) -> bool:
    """
    GPG를 사용하여 파일을 대칭키(passphrase) 방식으로 암호화합니다.
    (AES-256 사용 권장 - GPG 기본 설정에 따름)
    """
    if not os.path.exists(input_file):
        log_error(f"[encrypt_file] 입력 파일 없음: {input_file}")
        return False

    # GPG 암호화 명령
    # --batch: 비대화형 모드
    # --yes: 덮어쓰기 허용
    # --passphrase-fd 0: 표준 입력으로 비밀번호 받기
    # --symmetric: 대칭키 암호화
    # --cipher-algo AES256: 강력한 알고리즘 지정
    cmd = [
        'gpg', '--batch', '--yes',
        '--passphrase-fd', '0',
        '--symmetric',
        '--cipher-algo', 'AES256',
        '--output', output_file,
        input_file
    ]

    try:
        # 비밀번호를 stdin으로 전달하여 프로세스 목록에 노출되지 않게 함
        subprocess.run(
            cmd,
            input=passphrase.encode('utf-8'),
            check=True,
            capture_output=True
        )
        return True
    
    except subprocess.CalledProcessError as e:
        log_error(f"[encrypt_file] 암호화 실패: {e.stderr.decode().strip()}")
        return False
    except Exception as e:
        log_error(f"[encrypt_file] 예외 발생: {str(e)}")
        return False

def decrypt_file(input_file: str, output_file: str, passphrase: str) -> bool:
    """
    GPG로 암호화된 파일을 복호화합니다.
    """
    if not os.path.exists(input_file):
        log_error(f"[decrypt_file] 입력 파일 없음: {input_file}")
        return False

    cmd = [
        'gpg', '--batch', '--yes',
        '--passphrase-fd', '0',
        '--decrypt',
        '--output', output_file,
        input_file
    ]

    try:
        subprocess.run(
            cmd,
            input=passphrase.encode('utf-8'),
            check=True,
            capture_output=True
        )
        return True
    
    except subprocess.CalledProcessError as e:
        log_error(f"[decrypt_file] 복호화 실패 (비밀번호 오류일 수 있음): {e.stderr.decode().strip()}")
        return False
    except Exception as e:
        log_error(f"[decrypt_file] 예외 발생: {str(e)}")
        return False
