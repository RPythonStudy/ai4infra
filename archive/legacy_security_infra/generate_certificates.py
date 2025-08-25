# src/security_infra/generate_certificates.py

import typer
from pathlib import Path
import subprocess
from datetime import datetime
from typing import List, Optional

# [1] 프로젝트 루트 자동 탐지 (두 단계 위)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# [2] 서비스별 인증서/키 저장 경로 (프로젝트 루트 기준)
SERVICE_CERT_PATHS = {
    "vault": PROJECT_ROOT / "docker/vault/certs",
    "elk": PROJECT_ROOT / "docker/elk/certs",
    "keycloak": PROJECT_ROOT / "docker/keycloak/certs",
    "bitwarden": PROJECT_ROOT / "docker/bitwarden/certs",   # [추가]
}

DEFAULT_CERT_DAYS = 730

# [3] SAN(subjectAltName) 자동 구성 함수
def make_san(service: str, extra_san: Optional[List[str]] = None) -> str:
    san_base = [
        f"DNS:localhost",
        f"DNS:{service}",
        f"IP:127.0.0.1",
    ]
    if extra_san:
        san_base.extend(extra_san)
    return ", ".join(san_base)

# [4] openssl로 인증서/키 생성
def openssl_generate_cert(
    cert_dir: Path,
    common_name: str,
    san: str,
    days: int,
    overwrite: bool = False,
    service: str = "",
    logger=print
):
    cert_file = cert_dir / f"{common_name}.crt"
    key_file = cert_dir / f"{common_name}.key"
    if cert_file.exists() and key_file.exists() and not overwrite:
        logger(f"[SKIP] {service} 인증서/키 이미 존재 (덮어쓰기 안함): {cert_file}")
        return False
    cert_dir.mkdir(parents=True, exist_ok=True)
    subj = f"/CN={common_name}"
    cmd = [
        "openssl", "req", "-x509", "-nodes",
        "-newkey", "rsa:2048",
        "-keyout", str(key_file),
        "-out", str(cert_file),
        "-days", str(days),
        "-subj", subj,
        "-addext", f"subjectAltName = {san}",
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        logger(f"[OK] {service} 인증서/키 생성 완료: {cert_file}")
        return True
    except subprocess.CalledProcessError as e:
        logger(f"[FAIL] {service} 인증서 생성 실패\n{e.stderr.decode()}")
        return False

# [5] 인증서 생성 전체 프로세스
def generate_certificates(
    services: List[str],
    days: int = DEFAULT_CERT_DAYS,
    overwrite: bool = False,
    extra_san: Optional[List[str]] = None,
    logger=print
) -> str:
    """
    주요 서비스용 인증서/키 파일 자동 생성
    - SAN 및 CN 자동 구성, 기존 파일 보존(기본)
    """
    results = []
    logger("===[인증서 자동 생성]===")
    for service in services:
        cert_dir = SERVICE_CERT_PATHS.get(service)
        if not cert_dir:
            logger(f"[WARN] 지원하지 않는 서비스: {service}")
            results.append(f"[WARN] 지원하지 않는 서비스: {service}")
            continue
        cn = service
        san = make_san(service, extra_san)
        ok = openssl_generate_cert(cert_dir, cn, san, days, overwrite=overwrite, service=service, logger=logger)
        if ok:
            results.append(f"[OK] {service} 인증서 생성 완료")
        else:
            results.append(f"[FAIL/SKIP] {service} 인증서 생성 실패 또는 이미 존재")
    logger(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 인증서 생성 작업 완료.")
    return "\n".join(results)
