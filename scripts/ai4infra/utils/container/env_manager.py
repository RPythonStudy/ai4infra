#!/usr/bin/env python3

import os
import subprocess
from pathlib import Path

import yaml
from dotenv import load_dotenv

from common.logger import log_debug, log_error, log_info

load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT")
BASE_DIR = os.getenv("BASE_DIR", "/opt/ai4infra")


def extract_env_vars(env_path: str, section: str) -> dict:
    """지정된 섹션(# SECTION) 아래 key=value 쌍을 추출"""
    section_header = f"# {section.upper()}"
    env_vars, in_section = {}, False

    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                in_section = False
                continue
            if line.startswith("#"):
                in_section = (line == section_header)
                continue
            if in_section and "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()
    return env_vars


def extract_config_vars(service: str) -> dict:
    """./config/{service}.yml 읽고 ${PROJECT_ROOT}, ${BASE_DIR} 치환"""
    config_path = Path(f"./config/{service}.yml")
    if not config_path.exists():
        log_info(f"[extract_config_vars] 해당서비스명.yml 파일 없음: {config_path}")
        return {}

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        log_info(f"[extract_config_vars] YAML 파싱 실패: {e}")
        return {}

    def sub_vars(v):
        if isinstance(v, str):
            return v.replace("${PROJECT_ROOT}", PROJECT_ROOT).replace("${BASE_DIR}", BASE_DIR)
        if isinstance(v, dict):
            return {k: sub_vars(val) for k, val in v.items()}
        if isinstance(v, list):
            return [sub_vars(val) for val in v]
        return v

    return sub_vars(data)


def generate_env(service: str) -> str:

    # 1) 기본 변수 추출
    env_vars = extract_env_vars(".env", service)
    config_vars = extract_config_vars(service)

    # 2) config_vars에서 환경변수 후보만 필터링
    exclude_keys = {"path", "permissions", "tls"}
    config_env_vars = {
        k: v for k, v in config_vars.items()
        if k not in exclude_keys and not isinstance(v, dict)
    }

    # 3) env_vars 섹션이 있으면 그 내용을 추가
    if "env_vars" in config_vars and isinstance(config_vars["env_vars"], dict):
        config_env_vars.update(config_vars["env_vars"])

    # 병합: .env > config_ENV > path→DATA_DIR 변환 변수
    merged = {**env_vars, **config_env_vars}

    # 3) path.* → DATA_DIR / CERTS_DIR / CONF_DIR 자동 생성
    paths = config_vars.get("path", {})

    if "data" in paths:
        merged["DATA_DIR"] = paths["data"]

    if "private_key" in paths:
        merged["CERTS_DIR"] = str(Path(paths["private_key"]).parent)

    if "config" in paths:
        merged["CONF_DIR"] = paths["config"]

    # 4) 저장할 디렉터리
    service_dir = Path(f"{BASE_DIR}/{service}")
    output_file = service_dir / ".env"

    if not service_dir.exists():
        log_info(f"[generate_env] 경로 없음: {service_dir}")
        return ""

    if not merged:
        log_info(f"[generate_env] {service} 환경변수 없음 → .env 생성 생략")
        return ""

    # 5) tmp 파일 작성
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as tmp:
        for k, v in merged.items():
            tmp.write(f"{k}={v}\n")
        tmp_path = tmp.name

    # 6) 파일 이동 및 권한
    try:
        subprocess.run(
            ["sudo", "mv", tmp_path, str(output_file)],
            check=True, capture_output=True, text=True
        )

        owner = "bitwarden" if service == "bitwarden" else "root"
        subprocess.run(
            ["sudo", "chown", f"{owner}:{owner}", str(output_file)],
            check=True, capture_output=True, text=True
        )
        subprocess.run(
            ["sudo", "chmod", "600", str(output_file)],
            check=True, capture_output=True, text=True
        )

        log_info(f"[generate_env] {service.upper()} .env 생성 완료 → {output_file} (소유자: {owner})")

    except subprocess.CalledProcessError as e:
        log_error(f"[generate_env] 파일 이동/권한 설정 실패: {e.stderr}")
        if Path(tmp_path).exists():
            os.unlink(tmp_path)
        return ""

    return str(output_file)
