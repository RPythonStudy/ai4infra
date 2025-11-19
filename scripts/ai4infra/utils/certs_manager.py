#!/usr/bin/env python3
"""
파일명: scripts/ai4infra/utils/certs_manager.py

AI4INFRA 인증서 관리 모듈

주요 기능 (최소 기능 기반):
  1. Root CA 생성
  2. Root CA X.509 검증
  3. 서비스별 서버 인증서 생성 (key → csr → crt)
  4. 서비스 인증서의 CA chain 검증

설계 원칙:
  - 각 함수는 하나의 역할(Single Responsibility Principle)을 유지한다.
  - 고수준 작업(create_service_certificate)은 하위 단계를 orchestration한다.
  - OpenSSL 호출은 subprocess를 통해 표준 입력/출력 기반으로 수행한다.
  - 경로 구조는 BASE_DIR 및 PROJECT_ROOT(.env) 기반으로 일관성 확보.
  - 권한 설정은 보안 최우선(600 for key, 644 for cert).

변경이력:
  - 2025-11-19: 최초 구현 시작 (BenKorea)
  - 2025-11-20: 함수 재정렬, 메타데이터 보완, 구조 개선
"""

import os
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile
from dotenv import load_dotenv
from common.logger import log_info, log_warn, log_error


# -------------------------------------------------------------------
# 환경변수 로딩
# -------------------------------------------------------------------
load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT")
BASE_DIR = os.getenv("BASE_DIR", "/opt/ai4infra")

if not BASE_DIR:
    log_warn("[certs_manager] BASE_DIR 환경변수를 찾을 수 없습니다.")


# -------------------------------------------------------------------
# Root CA 경로 정의
# -------------------------------------------------------------------
CA_DIR = Path(f"{BASE_DIR}/certs/ca")
CA_KEY = CA_DIR / "rootCA.key"
CA_CERT = CA_DIR / "rootCA.pem"


# -------------------------------------------------------------------
# Root CA 생성
# -------------------------------------------------------------------
def create_root_ca(overwrite: bool = False) -> bool:
    """
    Root CA 생성
    - private key 생성 (4096-bit)
    - self-signed Root CA 인증서 생성 (10년 유효기간)
    - 기존 파일이 있으면 overwrite 옵션이 False일 때 유지

    Parameters
    ----------
    overwrite : bool
        기존 rootCA.key, rootCA.pem을 덮어쓸지 여부

    Returns
    -------
    bool
        생성 성공 여부
    """
    try:
        if CA_CERT.exists() and CA_KEY.exists() and not overwrite:
            log_info(f"[create_root_ca] Root CA 이미 존재: {CA_CERT}")
            return True

        subprocess.run(["sudo", "mkdir", "-p", str(CA_DIR)], check=True)

        log_info("[create_root_ca] Root CA private key 생성 중...")
        subprocess.run(
            ["sudo", "openssl", "genrsa", "-out", str(CA_KEY), "4096"],
            check=True
        )

        log_info("[create_root_ca] Root CA self-signed 인증서 생성 중...")
        subprocess.run(
            [
                "sudo", "openssl", "req", "-x509", "-new", "-nodes",
                "-key", str(CA_KEY),
                "-sha256", "-days", "3650",
                "-out", str(CA_CERT),
                "-subj", "/CN=AI4INFRA-Root-CA"
            ],
            check=True
        )

        subprocess.run(["sudo", "chmod", "600", str(CA_KEY)], check=True)
        subprocess.run(["sudo", "chmod", "644", str(CA_CERT)], check=True)

        log_info(f"[create_root_ca] Root CA 생성 완료 → {CA_CERT}")
        return True

    except subprocess.CalledProcessError as e:
        log_error(f"[create_root_ca] 실패: {e}")
        return False


# -------------------------------------------------------------------
# Root CA 검증
# -------------------------------------------------------------------
def verify_root_ca() -> bool:
    """
    Root CA 인증서 검증
    - openssl x509 -text 로 인증서가 정상인지 검사
    - 인증서 내용의 일부를 미리보기 출력

    Returns
    -------
    bool
        검증 성공 여부
    """
    if not CA_CERT.exists():
        log_warn("[verify_root_ca] Root CA 인증서가 존재하지 않습니다.")
        return False

    try:
        log_info("[verify_root_ca] Root CA 인증서 분석 시작...")
        result = subprocess.run(
            ["openssl", "x509", "-in", str(CA_CERT), "-noout", "-text"],
            capture_output=True, text=True, check=True
        )

        preview = result.stdout[:400]
        log_info(f"[verify_root_ca] Root CA 인증서 정보:\n{preview}")
        return True

    except subprocess.CalledProcessError as e:
        log_error(f"[verify_root_ca] OpenSSL 검증 실패: {e.stderr}")
        return False


