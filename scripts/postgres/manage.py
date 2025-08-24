from dotenv import load_dotenv
import os
import yaml
import typer
from dotenv import load_dotenv
from common.logger import log_info

app = typer.Typer()

@app.command("load-config")
def load_config():
    load_dotenv(override=True)
    POSTGRES_USER = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_DB = os.getenv("POSTGRES_DB")  


@app.command("install")
def install():
    from common.logger import log_info, log_error
    with open("config/postgres.yml") as f:
        postgres_cfg = yaml.safe_load(f).get("postgres", {})
        install_dir = postgres_cfg.get("PG_INSTALL_DIR")
        data_dir = postgres_cfg.get("PG_DATA_DIR")
        backup_dir = postgres_cfg.get("PG_BACKUP_DIR")
        port = postgres_cfg.get("PG_PORT")
    log_info(f"install_dir: {install_dir}")

    import shutil
    import subprocess
    from common.logger import log_info, log_error
    template_dir = "templates/postgres"
    # 0. 기존 data 폴더 백업 및 복원
    if data_dir and os.path.exists(data_dir):
        log_info(f"Data directory exists: {data_dir}. Running backup and restore...")
        # 백업
        import subprocess
        import sys
        subprocess.run([
            sys.executable, os.path.abspath(__file__), "backup"
        ], check=True)
    # 1. 디렉터리 생성
    for d in [install_dir, data_dir, backup_dir]:
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
            log_info(f"Created directory: {d}")

    # 2. 템플릿 파일 복사
    for fname in os.listdir(template_dir):
        src = os.path.join(template_dir, fname)
        dst = os.path.join(install_dir, fname)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
            log_info(f"Copied {src} to {dst}")

    # 3. 프로젝트 루트의 .env를 install_dir로 복사
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_file = os.path.join(project_root, ".env")
    env_dst = os.path.join(install_dir, ".env")
    if os.path.isfile(env_file):
        shutil.copy2(env_file, env_dst)
        log_info(f"Copied {env_file} to {env_dst}")

    # 4. 소유권 1000:1000으로 변경
    for d in [install_dir, data_dir, backup_dir]:
        if d:
            subprocess.run(["chown", "-R", "1000:1000", d], check=True)
            log_info(f"Changed ownership for {d} to 1000:1000")
    if os.path.isfile(env_dst):
        subprocess.run(["chown", "1000:1000", env_dst], check=True)
        log_info(f"Changed ownership for {env_dst} to 1000:1000")

    # 5. 기존 컨테이너 중단/삭제 후 새로운 컨테이너 실행
    container_name = postgres_cfg.get("container_name", "postgres")
    try:
        subprocess.run(["sudo", "docker", "stop", container_name], check=False)
        log_info(f"Stopped container: {container_name}")
    except Exception as e:
        log_info(f"No running container to stop: {e}")
    try:
        subprocess.run(["sudo", "docker", "rm", container_name], check=False)
        log_info(f"Removed container: {container_name}")
    except Exception as e:
        log_info(f"No container to remove: {e}")

    # 도커컴포즈 파일 경로로 이동 후 컨테이너 실행
    compose_dir = install_dir
    try:
        env = os.environ.copy()
        env["PG_DATA_DIR"] = data_dir
        env["PG_PORT"] = str(port)
        subprocess.run([
            "docker", "compose",
            "-f", os.path.join(compose_dir, "docker-compose.yml"),
            "up", "-d"
        ], check=True, env=env)
        log_info(f"Started new container from {os.path.join(compose_dir, 'docker-compose.yml')} with PG_DATA_DIR={data_dir}, PG_PORT={port}")
    except Exception as e:
        log_error(f"Failed to start new container: {e}")

    # 설치 후 restore 실행
    if data_dir and os.path.exists(data_dir):
        log_info(f"Running restore for {data_dir}...")
        import sys
        subprocess.run([
            sys.executable, os.path.abspath(__file__), "restore"
        ], check=True)

@app.command("backup")
def backup():
    import os
    import shutil
    import datetime
    import yaml
    from common.logger import log_info, log_error

    # config에서 경로 로딩
    with open("config/postgres.yml") as f:
        postgres_cfg = yaml.safe_load(f).get("postgres", {})
        data_dir = postgres_cfg.get("PG_DATA_DIR")
        backup_dir = postgres_cfg.get("PG_BACKUP_DIR")
        container_name = postgres_cfg.get("container_name", "postgres")

    # 1. 컨테이너 중지
    import subprocess
    try:
        subprocess.run(["sudo", "docker", "stop", container_name], check=True)
        log_info(f"Stopped container: {container_name}")
    except Exception as e:
        log_error(f"Failed to stop container {container_name}: {e}")
        return

    # 2. 데이터 디렉터리 백업
    if not os.path.exists(data_dir):
        log_error(f"Data directory not found: {data_dir}")
        return
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_target = os.path.join(backup_dir, f"backup_{timestamp}")
    try:
        shutil.copytree(data_dir, backup_target)
        log_info(f"Backup completed: {backup_target}")
    except Exception as e:
        log_error(f"Backup failed: {e}")

    # 3. 컨테이너 재가동
    try:
        subprocess.run(["sudo", "docker", "start", container_name], check=True)
        log_info(f"Started container: {container_name}")
    except Exception as e:
        log_error(f"Failed to start container {container_name}: {e}")


@app.command("restore")
def restore():
    import os
    import shutil
    import yaml
    import subprocess
    from common.logger import log_info, log_error

    # config에서 경로 로딩
    with open("config/postgres.yml") as f:
        postgres_cfg = yaml.safe_load(f).get("postgres", {})
        data_dir = postgres_cfg.get("PG_DATA_DIR")
        backup_dir = postgres_cfg.get("PG_BACKUP_DIR")
        container_name = postgres_cfg.get("container_name", "postgres")

    # 1. 컨테이너 중지
    try:
        subprocess.run(["sudo", "docker", "stop", container_name], check=True)
        log_info(f"Stopped container: {container_name}")
    except Exception as e:
        log_error(f"Failed to stop container {container_name}: {e}")
        return

    # 2. 최신 백업 찾기
    if not os.path.exists(backup_dir):
        log_error(f"Backup directory not found: {backup_dir}")
        return
    backups = [d for d in os.listdir(backup_dir) if d.startswith("backup_")]
    if not backups:
        log_error("No backup found.")
        return
    latest_backup = sorted(backups)[-1]
    backup_source = os.path.join(backup_dir, latest_backup)

    # 3. 기존 데이터 삭제 및 복원
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir)
        log_info(f"Removed old data_dir: {data_dir}")

    shutil.copytree(backup_source, data_dir)
    log_info(f"Restored backup from {backup_source} to {data_dir}")

    # 3-1. 복원 후 권한 변경
    try:
        subprocess.run(["chown", "-R", "1000:1000", data_dir], check=True)
        log_info(f"Changed ownership for {data_dir} to 1000:1000")
    except Exception as e:
        log_error(f"Failed to change ownership for {data_dir}: {e}")

    # 4. 컨테이너 재가동
    try:
        subprocess.run(["sudo", "docker", "start", container_name], check=True)
        log_info(f"Started container: {container_name}")
    except Exception as e:
        log_error(f"Failed to start container {container_name}: {e}")

if __name__ == "__main__":
    app()