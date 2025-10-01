"""
파일명: src/common/logger.py
목적: 로깅 프레임워크 제공
설명:
  - .env + logging.yml 기반 동적 설정
  - YAML 전역(키/값) 환경변수 치환: ${PROJECT_NAME}, ${LOG_PATH}...
  - 파일 핸들러의 경로/권한 검증(자동 생성 금지)
  - LOG_LEVEL로 root/서브 로거 레벨 일괄 오버라이드
  - 프로젝트 로거 자동 보장(없으면 생성)
  - audit 로거의 stdout 출력 금지 보장(정책 위반 시 예외)
  - get_logger, log_info 등 래퍼 제공
변경이력:
  - 2025-08-12: 새로 생성 (BenKorea)
"""

import os
import re
import socket
import logging
import logging.config
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv

load_dotenv(override=True)

PROJECT_NAME = os.getenv("PROJECT_NAME", "default")
VALID_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


def _get_log_level() -> str:
    """ENV LOG_LEVEL을 대문자로 읽어 유효성 검사 후 반환."""
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    return level if level in VALID_LEVELS else "INFO"


def _expand_env_placeholders(value: str) -> str:
    """문자열 내 ${VAR}/$VAR 환경변수 치환 (PROJECT_NAME, LOG_PATH 우선)."""
    if not isinstance(value, str):
        return value
    value = value.replace("${PROJECT_NAME}", PROJECT_NAME).replace("$PROJECT_NAME", PROJECT_NAME)
    value = value.replace("{PROJECT_NAME}", PROJECT_NAME)
    log_path = os.getenv("LOG_PATH", "")
    value = value.replace("${LOG_PATH}", log_path).replace("$LOG_PATH", log_path)
    return os.path.expandvars(value)


