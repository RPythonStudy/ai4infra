import os
import shutil
import subprocess
import getpass
from pathlib import Path
from typing import Callable

def create_directories(
    base_dir: str = ".",
    force: bool = False,
    logger: Callable[[str], None] = print
) -> str:
    """
    필수 인프라 폴더/파일 생성.
    이미 있으면 스킵/삭제/재생성 처리.
    오류 및 sudo 권한 처리까지 포함.
    결과 summary string 반환.
    """
    # 실제 프로젝트 루트에서 실행한다는 전제
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    base = PROJECT_ROOT if base_dir == "." else Path(base_dir)
    base_dirs = [
        "docker/elk/esdata",
        "docker/elk/logstash/pipeline",
        "docker/keycloak/data",
        "docker/vault/config",
        "docker/vault/file",
        "docker/vault/certs",
        "docker/vault/logs",
        "docker/openldap/data",
        "docker/openldap/config",
        "docker/bitwarden/bw-data",   # Bitwarden 데이터 볼륨
        "docker/bitwarden/certs",    # Bitwarden 인증서 디렉토리
    ]
    created, skipped, errors, sudo_failed = [], [], [], []
    user = getpass.getuser()
    reinstall_count = 0

    for rel in base_dirs:
        d = base / rel
        try:
            if d.exists():
                if force:
                    try:
                        if d.is_dir():
                            shutil.rmtree(d)
                        else:
                            d.unlink()
                        logger(f"[삭제] {d}")
                    except PermissionError:
                        logger(f"[권한경고] {d} 삭제 권한 부족. sudo로 삭제 시도...")
                        cmd = ["sudo", "rm", "-rf", str(d)]
                        result = subprocess.run(cmd, capture_output=True)
                        if result.returncode != 0:
                            logger(f"[sudo 삭제 실패] {d} : {result.stderr.decode()}")
                            errors.append((str(d), f"sudo 삭제 실패: {result.stderr.decode()}"))
                            sudo_failed.append(str(d))
                            continue
                        logger(f"[sudo 삭제] {d}")
                    try:
                        d.mkdir(parents=True, exist_ok=True)
                        logger(f"[재생성] {d}")
                        created.append((str(d), "재생성"))
                    except PermissionError:
                        logger(f"[권한경고] {d} 재생성 권한 부족. 수동으로 폴더 생성 필요.")
                        errors.append((str(d), "폴더 재생성 권한 부족"))
                        sudo_failed.append(str(d))
                        continue
                    reinstall_count += 1
                else:
                    skipped.append(str(d))
                    logger(f"[스킵] {d} (이미 존재)")
                    continue
            else:
                try:
                    d.mkdir(parents=True, exist_ok=True)
                    logger(f"[생성] {d}")
                    created.append((str(d), "생성"))
                except PermissionError:
                    logger(f"[권한경고] {d} 생성 권한 부족. sudo로 생성 시도...")
                    cmd = ["sudo", "mkdir", "-p", str(d)]
                    result = subprocess.run(cmd, capture_output=True)
                    if result.returncode != 0:
                        logger(f"[sudo 생성 실패] {d}: {result.stderr.decode()}")
                        errors.append((str(d), f"sudo 생성 실패: {result.stderr.decode()}"))
                        sudo_failed.append(str(d))
                        continue
                    subprocess.run(["sudo", "chown", f"{user}:{user}", str(d)])
                    logger(f"[sudo 생성] {d}")
                    created.append((str(d), "생성"))
        except Exception as e:
            logger(f"[폴더 생성 실패] {d}: {e}")
            errors.append((str(d), str(e)))

    # summary 메시지 생성
    summary_lines = []
    summary_lines.append("폴더 생성 요약:")
    for d, typ in created:
        summary_lines.append(f"  [{typ}] {d}")
    for d in skipped:
        summary_lines.append(f"  [스킵] {d}")
    if errors:
        summary_lines.append("[경고] 일부 폴더 생성 실패!")
        for d, e in errors:
            summary_lines.append(f"  - {d}: {e}")
    if sudo_failed:
        summary_lines.append("\n[중요] 아래 폴더(들)는 sudo로도 삭제/생성이 안되었습니다!")
        for d in sudo_failed:
            summary_lines.append(f"  sudo rm -rf '{d}'")
        summary_lines.append("\n폴더 삭제/생성 후, 다시 재설치 명령을 실행하세요.")
    return "\n".join(summary_lines)
