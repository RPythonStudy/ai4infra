"""
파일명: src/common/load_config.py
목적: YAML 설정 파일 로드 및 환경변수 치환
기능: 
  - YAML 설정 파일을 읽고 환경변수($VAR, ${VAR})를 실제 값으로 치환
  - 섹션 지정 시 해당 섹션만 반환, 미지정 시 전체 설정 반환
변경이력:
  - 2025-11-26: 업계 표준 패턴 적용 - 환경변수 치환 통합 (BenKorea)
  - 2025-11-25: substitute 함수를 호출하여 치환 작업 수행 (BenKorea)
  - 2025-09-29: 최초 구현 (BenKorea)
"""

import yaml

from common.logger import log_debug, log_error
from common.substitute import substitute_env


def load_config(yml_path="config/deidentification.yml", section=None):
    """
    YAML 설정 파일을 로드하고 환경변수를 치환하여 반환
    
    Args:
        yml_path (str): YAML 파일 경로 (기본값: config/deidentification.yml)
        section (str, optional): 특정 섹션만 추출. None이면 전체 반환
        
    Returns:
        dict: 환경변수가 치환된 설정 딕셔너리
        
    Raises:
        FileNotFoundError: 설정 파일이 존재하지 않을 때
        yaml.YAMLError: YAML 파싱 오류 발생 시
    """
    try:
        log_debug(f"[load_config] Loading config from: {yml_path}, section: {section}")
        
        # 1. 파일 열기 및 파싱
        with open(yml_path, encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)
        
        # 2. 환경변수 치환
        substituted_config = substitute_env(yaml_config)
        
        # 3. 섹션 추출 (지정된 경우)
        if section:
            result = substituted_config.get(section, {})
            log_debug(f"[load_config] Extracted section '{section}' with {len(result)} keys")
            return result
        
        # 4. 전체 반환
        log_debug(f"[load_config] Returning full config with {len(substituted_config)} top-level keys")
        return substituted_config
        
    except FileNotFoundError as e:
        log_error(f"[load_config] Config file not found: {yml_path}")
        raise
    except yaml.YAMLError as e:
        log_error(f"[load_config] YAML parsing error in {yml_path}: {e}")
        raise
    except Exception as e:
        log_error(f"[load_config] Unexpected error loading {yml_path}: {e}")
        raise