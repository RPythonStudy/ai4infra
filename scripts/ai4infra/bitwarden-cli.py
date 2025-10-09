
import os
import subprocess
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

from common.logger import log_info, log_error, log_debug

from utils.container_manager import stop_container as stop_container_util, bitwarden_stop_function, backup_data

load_dotenv()
BASE_DIR = os.getenv('BASE_DIR')
PROJECT_ROOT = Path(os.getenv('PROJECT_ROOT', '.'))

app = typer.Typer(help="AI4INFRA Bitwarden 관리")

SERVICES = ['bitwarden']




def get_bitwarden_dir() -> str:
    """Bitwarden 설치 디렉토리"""
    return f"{BASE_DIR}/bitwarden"


@app.command()
def setup_user(
    password: str = typer.Option("bitwarden2024!", "--password", help="bitwarden 사용자 비밀번호")
):
    """사용자 및 디렉토리 생성 (자동화)"""
    log_info("[setup_user] 시작")

    bitwarden_dir = get_bitwarden_dir()
    log_debug(f"[setup_user] bitwarden_dir: {bitwarden_dir}")
    
    # 사용자 생성 (자동 비밀번호 설정)
    try:
        # 사용자가 이미 존재하는지 확인
        result = subprocess.run(['id', 'bitwarden'], capture_output=True, text=True)
        if result.returncode == 0:
            log_info("[setup_user] 사용자 'bitwarden'이 이미 존재합니다")
        else:
            # 사용자 생성 (비대화형)
            subprocess.run(['sudo', 'useradd', '-m', '-s', '/bin/bash', 'bitwarden'], check=True)
            # 비밀번호 설정
            process = subprocess.run(f'echo "bitwarden:{password}" | sudo chpasswd', 
                                   shell=True, check=True)
            log_info("[setup_user] 사용자 bitwarden 생성 및 비밀번호 설정 완료")
    except subprocess.CalledProcessError as e:
        log_error(f"[setup_user] 사용자 생성 실패: {e}")
        return

    result = subprocess.run(['sudo', 'id', 'bitwarden'], capture_output=True, text=True)
    log_debug(f"[setup-user] {result.stdout.strip()}")

    # 디렉토리 생성 및 권한 설정
    subprocess.run(['sudo', 'mkdir', '-p', bitwarden_dir])

    subprocess.run(['sudo', 'chmod', '700', bitwarden_dir])
    subprocess.run(['sudo', 'chown', '-R', 'bitwarden:bitwarden', bitwarden_dir])
    log_debug("[setup-user] 사용자 bitwarden 소유권 변경 완료")

    result = subprocess.run(['ls', '-ld', bitwarden_dir], capture_output=True, text=True)
    log_debug(f"[setup-user] {result.stdout.strip()}")
    log_info(f"[setup-user] 완료: {bitwarden_dir}")


@app.command()
def copy_template():
    """템플릿 파일들 복사"""
    log_info("[copy-template] 시작")

    bitwarden_dir = get_bitwarden_dir()
    template_dir = PROJECT_ROOT / "template/bitwarden"
    
    # bitwarden.sh 복사
    subprocess.run(['sudo', 'cp', str(template_dir / 'bitwarden.sh'), 
                   f'{bitwarden_dir}/bitwarden.sh'])
    subprocess.run(['sudo', 'chmod', '700', f'{bitwarden_dir}/bitwarden.sh'])
    
    # docker-compose.override.yml 복사 (bwdata/docker 디렉토리에)
    bwdata_dir = f"{bitwarden_dir}/bwdata/docker"
    subprocess.run(['sudo', 'mkdir', '-p', bwdata_dir])
    subprocess.run(['sudo', 'cp', str(template_dir / 'docker-compose.override.yml'), 
                   f'{bwdata_dir}/docker-compose.override.yml'])
    
    # 권한 설정
    subprocess.run(['sudo', 'chown', '-R', 'bitwarden:bitwarden', bitwarden_dir])
    
    # 복사된 파일 목록 확인
    copied_files = [
        f"{bitwarden_dir}/bitwarden.sh",
        f"{bitwarden_dir}/bwdata/docker/docker-compose.override.yml"
    ]
    
    log_info(f"[copy_template] 복사 완료:")
    for file_path in copied_files:
        # sudo를 사용해서 파일 존재 확인
        result = subprocess.run(['sudo', 'test', '-f', file_path], capture_output=True)
        if result.returncode == 0:
            log_info(f"  ✅ {file_path}")
        else:
            log_error(f"  ❌ {file_path} (복사 실패)")


