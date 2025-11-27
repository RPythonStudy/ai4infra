#!/usr/bin/env python3

from pathlib import Path

import yaml

from common.logger import log_debug, log_error


def discover_services(config_dir="config") -> list:
    """
    config/*.yml 파일을 스캔하여 service.enable==true 인 서비스만 반환한다.
    SERVICES 하드코딩을 완전히 제거한다.
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
            log_debug(f"[discover_services] enable=true → {name}")
        else:
            log_debug(f"[discover_services] enable=false → {name}")

    return services
