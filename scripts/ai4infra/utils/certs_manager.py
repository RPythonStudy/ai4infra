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

# Standard library imports
import os
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile
from functools import wraps
import yaml

# Third-party imports
from dotenv import load_dotenv
from common.logger import log_info, log_warn, log_error
from common.load_config import load_config

load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT")
BASE_DIR = os.getenv("BASE_DIR", "/opt/ai4infra")
BITWARDEN_DOMAIN = "bitwarden.ai4infra.internal"
CA_DIR = Path(f"{BASE_DIR}/certs/ca")
CA_KEY = CA_DIR / "rootCA.key"
CA_CERT = CA_DIR / "rootCA.pem"  # 전역 Root CA 인증서 (PEM)


def create_root_ca(overwrite: bool = False) -> bool:
    
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
                "-subj",
                "/C=KR/ST=Seoul/O=AI4INFRA/CN=AI4INFRA-Root-CA",
                "-out",
                str(CA_CERT),
            ],
            check=True,
        )

        log_info(f"[create_root_ca] Root CA 생성 완료 → {CA_CERT}")
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"[create_root_ca] OpenSSL 호출 실패: {e}")
        return False
    except Exception as e:
        log_error(f"[create_root_ca] 예외 발생: {e}")
        return False

def verify_root_ca() -> bool:
  
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
    except Exception as e:
        log_error(f"[verify_root_ca] 예외 발생: {e}")
        return False

def generate_root_ca_if_needed() -> bool:
    """
    Root CA가 없으면 새로 생성하고, 있으면 그대로 사용
    """
    if CA_CERT.exists() and CA_KEY.exists():
        log_info("[generate_root_ca_if_needed] 기존 Root CA 유지")
        return True

    log_info("[generate_root_ca_if_needed] Root CA 없음 → 새로 생성합니다.")
    return create_root_ca(overwrite=False)

def get_service_cert_paths(service: str) -> tuple[Path, Path, Path]:

    base = Path(BASE_DIR) / service / "certs"
    key_path = base / "private.key"
    csr_path = base / "request.csr"
    cert_path = base / "certificate.crt"
    return key_path, csr_path, cert_path

def build_default_san(service: str) -> str:
    """
    서비스 이름을 기반으로 기본 SubjectAltName 문자열을 구성

    예) postgres → DNS:postgres,DNS:ai4infra-postgres,IP:127.0.0.1
    """
    dns_entries = [
        service,
        f"ai4infra-{service}",
        f"{service}.ai4infra.internal",
        "localhost",
    ]
    ip_entries = [
        "127.0.0.1",
    ]

    san_parts = [f"DNS:{d}" for d in dns_entries] + [f"IP:{ip}" for ip in ip_entries]
    return ",".join(san_parts)

def create_service_key(service: str, key_path: Path) -> bool:
    """
    서비스 private key 생성
    """
    try:
        key_dir = key_path.parent
        subprocess.run(["sudo", "mkdir", "-p", str(key_dir)], check=True)

        subprocess.run(
            ["sudo", "openssl", "genrsa", "-out", str(key_path), "4096"],
            check=True,
        )
        log_info(f"[create_service_key] {service} key 생성 완료: {key_path}")
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"[create_service_key] OpenSSL 호출 실패: {e}")
        return False
    except Exception as e:
        log_error(f"[create_service_key] 예외 발생: {e}")
        return False

