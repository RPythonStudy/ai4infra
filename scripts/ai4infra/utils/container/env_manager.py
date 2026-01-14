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
    """
    지정된 섹션(# SECTION) 아래 key=value 쌍을 추출
    
    Notes
    -----
    # SECTION 뒤에 추가 텍스트가 있어도 인식
    예: # BITWARDEN, # BITWARDEN compose_vars 모두 인식
    """
    section_prefix = f"# {section.upper()}"
    env_vars, in_section = {}, False

    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                in_section = False
                continue
            if line.startswith("#"):
                # "# SECTION"으로 시작하면 매칭 (뒤에 텍스트 무시)
                in_section = line.startswith(section_prefix)
                continue
            if in_section and "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()
    return env_vars

def extract_config_vars(service: str) -> dict:
    """./config/{service}.yml 또는 apps/*/config/{service}.yml 읽고 변수 치환"""
    # 1. Default Path
    config_path = Path(f"./config/{service}.yml")
    
    # 2. Extension Path Search (if not in default)
    if not config_path.exists():
        # Search in apps/*/config/{service}.yml
        candidates = list(Path("apps").glob(f"*/config/{service}.yml"))
        if candidates:
            config_path = candidates[0] # Pick first match
    
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
            # 1. 고정 경로 치환
            v = v.replace("${PROJECT_ROOT}", PROJECT_ROOT).replace("${BASE_DIR}", BASE_DIR)
            # 2. 환경변수 치환 (.env 로드됨)
            return os.path.expandvars(v)
        if isinstance(v, dict):
            return {k: sub_vars(val) for k, val in v.items()}
        if isinstance(v, list):
            return [sub_vars(val) for val in v]
        return v

    return sub_vars(data)

def generate_env(service: str) -> str:

    # 1) 변수 수집 (.env < compose_vars < env_vars)
    # .env 파일의 변수를 기본으로 하되, YAML 설정이 덮어쓰도록 구성
    base_env = extract_env_vars(".env", service)
    config = extract_config_vars(service)
    
    # compose_vars: docker-compose에서 사용할 변수 (예: PORT, VERSION)
    compose_vars = config.get("compose_vars", {})
    if not isinstance(compose_vars, dict): compose_vars = {}

    # env_vars: 컨테이너 내부에 주입될 환경변수 (예: VAULT_ADDR)
    container_env = config.get("env_vars", {})
    if not isinstance(container_env, dict): container_env = {}

    # entry_vars: 스크립트(Entrypoint)에서 사용할 변수 (예: ORTHANC_ADMIN_PASSWORD)
    entry_vars = config.get("entry_vars", {})
    if not isinstance(entry_vars, dict): entry_vars = {}

    # 병합 (순서 중요: 뒤에 오는 것이 덮어씀)
    merged = {**base_env, **compose_vars, **container_env, **entry_vars}

    # 2) 필수 경로 변수 자동 주입 (System Standard)
    # YAML의 path 설정과 관계없이 표준 경로를 강제하여 복잡도 제거
    service_home = f"{BASE_DIR}/{service}"
    merged["DATA_DIR"] = f"{service_home}/data"
    merged["CONF_DIR"] = f"{service_home}/config"
    merged["CERTS_DIR"] = f"{service_home}/certs"

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
            ["mv", tmp_path, str(output_file)],
            check=True, capture_output=True, text=True
        )

        owner = os.getenv("USER", "unknown")
        # subprocess.run(["chown", root...]) -> Skip (User owned)
        
        subprocess.run(
            ["chmod", "600", str(output_file)],
            check=True, capture_output=True, text=True
        )

        log_info(f"[generate_env] {service.upper()} .env 생성 완료 → {output_file} (소유자: {owner})")

    except subprocess.CalledProcessError as e:
        log_error(f"[generate_env] 파일 이동/권한 설정 실패: {e.stderr}")
        if Path(tmp_path).exists():
            os.unlink(tmp_path)
        return ""

    return str(output_file)
