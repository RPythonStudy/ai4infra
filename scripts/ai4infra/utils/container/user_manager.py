#!/usr/bin/env python3

import os
import subprocess

from dotenv import load_dotenv

from common.logger import log_debug, log_error, log_info

load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT")
BASE_DIR = os.getenv('BASE_DIR', '/opt/ai4infra')


def create_user(username: str, password: str = "bit") -> bool:

    try:
        # 1) 사용자 존재 여부 확인
        cmd = ['id', username]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            log_debug(f"[create_user] id {username} → result: {result.stdout.strip()}")
            log_info(f"[create_user] 동일한 id 존재, 이 단계를 건너뜁니다.")
            return True

        # 2) 존재하지 않으면 `useradd`로 사용자 생성
        cmd = ['sudo', 'useradd', '-m', '-s', '/bin/bash', username]
        subprocess.run(cmd, check=True)
        log_info(f"[create_user] useradd result → '{username}' 생성 완료")

        # 3) 비밀번호 설정
        cmd = ['sudo', 'chpasswd']
        subprocess.run(cmd, input=f"{username}:{password}", text=True, check=True)
        log_info(f"[create_user] 사용자 '{username}' 비밀번호 설정 완료")
        return True

    except subprocess.CalledProcessError as e:
        log_error(f"[create_user] 실패: {e}")
        return False


def add_docker_group(user: str):
    """사용자를 docker 그룹에 추가 (이미 속해 있으면 건너뜀)"""
    try:
        # 현재 그룹 확인
        cmd = ['groups', user]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        current_groups = result.stdout.strip()        
        if 'docker' in current_groups.split():
            log_info(f"[add_docker_group] {user} 사용자가 이미 docker 그룹에 속해 있습니다.")
            return True
        
        # docker 그룹에 추가
        subprocess.run(['sudo', 'usermod', '-aG', 'docker', user], check=True)
        log_info(f"[add_docker_group] {user} 사용자를 docker 그룹에 추가했습니다.")
        return True
    
    except subprocess.CalledProcessError as e:
        log_error(f"[add_docker_group] 실패: {e.stderr if e.stderr else str(e)}")
        return False
