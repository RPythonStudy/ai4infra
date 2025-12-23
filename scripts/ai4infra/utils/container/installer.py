#!/usr/bin/env python3

from pathlib import Path

import yaml

from common.logger import log_debug, log_error


def discover_services(config_dir="config") -> list:
    """
    config/*.yml 파일을 스캔하여 service.enable==true 인 서비스만 반환한다.
    """
    services = []
    config_path = Path(config_dir)

    for yml_file in config_path.glob("*.yml"):
        name = yml_file.stem  # ex: postgres.yml → postgres

        try:
            cfg = yaml.safe_load(yml_file.read_text(encoding="utf-8")) or {}
        except Exception as e:
            log_error(f"[discover_services] YAML 파싱 실패: {yml_file} ({e})")
            continue

        service_cfg = cfg.get("service", {})
        enabled = service_cfg.get("enable", False)

        if enabled:
            services.append(name)
            log_debug(f"[discover_services] enable=false → {name}")

    return services


def is_hot_backup_service(service: str) -> bool:
    """config/{service}.yml에서 backup.mode가 hot인지 확인"""
    # PROJECT_ROOT나 helper는 여기서 import가 어려울 수 있으니 yaml 직접 로드
    # 하지만 load_config가 common에 있으므로 사용 가능하면 좋음
    # 여기선 installer.py가 common 의존성이 적으므로 직접 yaml 로드 구현 권장?
    # 아니면 load_config 사용. installer.py는 이미 yaml을 쓰고 있음.
    
    # 여기서 config/ 경로를 찾기 위해 프로젝트 루트 추정 필요
    # discover_services가 'config' 디렉토리를 인자로 받으므로, 그걸 활용하거나
    # 단순히 상대경로 ./config/{service}.yml 사용 (cli 실행 위치 기준)
    
    import os
    from common.load_config import load_config
    
    project_root = os.getenv("PROJECT_ROOT", os.getcwd())
    cfg_path = f"{project_root}/config/{service}.yml"
    
    try:
        cfg = load_config(cfg_path) or {}
        backup_cfg = cfg.get("backup", {})
        mode = backup_cfg.get("mode", "cold") # default: cold
        return mode.lower() == "hot"
    except Exception:
        return False