# -------------------------------------------------------------------
# 서비스 인증서 생성 용 하위 함수들 (각각 단일 책임 원칙)
# -------------------------------------------------------------------

def create_service_key(service: str, key_path: Path) -> bool:
    """
    서비스 private key 생성 (RSA 2048)
    """
    try:
        subprocess.run(
            ["sudo", "openssl", "genrsa", "-out", str(key_path), "2048"],
            check=True
        )
        subprocess.run(["sudo", "chmod", "600", str(key_path)], check=True)
        log_info(f"[create_service_key] {service} key 생성 완료: {key_path}")
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"[create_service_key] 실패: {e}")
        return False


def create_service_csr(service: str, key_path: Path, csr_path: Path) -> bool:
    """
    서비스 CSR 생성 (CN={service})
    """
    try:
        subprocess.run(
            ["sudo", "openssl", "req", "-new",
             "-key", str(key_path),
             "-out", str(csr_path),
             "-subj", f"/CN={service}"
             ],
            check=True
        )
        log_info(f"[create_service_csr] {service} CSR 생성: {csr_path}")
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"[create_service_csr] 실패: {e}")
        return False


def sign_service_cert_with_ca(service: str, csr_path: Path, cert_path: Path, san: str) -> bool:
    """
    Root CA로 서비스 CSR을 서명하여 server.crt 생성
    - SAN은 subjectAltName= 에 전달됨
    """

    if not CA_CERT.exists() or not CA_KEY.exists():
        log_error("[sign_service_cert_with_ca] Root CA가 먼저 생성되어야 합니다.")
        return False

    try:
        # WSL2/Ubuntu 호환성을 위해 SAN을 tempfile로 작성
        with NamedTemporaryFile("w", delete=False) as tmp:
            tmp.write(f"subjectAltName={san}")
            tmp_path = tmp.name

        subprocess.run(
            [
                "sudo", "openssl", "x509", "-req",
                "-in", str(csr_path),
                "-CA", str(CA_CERT),
                "-CAkey", str(CA_KEY),
                "-CAcreateserial",
                "-out", str(cert_path),
                "-days", "825",
                "-sha256",
                "-extfile", tmp_path,
            ],
            check=True
        )

        subprocess.run(["sudo", "chmod", "644", str(cert_path)], check=True)
        log_info(f"[sign_service_cert_with_ca] {service} cert 생성 완료: {cert_path}")
        return True

    except subprocess.CalledProcessError as e:
        log_error(f"[sign_service_cert_with_ca] 실패: {e}")
        return False


def verify_service_cert(service: str, cert_path: Path) -> bool:
    """
    Root CA 기반 서비스 인증서 검증
    """
    try:
        result = subprocess.run(
            ["openssl", "verify",
             "-CAfile", str(CA_CERT),
             str(cert_path)],
            capture_output=True, text=True, check=True
        )
        log_info(f"[verify_service_cert] OK: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"[verify_service_cert] 실패: {e.stderr}")
        return False


# -------------------------------------------------------------------
# 서비스 인증서 full chain 생성
# -------------------------------------------------------------------
def create_service_certificate(service: str) -> bool:
    """
    서비스 full chain 인증서 생성
    순서:
      1) private key 생성
      2) CSR 생성
      3) Root CA 서명하여 cert 생성
      4) 인증서 chain 검증

    Parameters
    ----------
    service : str
        vault, bitwarden, postgres, ldap, elk 등 서비스 이름

    Returns
    -------
    bool
        전체 과정 성공 여부
    """

    service_dir = Path(f"{BASE_DIR}/{service}/certs")
    key_path = service_dir / f"{service}.key"
    csr_path = service_dir / f"{service}.csr"
    cert_path = service_dir / f"{service}.crt"

    # SAN 기본 구조
    san = f"DNS:localhost,DNS:{service},IP:127.0.0.1"

    try:
        subprocess.run(["sudo", "mkdir", "-p", str(service_dir)], check=True)

        if not create_service_key(service, key_path):
            return False

        if not create_service_csr(service, key_path, csr_path):
            return False

        if not sign_service_cert_with_ca(service, csr_path, cert_path, san):
            return False

        if not verify_service_cert(service, cert_path):
            return False

        log_info(f"[create_service_certificate] {service} full chain 인증서 생성 완료")
        return True

    except Exception as e:
        log_error(f"[create_service_certificate] 예외 발생: {e}")
        return False
