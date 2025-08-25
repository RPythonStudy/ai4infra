# security-infra-cli.py

import typer
from pathlib import Path
import logging
import logging.handlers
import os
import socket
from datetime import datetime
import uuid
import json
from typing import List


# config_loader는 기존과 동일하게 유지
from security_infra.config_loader import load_config, get_mode, get_log_level
from security_infra.create_directories import create_directories
from security_infra.generate_certificates import generate_certificates
from security_infra.sync_templates import sync_templates
from security_infra.set_permissions import set_permissions
from security_infra.compose_manager import compose_command
from security_infra.auto_unseal import auto_unseal


app = typer.Typer()

# [1] 항상 프로젝트 root 기준
PROJECT_ROOT = Path(__file__).resolve().parent

# 감사/보안 로그 포맷 (구조화, 사용자/호스트/PID 등 포함)
def make_audit_log(event, **fields):
    base = {
        "event": event,
        "timestamp": datetime.now().isoformat(),
        "user": os.getenv("USER", "unknown"),
        "hostname": socket.gethostname(),
        "cwd": os.getcwd(),
        "pid": os.getpid(),
        "exec_id": os.environ.get("PS_EXEC_UUID", str(uuid.uuid4())),
    }
    base.update(fields)
    return "[AUDIT] " + json.dumps(base, ensure_ascii=False)

def get_dual_logger(
    project_logfile=PROJECT_ROOT / "logs/install.log",
    syslog_address="/dev/log",
    logger_name="infra_install"
):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    # 프로젝트 로그 (FileHandler)
    if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        Path(project_logfile).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(project_logfile)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    # 시스템 로그 (SysLogHandler, UNIX 계열)
    if os.path.exists(syslog_address) and not any(isinstance(h, logging.handlers.SysLogHandler) for h in logger.handlers):
        try:
            sh = logging.handlers.SysLogHandler(address=syslog_address)
            sh.setFormatter(logging.Formatter('infra_install: %(message)s'))
            logger.addHandler(sh)
        except Exception as e:
            logger.error(f"SysLogHandler 등록 실패: {e}")
    return logger

@app.callback()
def main(
    mode: str = typer.Option(None, "--mode", "-m", help="실행 모드"),
    log_level: str = typer.Option(None, "--log-level", "-l", help="로그레벨"),
    project_logfile: str = typer.Option(None, help="프로젝트 감사 로그 파일 경로(기본값: logs/install.log)"),
    syslog: str = typer.Option("/dev/log", help="시스템 로그 소켓(Unix 계열, 예: /dev/log)"),
):
    """
    모든 명령에서 공통 옵션: 모드/로그레벨/로그파일(이중로깅)/시스템로그
    """
    # 매 실행마다 실행UUID 설정
    exec_id = str(uuid.uuid4())
    os.environ["PS_EXEC_UUID"] = exec_id
    cfg = load_config()
    effective_mode = mode if mode else get_mode(cfg)
    effective_log_level = log_level if log_level else get_log_level(cfg)
    # 경로 처리 (옵션이 없으면 프로젝트 내 logs/install.log)
    log_path = Path(project_logfile) if project_logfile else (PROJECT_ROOT / "logs/install.log")
    global logger
    logger = get_dual_logger(log_path, syslog)
    logger.setLevel(getattr(logging, effective_log_level, logging.INFO))
    logger.info(make_audit_log(
        "프로그램 시작",
        mode=effective_mode,
        log_level=effective_log_level,
        user=os.getenv("USER"),
        exec_id=exec_id
    ))
    typer.echo(f"[INFO] 모드={effective_mode}, 로그레벨={effective_log_level}, 실행ID={exec_id}")

@app.command("create-directories")
def create_directories_cmd(
    base_dir: str = typer.Option(".", help="디렉터리 생성 기준 경로"),
    force: bool = typer.Option(False, help="강제 삭제 후 재생성"),
):
    """필수 인프라 디렉터리 생성"""
    summary = create_directories(base_dir=base_dir, force=force, logger=logger.info)
    typer.echo(summary)
    

@app.command("generate-certificates")
def generate_certificates_cmd(
    services: List[str] = typer.Option(
        ["vault", "elk", "keycloak"],
        help="인증서 생성할 서비스(여러 개 선택 가능, 기본: 전체)"
    ),
    days: int = typer.Option(730, help="유효기간(일수)"),
    overwrite: bool = typer.Option(False, "--overwrite", help="기존 인증서 강제 덮어쓰기"),
    extra_san: List[str] = typer.Option(None, help="추가 SAN(DNS:xxx, IP:yyy 형식, 여러개 입력 가능)")
):
    summary = generate_certificates(services, days, overwrite, extra_san, logger=logger.info)
    typer.echo(summary)
    

@app.command("sync-templates")
def sync_templates_cmd():
    """템플릿(config) 복사만 수행 (권한/퍼미션은 별도 명령)"""
    summary = sync_templates(logger=logger.info)
    typer.echo(summary)
    
@app.command("set-permissions")
def set_permissions_cmd(
    services: List[str] = typer.Option(
        None,
        "--services",
        "-s",
        help="권한을 변경할 서비스명(예: vault, elk, keycloak, bitwarden, openldap), 여러 개 반복 지정 가능",
        show_default=False,
    )
):
    """
    서비스별 볼륨/인증서 디렉토리 권한을 일괄 변경
    (ELK, Vault, Bitwarden 등, 필요시 --services로 개별 선택)
    """
    summary = set_permissions(services, logger=print)
    typer.echo(summary) 

@app.command("compose")
def compose_cmd(
    action: str = typer.Argument(..., help="up|down|restart|logs|ps"),
    service: str = typer.Option("all", help="all|vault|elk|keycloak|openldap")
):
    compose_file = PROJECT_ROOT / "docker-compose.yml"
    try:
        result = compose_command(
            action, service, compose_file,
            logger=logger, make_audit_log=make_audit_log
        )
        typer.echo(result)
    except Exception as e:
        typer.echo(str(e))
        raise typer.Exit(1)

    

@app.command("auto-unseal")
def auto_unseal_cmd(
    bw_item: str = typer.Option("vault unseal key - desktop", help="Bitwarden 항목명"),
    vault_addr: str = typer.Option("https://127.0.0.1:8200", help="Vault API 주소")
):
    """
    Bitwarden에서 Unseal Key를 자동으로 추출해 Vault 언실 처리
    """
    auto_unseal(bw_item=bw_item, vault_addr=vault_addr, logger=print)

if __name__ == "__main__":
    app()
