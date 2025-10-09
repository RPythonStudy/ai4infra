"""
파일명: scripts/ai4infra/generate_certificates.py
목적: AI4INFRA 프로젝트용 SSL 인증서 자동 생성
기능: 
  - OpenSSL 기반 자체 서명 인증서 생성
  - 서비스별 SAN(Subject Alternative Name) 자동 구성
  - /opt/ai4infra 경로 구조 지원
변경이력:
  - 2025-10-08: AI4INFRA 프로젝트에 맞게 리팩토링 (BenKorea)
"""

import sys
from pathlib import Path
import subprocess
from typing import List, Optional

from common.logger import log_info, log_warn, log_error

# AI4INFRA 서비스별 인증서 경로
def get_cert_path(service: str) -> str:
    """BASE_DIR 기반 인증서 경로 반환"""
    import os
    base_dir = os.getenv('BASE_DIR', '/opt/ai4infra')
    return f"{base_dir}/{service}/certs"


def create_cert(service: str, days: int = 730, overwrite: bool = False) -> bool:
    """단일 서비스 인증서 생성"""
    supported_services = ["vault", "postgres", "ldap", "elk", "bitwarden"]
    if service not in supported_services:
        log_warn(f"[create_cert] 지원하지 않는 서비스: {service}")
        return False
    
    cert_dir = Path(get_cert_path(service))
    cert_file = cert_dir / f"{service}.crt"
    key_file = cert_dir / f"{service}.key"
    
    if cert_file.exists() and key_file.exists() and not overwrite:
        log_info(f"[create_cert] {service} 인증서가 이미 존재합니다: {cert_file}")
        return True
    
    # sudo로 디렉토리 생성
    subprocess.run(['sudo', 'mkdir', '-p', str(cert_dir)], check=True)
    
    # SAN 구성
    san = f"DNS:localhost,DNS:{service},IP:127.0.0.1"
    
    # OpenSSL 명령어
    cmd = [
        'sudo', 'openssl', 'req', '-x509', '-nodes',
        '-newkey', 'rsa:2048',
        '-keyout', str(key_file),
        '-out', str(cert_file),
        '-days', str(days),
        '-subj', f'/CN={service}',
        '-addext', f'subjectAltName = {san}'
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        # 컨테이너에서 읽을 수 있도록 권한 설정
        subprocess.run(['sudo', 'chmod', '644', str(cert_file)])
        subprocess.run(['sudo', 'chmod', '644', str(key_file)])
        subprocess.run(['sudo', 'chown', '999:999', str(cert_file)])  # vault 사용자
        subprocess.run(['sudo', 'chown', '999:999', str(key_file)])
        
        log_info(f"[create_cert] {service} 인증서 생성 완료: {cert_file}")
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"[create_cert] {service} 인증서 생성 실패: {e.stderr}")
        return False


def generate_certificates(services: List[str], days: int = 730, 
                        overwrite: bool = False) -> bool:
    """여러 서비스 인증서 일괄 생성"""
    log_info(f"[generate_certificates] 인증서 생성 시작")
    
    success_count = 0
    for service in services:
        if create_cert(service, days, overwrite):
            success_count += 1

    log_info(f"[generate_certificates] 인증서 생성 완료: {success_count}/{len(services)}")
    return success_count == len(services)


if __name__ == "__main__":
    import typer
    
    app = typer.Typer(help="AI4INFRA SSL 인증서 생성기")
    
    @app.command()
    def cert(
        services: List[str] = typer.Argument(..., help="생성할 서비스 목록"),
        days: int = typer.Option(730, "--days", "-d", help="인증서 유효기간"),
        overwrite: bool = typer.Option(False, "--overwrite", "-f", 
                                     help="기존 인증서 덮어쓰기")
    ):
        """SSL 인증서 생성"""
        generate_certificates(services, days, overwrite)
    
    app()
