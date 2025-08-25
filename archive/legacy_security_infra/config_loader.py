# src/security_infra/config_loader.py

import logging
from pathlib import Path
import yaml

# projects/config/config.yml 기준
ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config/config.yml"

def load_config():
    """config/config.yml을 읽어 dict로 반환. 없으면 기본값 반환."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f)
    return {
        "mode": "dev",
        "logging": {"level": "DEBUG"}
    }

def get_mode(config=None):
    """mode 값 반환 (없으면 'dev')"""
    if config is None:
        config = load_config()
    return str(config.get("mode", "dev")).lower()

def get_log_level(config=None):
    """logging.level 값 반환 (없으면 'DEBUG')"""
    if config is None:
        config = load_config()
    level = config.get("logging", {}).get("level", "DEBUG")
    return str(level).upper()

def setup_logger(name="infra", log_level=None):
    """
    logger 생성 및 레벨 적용.
    log_level이 명시되면 config보다 우선 적용.
    """
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        if log_level is None:
            log_level = get_log_level()
        logger.setLevel(getattr(logging, log_level, logging.DEBUG))
        handler = logging.StreamHandler()
        fmt = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    return logger