def _expand_env_any(obj: Any) -> Any:
    """
    YAML 전체(딕셔너리 키/값, 리스트 요소, 문자열)에 대해
    환경변수 치환을 재귀적으로 수행.
    """
    if isinstance(obj, dict):
        return {_expand_env_any(k): _expand_env_any(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env_any(x) for x in obj]
    if isinstance(obj, str):
        return _expand_env_placeholders(obj)
    return obj


def _require_parent_exists_and_writable(path: Path, handler_name: str) -> None:
    """
    컴플라이언스: 디렉토리 자동 생성 금지.
    존재/쓰기권한이 없으면 명확한 예외를 발생시킨다.
    """
    parent = path.parent
    if not parent.exists():
        raise FileNotFoundError(
            f"[{handler_name}] 로그 디렉토리가 존재하지 않습니다: {parent}\n"
            "- Linux 예: /var/log/<project>, ~/logs\n"
            "- Windows 예: C:\\logs, %USERPROFILE%\\logs\n"
            "- .env의 LOG_PATH 설정을 확인하세요."
        )
    if not os.access(parent, os.W_OK):
        raise PermissionError(
            f"[{handler_name}] 로그 디렉토리에 쓰기 권한이 없습니다: {parent}\n"
            "- Unix: chmod/chown 검토, Windows: 보안 탭 권한 부여 필요\n"
            "- CI 환경이라면 실행 사용자(예: 서비스 계정) 권한을 확인하세요."
        )


def _ensure_project_logger(config: dict, level: str) -> None:
    """
    ${PROJECT_NAME} 로거가 YAML에 없더라도 안전하게 동작하도록 보장.
    - handlers는 비워 두고 propagate만 True로 둬 루트로 전달되게 함.
    """
    loggers = config.setdefault("loggers", {})
    if PROJECT_NAME not in loggers:
        loggers[PROJECT_NAME] = {"level": level, "propagate": True}


def _assert_audit_is_file_only(config: dict) -> None:
    """
    개인정보보호정책: audit 로거는 전용 파일에만 기록되어야 하며 stdout(console) 금지.
    정책 위반 구성 발견 시 예외를 발생시킨다.
    """
    audit = config.get("loggers", {}).get("audit")
    if not audit:
        return
    handlers = set(audit.get("handlers", []))
    if "console" in handlers:
        raise RuntimeError("개인정보보호정책 위반: 'audit' 로거에 console 핸들러를 사용할 수 없습니다.")
    # propagate가 True이면 루트 console로 전파될 수 있으므로 금지
    if audit.get("propagate", False):
        raise RuntimeError("개인정보보호정책 위반: 'audit' 로거는 propagate: false 여야 합니다.")


def _load_logging_config() -> dict:
    """
    config/logging.yml을 로드하여:
      - YAML 전역 ENV 치환(키/값)
      - LOG_LEVEL로 레벨 일괄 오버라이드
      - 파일 핸들러 filename 치환 및 경로/권한 검증
      - 프로젝트 로거 보장
      - audit stdout 금지 검증
    을 수행한 dictConfig용 딕셔너리를 반환.
    """
    yaml_path = Path(__file__).parent.parent.parent / "config" / "logging.yml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"logging.yml 파일이 필요합니다: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 0) YAML 전역(키/값) ENV 치환
    config = _expand_env_any(config)

    # 1) LOG_LEVEL 일괄 오버라이드
    level = _get_log_level()
    config.setdefault("root", {})["level"] = level
    for _, logger_cfg in config.get("loggers", {}).items():
        logger_cfg["level"] = level

    # 2) 프로젝트 로거 보장
    _ensure_project_logger(config, level)

    # 3) 파일 핸들러의 filename 처리(치환 후 경로/권한 검증)
    for handler_name, handler_cfg in config.get("handlers", {}).items():
        handler_class = handler_cfg.get("class", "")
        # FileHandler, RotatingFileHandler 등 파일 기반 핸들러 탐지
        if re.search(r"FileHandler$", handler_class):
            raw_filename = handler_cfg.get("filename", "")
            if not raw_filename:
                raise ValueError(f"[{handler_name}] filename이 지정되어 있지 않습니다.")
            expanded = _expand_env_placeholders(raw_filename)
            if expanded == raw_filename and ("${" in raw_filename or "$" in raw_filename):
                raise ValueError(
                    f"[{handler_name}] 환경변수 치환 실패: {raw_filename}\n"
                    "- .env의 관련 변수를 확인하세요."
                )
            file_path = Path(expanded)
            _require_parent_exists_and_writable(file_path, handler_name)
            handler_cfg["filename"] = str(file_path)

    # 4) audit stdout 금지(정책 점검)
    _assert_audit_is_file_only(config)

    return config


def setup_logging() -> None:
    """dictConfig로 로깅을 초기화."""
    cfg = _load_logging_config()
    logging.config.dictConfig(cfg)


def get_logger(name: Optional[str] = PROJECT_NAME) -> logging.Logger:
    """
    지정된 이름의 로거 반환. 최초 호출 시 자동으로 setup_logging() 수행.
    기본값은 .env의 PROJECT_NAME.
    """
    root_logger = logging.getLogger()
    if not root_logger.hasHandlers():
        setup_logging()
    return logging.getLogger(name or None)


def audit_log(action: str, detail: Optional[Dict[str, Any]] = None,
              compliance: str = "개인정보보호법 제28조") -> None:
    """
    감사 로그(JSON). 'audit' 로거는 전용 파일에만 기록되어야 함(stdout 금지).
    """
    audit_logger = get_logger("audit")
    user = os.getenv("USER") or os.getenv("USERNAME") or "unknown"
    log = {
        "action": action,
        "user": user,
        "process_id": os.getpid(),
        "server_id": socket.gethostname(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "compliance_check": compliance,
    }
    if detail:
        log.update(detail)
    audit_logger.info(log)


# 편의 래퍼(일관 API)
def log_debug(msg: str) -> None:
    get_logger().debug(msg)

def log_info(msg: str) -> None:
    get_logger().info(msg)

def log_warn(msg: str) -> None:
    get_logger().warning(msg)

def log_error(msg: str) -> None:
    get_logger().error(msg)

def log_critical(msg: str) -> None:
    get_logger().critical(msg)
