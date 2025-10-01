"""
파일명: src/common/load_config.py
목적: deidentification.yml 설정 로드
기능: 
  - config/deidentification.yml 파일을 읽어와서 병리보고서 관련 설정을 반환
변경이력:
  - 2025-09-29: 최초 구현 (BenKorea)
"""

import yaml

from common.logger import log_debug


def load_config(yml_path="config/deidentification.yml", section="pathology_report"):
    try:
        with open(yml_path, encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)
        log_debug(f"[load_config] path = {yml_path}, section = {section}")
        return yaml_config.get(section, {})
    except Exception as e:
        log_debug(f"[ERROR] load_config: {e}")
        return {}