@app.command()
def setup_sudoers():
    """Sudoers 설정 (멱등성 보장)"""
    log_info("[setup-sudoers] 시작")
    
    bitwarden_dir = get_bitwarden_dir()
    sudoers_file = "/etc/sudoers.d/bitwarden-docker"
    sudoers_line = f"bitwarden ALL=(ALL) NOPASSWD: /usr/bin/docker, {bitwarden_dir}/bitwarden.sh"
    
    # 파일 존재 및 내용 확인
    if Path(sudoers_file).exists():
        result = subprocess.run(['sudo', 'grep', '-F', sudoers_line, sudoers_file], 
                              capture_output=True)
        if result.returncode == 0:
            log_info("[setup-sudoers] 이미 설정되어 있음")
            result = subprocess.run(['sudo', '-u', 'bitwarden', 'sudo', '-l'], capture_output=True, text=True)
            log_info(f"[setup-sudoers] 완료 {result.stdout.strip()}")
            return
        else:
            log_info("[setup-sudoers] 기존 파일에 내용 추가")
            # 기존 파일에 추가
            subprocess.run(['sudo', 'bash', '-c', f'echo "{sudoers_line}" >> {sudoers_file}'])
    else:
        log_info("[setup-sudoers] 새 파일 생성")
        # 새 파일 생성
        with open('/tmp/bitwarden-docker', 'w') as f:
            f.write(f"{sudoers_line}\n")
        subprocess.run(['sudo', 'cp', '/tmp/bitwarden-docker', sudoers_file])
        subprocess.run(['rm', '/tmp/bitwarden-docker'])
    
    # 권한 설정 (항상 실행)
    subprocess.run(['sudo', 'chmod', '440', sudoers_file])
    result = subprocess.run(['sudo', '-u', 'bitwarden', 'sudo', '-l'], capture_output=True, text=True)
    log_info(f"[setup-sudoers] 완료 {result.stdout.strip()}")

@app.command()
def install(service: str = typer.Argument("all", help="설치할 서비스 이름 (또는 'all' 전체)")):
    services_to_install = SERVICES if service == "all" else [service]
    
    # 각 서비스별 처리
    for svc_name in services_to_install:
        print(f"####################################################################")
        log_info(f"[install] {svc_name} 설치 시작")
        
        # 1. 컨테이너 중지
        bitwarden_dir = get_bitwarden_dir()
        stop_container_util(
            service=svc_name,
            search_pattern='bitwarden_',
            stop_function=bitwarden_stop_function(bitwarden_dir)
        )
        
        # 2. 기존 데이터 백업
        backup_file = backup_data(svc_name)
        if backup_file:
            log_info(f"[install] {svc_name} 백업 완료: {backup_file}")


@app.command()
def start():
    """Bitwarden 시작"""
    log_info("[start] 시작")
    
    bitwarden_dir = get_bitwarden_dir()
    subprocess.run(['sudo', '-u', 'bitwarden', f'{bitwarden_dir}/bitwarden.sh', 'start'],
                  cwd=bitwarden_dir)
    
    log_info("[start] 완료")




@app.command()
def setup_all(
    password: str = typer.Option("bitwarden2024!", "--password", help="bitwarden 사용자 비밀번호"),
    force: bool = typer.Option(False, "--force", "-f", help="기존 설치 강제 삭제 후 재설치")
):
    """전체 설치 (완전 자동화)"""
    log_info("[setup_all] 전체 설치 시작 (자동화 모드)")
    
    # 1. 사용자 생성
    log_info("[setup_all] 1단계: bitwarden 사용자 생성")
    setup_user(password=password)
    
    # 2. 템플릿 복사
    log_info("[setup_all] 2단계: 템플릿 파일 복사") 
    copy_template()
    
    # 3. Sudoers 설정
    log_info("[setup_all] 3단계: sudoers 설정")
    setup_sudoers()
    
    # 4. Bitwarden 설치 (자동)
    log_info("[setup_all] 4단계: Bitwarden 설치")
    install(force=force)
    
    # 5. 서비스 시작
    log_info("[setup_all] 5단계: 서비스 시작")
    start()
    
    log_info("[setup_all] ✅ 전체 설치 완료!")
    domain = os.getenv('BW_DOMAIN', 'localhost')
    print("\n" + "="*60)
    print("🎉 Bitwarden 설치가 완료되었습니다!")
    print(f"🌐 접속 URL: https://{domain}")
    print("👤 관리자 계정을 생성하여 사용을 시작하세요")
    print("="*60)


if __name__ == "__main__":
    app()
