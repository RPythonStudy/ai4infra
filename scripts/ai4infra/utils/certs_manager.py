#!/usr/bin/env python3
"""
파일명: scripts/ai4infra/utils/certs_manager.py

AI4INFRA 인증서 관리 모듈 (리팩터링 버전)

주요 기능:
  1. Root CA 생성 및 검증
  2. 서비스별 서버 인증서 생성 (key → csr → crt)
  3. 서비스 인증서의 CA chain 검증
  4. Root CA를 서비스 디렉터리로 복사 (rootCA.crt / ca.crt)

설계 원칙:
  - 각 함수는 단일 책임(SRP)을 유지한다.
  - 상위 함수(create_service_certificate)는 하위 단계를 orchestration 한다.
  - OpenSSL 호출은 subprocess를 통해 수행한다.
  - 경로 구조는 BASE_DIR 및 서비스 이름 기반으로 일관성을 유지한다.
  - 서비스별 key/cert 파일명은 최대한 통일한다.
    * private.key
    * certificate.crt
  - Root CA 원본은 BASE_DIR/certs/ca/rootCA.pem 을 기준으로 관리하고,
    각 서비스 디렉터리에는 복사본(rootCA.crt 또는 ca.crt)만 둔다.

변경이력:
  - 2025-11-19: 최초 구현 시작 (BenKorea)
  - 2025-11-20: 구조 개선, SAN 기본값 추가, Bitwarden 경로 반영
  - 2025-11-20: 서비스별 파일명 통일(private.key/certificate.crt),
                Root CA 전역 보존(rootCA.pem) + 서비스별 복사로 정리
"""

import os
import shutil
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict

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
# Root CA 경로 정의 (전역 기준)
# -------------------------------------------------------------------
CA_DIR = Path(f"{BASE_DIR}/certs/ca")
CA_KEY = CA_DIR / "rootCA.key"
CA_CERT = CA_DIR / "rootCA.pem"  # 전역 Root CA 인증서 (PEM)


