#!/usr/bin/env python3

import os
import subprocess

from dotenv import load_dotenv

from common.logger import log_debug, log_error, log_info

load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT")
BASE_DIR = os.getenv('BASE_DIR', '/opt/ai4infra')


def setup_usb_secrets() -> bool:
    usb_dir = "/mnt/usb"
    template_usb = f"{PROJECT_ROOT}/template/usb"
    
    try:
        # 마운트 포인트 생성
        cmd = ['sudo', 'mkdir', '-p', usb_dir]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        log_debug(f"[setup_usb_secrets] {usb_dir} 디렉터리 생성 완료")
        
        # USB 디렉터리가 비어있는지 확인
        cmd = ['sudo', 'ls', '-A', usb_dir]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        is_empty = not result.stdout.strip()
        
        if is_empty:
            # 템플릿 복사 (실제 USB 미마운트 시)
            cmd = ['sudo', 'cp', '-a', f"{template_usb}/.", usb_dir]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            log_info(f"[setup_usb_secrets] USB 템플릿 복사 완료 → {usb_dir}")
            
            # 권한 설정 (600: 소유자만 읽기/쓰기)
            cmd = ['sudo', 'find', usb_dir, '-name', '*.enc', '-exec', 'chmod', '600', '{}', ';']
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            log_info(f"[setup_usb_secrets] *.enc 파일 권한 설정 완료 (600)")
        else:
            log_info(f"[setup_usb_secrets] {usb_dir}에 이미 파일이 존재하므로 복사를 건너뜁니다.")
        
        # 파일 목록 확인
        cmd = ['sudo', 'ls', '-lh', usb_dir]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        log_debug(f"[setup_usb_secrets] {usb_dir} 내용:\n{result.stdout.strip()}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        log_error(f"[setup_usb_secrets] 명령 실패: {e}")
        if e.stderr:
            log_error(f"[setup_usb_secrets] stderr: {e.stderr}")
        return False
    except Exception as e:
        log_error(f"[setup_usb_secrets] 예외 발생: {e}")
        return False
