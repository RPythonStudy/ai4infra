#!/usr/bin/env python3
"""AI4INFRA CLI - 서비스 관리 도구"""

import os
import platform
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv

from common.logger import log_debug, log_error, log_info

# 환경변수 로드
load_dotenv()

app = typer.Typer(help="AI4INFRA 서비스 관리")

@app.command()
def info():
    """플랫폼 정보"""
    log_debug(f"OS: {platform.system()}")
    log_debug(f"SERVICE_PATH: {os.getenv('SERVICE_PATH', 'Not set')}")

@app.command()
def status(service: str = "all"):
    """서비스 상태"""
    log_info(f"Status: {service}")

@app.command()
def start(service: str):
    """서비스 시작"""
    log_info(f"Starting: {service}")

@app.command()
def stop(service: str):
    """서비스 중지"""
    log_info(f"Stopping: {service}")

@app.command()
def ls():
    """서비스 목록"""
    services = ["postgres", "vault", "elk", "bitwarden", "ldap"]
    for s in services:
        print(f"- {s}")

if __name__ == "__main__":
    try:
        app()
    except Exception as e:
        log_error(str(e))
        sys.exit(1)