# -------------------------------------------------------------------
# Root CA 생성
# -------------------------------------------------------------------
def create_root_ca(overwrite: bool = False) -> bool:
    """
    Root CA 생성
    - private key 생성 (4096-bit)
    - self-signed Root CA 인증서 생성 (10년 유효기간)
    - 기존 파일이 있으면 overwrite=False 에서는 유지

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
            check=True,
        )

        log_info("[create_root_ca] Root CA self-signed 인증서 생성 중...")
        subprocess.run(
            [
                "sudo",
                "openssl",
                "req",
                "-x509",
                "-new",
                "-nodes",
                "-key",
                str(CA_KEY),
                "-sha256",
                "-days",
                "3650",
                "-out",
                str(CA_CERT),
                "-subj",
                "/CN=AI4INFRA-Root-CA",
            ],
            check=True,
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
            capture_output=True,
            text=True,
            check=True,
        )

        preview = result.stdout[:400]
        log_info(f"[verify_root_ca] Root CA 인증서 정보:\n{preview}")
        return True

    except subprocess.CalledProcessError as e:
        log_error(f"[verify_root_ca] OpenSSL 검증 실패: {e.stderr}")
        return False


# -------------------------------------------------------------------
# SAN 기본값 생성
# -------------------------------------------------------------------
def build_default_san(service: str) -> str:
    """
    서비스 이름을 기반으로 기본 SAN(subjectAltName) 문자열 생성
    - DNS:localhost
    - IP:127.0.0.1
    - DNS:{service}
    - DNS:ai4infra-{service}
    - DNS:{hostname}
    """
    entries = {
        "DNS:localhost",
        "IP:127.0.0.1",
        f"DNS:{service}",
        f"DNS:ai4infra-{service}",
    }

    try:
        hostname = os.uname().nodename
        if hostname:
            entries.add(f"DNS:{hostname}")
    except Exception:
        pass

    return ",".join(sorted(entries))


# -------------------------------------------------------------------
# 서비스 인증서 생성 용 하위 함수들 (각각 단일 책임)
# -------------------------------------------------------------------
def create_service_key(service: str, key_path: Path) -> bool:
    """
    서비스 private key 생성 (RSA 2048)
    """
    try:
        subprocess.run(
            ["sudo", "openssl", "genrsa", "-out", str(key_path), "2048"],
            check=True,
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
            [
                "sudo",
                "openssl",
                "req",
                "-new",
                "-key",
                str(key_path),
                "-out",
                str(csr_path),
                "-subj",
                f"/CN={service}",
            ],
            check=True,
        )
        log_info(f"[create_service_csr] {service} CSR 생성: {csr_path}")
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"[create_service_csr] 실패: {e}")
        return False


def sign_service_cert_with_ca(
    service: str, csr_path: Path, cert_path: Path, san: str
) -> bool:
    """
    Root CA로 서비스 CSR을 서명하여 server 인증서 생성
    - SAN은 subjectAltName= 에 전달
    """
    if not CA_CERT.exists() or not CA_KEY.exists():
        log_error("[sign_service_cert_with_ca] Root CA가 먼저 생성되어야 합니다.")
        return False

    tmp_path = None
    try:
        # SAN 설정용 임시 파일 작성
        with NamedTemporaryFile("w", delete=False) as tmp:
            tmp.write(f"subjectAltName={san}")
            tmp_path = tmp.name

        subprocess.run(
            [
                "sudo",
                "openssl",
                "x509",
                "-req",
                "-in",
                str(csr_path),
                "-CA",
                str(CA_CERT),
                "-CAkey",
                str(CA_KEY),
                "-CAcreateserial",
                "-out",
                str(cert_path),
                "-days",
                "825",
                "-sha256",
                "-extfile",
                tmp_path,
            ],
            check=True,
        )

        subprocess.run(["sudo", "chmod", "644", str(cert_path)], check=True)
        log_info(
            f"[sign_service_cert_with_ca] {service} cert 생성 완료: {cert_path}"
        )
        return True

    except subprocess.CalledProcessError as e:
        log_error(f"[sign_service_cert_with_ca] 실패: {e}")
        return False

    finally:
        if tmp_path and Path(tmp_path).exists():
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def verify_service_cert(service: str, cert_path: Path) -> bool:
    """
    Root CA 기반 서비스 인증서 검증
    """
    try:
        result = subprocess.run(
            ["openssl", "verify", "-CAfile", str(CA_CERT), str(cert_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        log_info(f"[verify_service_cert] OK: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"[verify_service_cert] 실패: {e.stderr}")
        return False


# -------------------------------------------------------------------
# 서비스별 인증서 경로 계산
# -------------------------------------------------------------------
def get_service_cert_paths(service: str) -> Dict[str, Path]:
    """
    서비스별 인증서 경로를 반환한다.

    공통 규칙:
      - key 파일명: private.key
      - cert 파일명: certificate.crt
      - CSR 파일명: {service}.csr

    Bitwarden 전용 규칙:
      - 디렉터리: {BASE_DIR}/bitwarden/bwdata/nginx/ssl
      - Root CA 파일명: ca.crt (전역 rootCA.pem 복사본)
    """
    base = BASE_DIR

    # Bitwarden 전용 경로 (공식 구조 기준)
    if service == "bitwarden":
        certs_dir = Path(f"{base}/bitwarden/bwdata/nginx/ssl")
        return {
            "certs_dir": certs_dir,
            "key": certs_dir / "private.key",
            "csr": certs_dir / "bitwarden.csr",
            "cert": certs_dir / "certificate.crt",
            "ca": certs_dir / "ca.crt",
        }

    # 일반 서비스 기본 구조
    certs_dir = Path(f"{base}/{service}/certs")
    return {
        "certs_dir": certs_dir,
        "key": certs_dir / "private.key",
        "csr": certs_dir / f"{service}.csr",
        "cert": certs_dir / "certificate.crt",
        "ca": certs_dir / "rootCA.crt",
    }


# -------------------------------------------------------------------
# Root CA 없으면 자동 생성
# -------------------------------------------------------------------
def generate_root_ca_if_needed(overwrite: bool = False) -> bool:
    """
    Root CA가 없으면 자동 생성.
    """
    if CA_KEY.exists() and CA_CERT.exists() and not overwrite:
        log_info("[generate_root_ca_if_needed] 기존 Root CA 유지")
        return True

    log_info("[generate_root_ca_if_needed] Root CA 없음 → 새로 생성합니다.")
    return create_root_ca(overwrite=overwrite)


# -------------------------------------------------------------------
# 서비스 디렉터리로 Root CA 복사
# -------------------------------------------------------------------
def deploy_root_ca_to_service(service: str, ca_dest: Path) -> bool:
    """
    전역 Root CA(CA_CERT)를 서비스 디렉터리로 복사한다.
    Bitwarden일 경우 ca_dest는 ca.crt,
    일반 서비스는 rootCA.crt를 사용한다.
    """
    if not CA_CERT.exists():
        log_error("[deploy_root_ca_to_service] Root CA 인증서가 없습니다.")
        return False

    try:
        ca_dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["sudo", "cp", str(CA_CERT), str(ca_dest)],
            check=True,
        )
        subprocess.run(["sudo", "chmod", "644", str(ca_dest)], check=True)
        log_info(
            f"[deploy_root_ca_to_service] Root CA 복사 완료 → {service}: {ca_dest}"
        )
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"[deploy_root_ca_to_service] 실패: {e}")
        return False


# -------------------------------------------------------------------
# Bitwarden 전용 권한 설정
# -------------------------------------------------------------------
def fix_bitwarden_cert_permissions() -> None:
    """
    Bitwarden SSL 디렉터리 권한 정리
    - 소유자: bitwarden:bitwarden
    - private.key: 600
    - certificate.crt, ca.crt: 644
    """
    ssl_dir = f"{BASE_DIR}/bitwarden/bwdata/nginx/ssl"

    try:
        subprocess.run(
            ["sudo", "chown", "-R", "bitwarden:bitwarden", ssl_dir],
            check=True,
        )
        subprocess.run(
            ["sudo", "chmod", "600", f"{ssl_dir}/private.key"], check=False
        )
        subprocess.run(
            ["sudo", "chmod", "644", f"{ssl_dir}/certificate.crt"], check=False
        )
        subprocess.run(
            ["sudo", "chmod", "644", f"{ssl_dir}/ca.crt"], check=False
        )
        log_info("[fix_bitwarden_cert_permissions] Bitwarden cert 권한 정리 완료")
    except subprocess.CalledProcessError as e:
        log_error(f"[fix_bitwarden_cert_permissions] 실패: {e}")


# -------------------------------------------------------------------
# 서비스 full chain 인증서 생성 (상위 Orchestration 함수)
# -------------------------------------------------------------------
def create_service_certificate(
    service: str,
    overwrite: bool = False,
    san: str | None = None,
) -> bool:
    """
    서비스 full chain 인증서 생성 (최상위 함수)

    Parameters
    ----------
    service : str
        서비스 이름(vault, bitwarden, postgres 등)
    overwrite : bool
        기존 key/cert/ca 파일이 있어도 덮어쓸지 여부
    san : str, optional
        Subject Alternative Name 문자열.
        None이면 build_default_san(service)를 사용.

    Returns
    -------
    bool
        전체 과정 성공 여부
    """
    # Root CA 준비
    if not generate_root_ca_if_needed():
        return False

    paths = get_service_cert_paths(service)
    certs_dir: Path = paths["certs_dir"]
    key_path: Path = paths["key"]
    csr_path: Path = paths["csr"]
    cert_path: Path = paths["cert"]
    ca_path: Path = paths["ca"]

    # 기존 파일이 있고 overwrite=False이면 스킵
    if (
        key_path.exists()
        and cert_path.exists()
        and ca_path.exists()
        and not overwrite
    ):
        log_info(
            f"[create_service_certificate] {service} 인증서 이미 존재, "
            f"overwrite=False → 재생성하지 않음"
        )
        return True

    san_value = san or build_default_san(service)

    try:
        # 디렉터리 생성
        subprocess.run(["sudo", "mkdir", "-p", str(certs_dir)], check=True)

        # 1) key 생성
        if not create_service_key(service, key_path):
            return False

        # 2) CSR 생성
        if not create_service_csr(service, key_path, csr_path):
            return False

        # 3) CA 서명 (cert 생성)
        if not sign_service_cert_with_ca(service, csr_path, cert_path, san_value):
            return False

        # 4) chain 검증
        if not verify_service_cert(service, cert_path):
            return False

        # 5) 서비스 디렉터리로 Root CA 복사
        if not deploy_root_ca_to_service(service, ca_path):
            return False

        # 6) Bitwarden 권한 정리
        if service == "bitwarden":
            fix_bitwarden_cert_permissions()

        log_info(f"[create_service_certificate] {service} full chain 생성 완료")
        return True

    except Exception as e:
        log_error(f"[create_service_certificate] 예외 발생: {e}")
        return False