def create_service_csr(service: str, key_path: Path, csr_path: Path) -> bool:
    """
    서비스 CSR 생성
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
                f"/C=KR/ST=Seoul/O=AI4INFRA/CN={service}.ai4infra.internal",
            ],
            check=True,
        )
        log_info(f"[create_service_csr] {service} CSR 생성: {csr_path}")
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"[create_service_csr] OpenSSL 호출 실패: {e}")
        return False
    except Exception as e:
        log_error(f"[create_service_csr] 예외 발생: {e}")
        return False

def sign_service_cert_with_ca(
    service: str,
    csr_path: Path,
    cert_path: Path,
    san: str,
) -> bool:
    """
    CSR을 Root CA로 서명하여 서버 인증서 생성

    Parameters
    ----------
    san : str
        SubjectAltName 문자열 (예: "DNS:...,IP:127.0.0.1")
    """
    try:
        cert_dir = cert_path.parent
        subprocess.run(["sudo", "mkdir", "-p", str(cert_dir)], check=True)

        with NamedTemporaryFile("w", delete=False, suffix=".cnf") as tmp:
            tmp_path = Path(tmp.name)
            tmp.write("[ req ]\n")
            tmp.write("distinguished_name = req_distinguished_name\n")
            tmp.write("req_extensions = v3_req\n")
            tmp.write("[ req_distinguished_name ]\n")
            tmp.write("[ v3_req ]\n")
            tmp.write(f"subjectAltName = {san}\n")

        log_info(
            f"[sign_service_cert_with_ca] {service} cert CA 서명 (SAN={san}) → {cert_path}"
        )

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
                "365",
                "-sha256",
                "-extensions",
                "v3_req",
                "-extfile",
                str(tmp_path),
            ],
            check=True,
        )

        tmp_path.unlink(missing_ok=True)
        return True

    except subprocess.CalledProcessError as e:
        log_error(f"[sign_service_cert_with_ca] OpenSSL 호출 실패: {e}")
        return False
    except Exception as e:
        log_error(f"[sign_service_cert_with_ca] 예외 발생: {e}")
        return False

def verify_service_cert(service: str, cert_path: Path) -> bool:
    """
    서비스 인증서를 Root CA로 검증
    """
    try:
        result = subprocess.run(
            [
                "openssl",
                "verify",
                "-CAfile",
                str(CA_CERT),
                str(cert_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        log_info(f"[verify_service_cert] OK: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"[verify_service_cert] 검증 실패: {e.stderr.strip()}")
        return False
    except Exception as e:
        log_error(f"[verify_service_cert] 예외 발생: {e}")
        return False

def deploy_root_ca_to_service(service: str, ca_src: Path) -> bool:
    """
    서비스 디렉터리 내부 certs/에 Root CA 복사

    - 기본 파일명: rootCA.crt
    - Bitwarden 의 경우: bwdata/ssl/<domain>/ca.crt
    """
    try:
        if service == "bitwarden":
            ssl_dir = Path(BASE_DIR) / "bitwarden" / "bwdata" / "ssl" / BITWARDEN_DOMAIN
            subprocess.run(["sudo", "mkdir", "-p", str(ssl_dir)], check=True)
            dst = ssl_dir / "ca.crt"
        else:
            cert_dir = Path(BASE_DIR) / service / "certs"
            subprocess.run(["sudo", "mkdir", "-p", str(cert_dir)], check=True)
            dst = cert_dir / "rootCA.crt"

        subprocess.run(
            ["sudo", "cp", "-a", str(ca_src), str(dst)],
            check=True,
        )
        log_info(f"[deploy_root_ca_to_service] Root CA 복사 완료: {dst}")
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"[deploy_root_ca_to_service] 복사 실패: {e}")
        return False
    except Exception as e:
        log_error(f"[deploy_root_ca_to_service] 예외 발생: {e}")
        return False

def fix_bitwarden_cert_permissions() -> None:
    """
    Bitwarden SSL 디렉터리 권한 정리

    - private.key: 600
    - certificate.crt, ca.crt: 644

    소유자/그룹(uid/gid)은 apply_service_permissions()에서
    config/bitwarden.yml의 permissions 설정을 기준으로 일괄 관리한다.
    """
    ssl_dir = Path(BASE_DIR) / "bitwarden" / "bwdata" / "ssl" / BITWARDEN_DOMAIN

    if not ssl_dir.exists():
        log_warn(
            f"[fix_bitwarden_cert_permissions] Bitwarden ssl 디렉터리가 없습니다: {ssl_dir}"
        )
        return

    try:
        # private key
        key_path = ssl_dir / "private.key"
        if key_path.exists():
            subprocess.run(
                ["sudo", "chmod", "600", str(key_path)],
                check=False,
            )

        # server cert / CA cert
        cert_paths = [ssl_dir / "certificate.crt", ssl_dir / "ca.crt"]
        for path in cert_paths:
            if path.exists():
                subprocess.run(
                    ["sudo", "chmod", "644", str(path)],
                    check=False,
                )

        log_info("[fix_bitwarden_cert_permissions] Bitwarden cert 권한 정리 완료")

    except subprocess.CalledProcessError as e:
        log_error(f"[fix_bitwarden_cert_permissions] 실패: {e}")

def resolve_cert_paths(service: str) -> dict:
    """
    인증서 경로를 일원화하여 반환합니다.

    원칙:
      1) config/<service>.yml 의 path.* 가 있으면 절대 신뢰하여 그대로 사용
      2) 없으면 BASE_DIR/<service>/certs/ 를 fallback 으로 사용
      3) Bitwarden 은 독립 구조 유지
    """

    cfg_path = f"{PROJECT_ROOT}/config/{service}.yml"

    try:
        yml = load_config(cfg_path, section="path") or {}
    except Exception:
        yml = {}

    # ---------------------------------------------------------
    # Bitwarden 특수 구조
    # ---------------------------------------------------------
    if service == "bitwarden":
        base = Path(BASE_DIR) / "bitwarden" / "bwdata" / "ssl" / BITWARDEN_DOMAIN

        key = Path(yml.get("private_key", base / "private.key"))
        csr = Path(yml.get("csr", key.parent / "request.csr"))
        crt = Path(yml.get("service_crt", base / "certificate.crt"))
        root_ca = Path(yml.get("root_ca", base / "ca.crt"))

        return {
            "key": key,
            "csr": csr,
            "crt": crt,
            "root_ca": root_ca,
        }

    # ---------------------------------------------------------
    # 기본 서비스 구조
    # ---------------------------------------------------------

    # fallback base 경로 (path.* 가 없을 경우 사용)
    base = Path(BASE_DIR) / service / "certs"

    key = Path(yml.get("private_key", base / "private.key"))
    csr = Path(yml.get("csr", key.parent / "request.csr"))
    crt = Path(yml.get("service_crt", base / "certificate.crt"))
    root_ca = Path(yml.get("root_ca", base / "rootCA.crt"))

    return {
        "key": key,
        "csr": csr,
        "crt": crt,
        "root_ca": root_ca,
    }

def create_service_certificate(service: str, san: str | None = None) -> bool:
    """
    서비스 인증서 생성:
      1) 경로는 resolve_cert_paths()에서 일원화
      2) key → csr → crt 순 생성
      3) rootCA 복사는 deploy_root_ca_to_service()가 전담
    """
    try:
        # 1) 통합 경로 결정
        paths = resolve_cert_paths(service)
        key_path = paths["key"]
        csr_path = paths["csr"]
        cert_path = paths["crt"]

        # 2) 이미 key + cert 존재하면 skip
        if key_path.exists() and cert_path.exists():
            deploy_root_ca_to_service(service, CA_CERT)
            return True

        # 3) SAN 결정
        san_value = san or build_default_san(service)

        # 4) key / csr / crt 생성
        if not create_service_key(service, key_path):
            return False

        if not create_service_csr(service, key_path, csr_path):
            return False

        if not sign_service_cert_with_ca(service, csr_path, cert_path, san_value):
            return False

        if not verify_service_cert(service, cert_path):
            return False

        # 5) rootCA 복사
        if not deploy_root_ca_to_service(service, CA_CERT):
            return False

        return True

    except Exception as e:
        log_error(f"[create_service_certificate] {e}")
        return False

def apply_service_permissions(service: str) -> bool:
    """
    최종 전략에 맞춘 퍼미션 설정 함수
    """
    try:
        cfg_path = f"{PROJECT_ROOT}/config/{service}.yml"

        # load_config로 설정 일관성 유지
        try:
            cfg = load_config(cfg_path) or {}
        except Exception:
            log_warn(f"[apply_service_permissions] 설정 로드 실패: {cfg_path}")
            return False

        perms = cfg.get("permissions", {})
        uid = perms.get("uid")
        gid = perms.get("gid")
        data_mode = str(perms.get("data_dir_mode", "700"))
        key_mode = str(perms.get("key_mode", "600"))
        cert_mode = str(perms.get("cert_mode", "644"))

        service_dir = Path(BASE_DIR) / service
        path_cfg = cfg.get("path", {})

        # -----------------------------------------
        # 1) data_dir 결정 (bitwarden만 예외)
        # -----------------------------------------
        data_path = path_cfg.get("data")

        if service == "bitwarden":
            data_dir = service_dir / "bwdata"
        elif data_path:
            data_dir = Path(data_path)
        else:
            data_dir = service_dir / "data"

        # -----------------------------------------
        # 2) cert_dir 결정 (private_key 기반)
        # -----------------------------------------
        private_key_path = path_cfg.get("private_key")

        if service == "bitwarden":
            cert_dir = service_dir / "bwdata" / "ssl" / BITWARDEN_DOMAIN
        elif private_key_path:
            cert_dir = Path(private_key_path).parent
        else:
            cert_dir = service_dir / "certs"

        # -----------------------------------------
        # 3) 서비스 루트 소유권
        # -----------------------------------------
        if service_dir.exists() and uid is not None and gid is not None:
            subprocess.run(
                ["sudo", "chown", "-R", f"{uid}:{gid}", str(service_dir)],
                check=False
            )
            log_info(f"[apply_service_permissions] 소유권 변경 → {service_dir} ({uid}:{gid})")

        # -----------------------------------------
        # 4) data_dir 권한
        # -----------------------------------------
        if data_dir.exists():
            subprocess.run(
                ["sudo", "chmod", "-R", data_mode, str(data_dir)],
                check=False
            )
            log_info(f"[apply_service_permissions] data 권한({data_mode}) 적용 → {data_dir}")

        # -----------------------------------------
        # 5) cert_dir 권한 (key_mode / cert_mode 구분)
        # -----------------------------------------
        if cert_dir.exists():
            key_paths = set()
            key_count = 0

            for pattern in ("*.key", "*key.pem", "*_key.pem"):
                for path in cert_dir.glob(pattern):
                    key_paths.add(path)
                    subprocess.run(["sudo", "chmod", key_mode, str(path)], check=False)
                    key_count += 1

            if key_count > 0:
                log_info(
                    f"[apply_service_permissions] Private key {key_count}개 ({key_mode}) 적용"
                )

            cert_count = 0
            for path in cert_dir.glob("*.crt"):
                if path not in key_paths:
                    subprocess.run(["sudo", "chmod", cert_mode, str(path)], check=False)
                    cert_count += 1

            for path in cert_dir.glob("*.pem"):
                if path not in key_paths:
                    subprocess.run(["sudo", "chmod", cert_mode, str(path)], check=False)
                    cert_count += 1

            if cert_count > 0:
                log_info(
                    f"[apply_service_permissions] Certificate {cert_count}개 ({cert_mode}) 적용"
                )

        # -----------------------------------------
        # 6) Bitwarden 보정
        # -----------------------------------------
        if service == "bitwarden":
            try:
                fix_bitwarden_cert_permissions()
            except Exception as e:
                log_warn(f"[apply_service_permissions] Bitwarden 보정 실패: {e}")

        log_info(f"[apply_service_permissions] {service} 권한 정리 완료")
        return True

    except Exception as e:
        log_error(f"[apply_service_permissions] 예외 발생: {e}")
        return False

def install_root_ca_windows():
    """
    WSL에서 생성한 Root CA를 Windows 신뢰 저장소에 설치
    - certutil -addstore "Root" rootCA.cer
    """
    root_ca_path = Path("/opt/ai4infra/certs/ca/rootCA.pem")
    if not root_ca_path.exists():
        print("[ERROR] Root CA 파일이 존재하지 않습니다:", root_ca_path)
        return False

    # Windows %USERPROFILE% 가져오기 (CMD 출력 = cp949)
    try:
        win_home_raw = subprocess.check_output(
            ["cmd.exe", "/c", "echo %USERPROFILE%"],
            stderr=subprocess.DEVNULL,  # UNC 경고 숨김
        )
        win_home = win_home_raw.decode("cp949").strip()
        win_home = win_home.replace("\\", "/")
    except Exception as e:
        print(f"[ERROR] USERPROFILE 경로를 가져오지 못했습니다: {e}")
        return False

    target = f"{win_home}/Downloads/ai4infra-rootCA.cer"

    # Root CA를 Windows로 복사
    subprocess.run(["cp", str(root_ca_path), f"/mnt/c{target[2:]}"], check=True)
    print(f"[INFO] Root CA 복사 완료 → {target}")

    # certutil로 Root CA를 신뢰 저장소에 추가
    try:
        result = subprocess.run(
            ["cmd.exe", "/c", f'certutil -addstore "Root" "{target}"'],
            capture_output=True,
        )
        stdout = result.stdout.decode("cp949", errors="ignore")
        stderr = result.stderr.decode("cp949", errors="ignore")

        print("[INFO] certutil stdout:")
        print(stdout)
        print("[INFO] certutil stderr:")
        print(stderr)

        if result.returncode == 0:
            print("[SUCCESS] Windows Trusted Root Store에 Root CA 설치 완료")
            return True
        else:
            print("[ERROR] Root CA 설치 실패")
            return False

    except Exception as e:
        print(f"[ERROR] certutil 실행 중 예외 발생: {e}")
        return False
