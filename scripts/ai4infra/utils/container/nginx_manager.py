#!/usr/bin/env python3

import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv

from common.logger import log_info, log_error, log_debug
from utils.container.healthcheck import check_container

load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT")
BASE_DIR = os.getenv('BASE_DIR', '/opt/ai4infra')

def deploy_nginx_certs(service: str, service_dir: str):
    """
    서비스의 인증서를 Nginx가 읽을 수 있는 공용 인증서 폴더로 복사합니다.
    """
    nginx_certs_dir = f"{BASE_DIR}/nginx/certs"
    
    # Nginx 컨테이너가 없으면 굳이 복사할 필요 없음 (혹은 미리 준비)
    if not check_container("nginx"):
        return

    # Ensure folder exists
    subprocess.run(["mkdir", "-p", nginx_certs_dir], check=False)

    src_crt = f"{service_dir}/certs/certificate.crt"
    src_key = f"{service_dir}/certs/private.key"
    dst_crt = f"{nginx_certs_dir}/{service}.crt"
    dst_key = f"{nginx_certs_dir}/{service}.key"

    if os.path.exists(src_crt) and os.path.exists(src_key):
        log_info(f"[deploy_nginx_certs] Nginx용 인증서 복사: {service}.crt/.key")
        subprocess.run(["cp", src_crt, dst_crt], check=False)
        subprocess.run(["cp", src_key, dst_key], check=False)
        
        # Nginx가 읽을 수 있도록 권한 설정 (World Readable for Cert, Key needs care)
        # Nginx 컨테이너 내부 사용자 권한 문제 방지를 위해 644로 설정 (내부 root 실행 가정시 600도 가능하나 안전하게)
        subprocess.run(["chmod", "644", dst_crt], check=False)
        subprocess.run(["chmod", "644", dst_key], check=False) 
    else:
        log_debug(f"[deploy_nginx_certs] {service} 인증서 파일이 없어 복사 생략")

def deploy_nginx_config(service: str):
    """
    서비스용 Nginx 설정 파일(.conf)을 복사합니다.
    """
    nginx_conf_src = f"{PROJECT_ROOT}/templates/nginx/config/conf.d/{service}.conf"
    nginx_conf_dest = f"{BASE_DIR}/nginx/config/conf.d/{service}.conf"

    if os.path.exists(nginx_conf_src) and check_container("nginx"):
        log_info(f"[deploy_nginx_config] Nginx 설정 복사: {service}.conf")
        # 대상 폴더는 nginx 설치 시 생성됨
        subprocess.run(["cp", nginx_conf_src, nginx_conf_dest], check=False)
        return True
    
    return False

def reload_nginx():
    """
    Nginx 컨테이너를 재시작하여 변경 사항을 반영합니다.
    (reload 명령을 쓸 수도 있으나, 확실한 반영을 위해 restart 사용)
    """
    if check_container("nginx"):
        log_info(f"[reload_nginx] 설정 반영을 위해 Nginx 재시작...")
        subprocess.run(["docker", "restart", "ai4infra-nginx"], check=False)

def setup_nginx_for_service(service: str):
    """
    서비스 설치 후 Nginx 관련 통합 작업 (인증서, 설정, 리로드)을 수행합니다.
    """
    service_dir = f"{BASE_DIR}/{service}"
    
    # 1. 인증서 배포
    deploy_nginx_certs(service, service_dir)
    
    # 2. 설정 파일 배포
    config_deployed = deploy_nginx_config(service)
    
    # 3. 변경 사항이 있거나, Orthanc/Keycloak 등 강제 리로드 필요 서비스인 경우 리로드
    # (단, deploy_nginx_config가 True를 반환했거나, 기존 로직상 필요한 경우)
    
    # 기존 로직: if config_deployed OR (Keycloak/Orthanc and Nginx exists)
    # 여기서는 단순하게 config가 배포되거나 업데이트 되었으면 리로드, 
    # 하지만 "항상" 리로드하는 것이 안전함 (인증서 갱신 등)
    # 단, 너무 잦은 리로드는 비효율적이나 설치 스크립트 특성상 허용.
    
    if config_deployed or service == "keycloak" or service.startswith("orthanc"):
        reload_nginx()
