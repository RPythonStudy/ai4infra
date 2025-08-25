import os
import subprocess
from pathlib import Path
import yaml

def load_permission_config(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg

def set_permission_and_mode(target: Path, owner: str, mode: str, logger=print):
    try:
        subprocess.run(["sudo", "chown", owner, str(target)], check=True)
        logger(f"[OK] {target} → chown {owner}")
    except Exception as e:
        logger(f"[FAIL] {target} chown: {e}")
    try:
        subprocess.run(["sudo", "chmod", mode, str(target)], check=True)
        logger(f"[OK] {target} → chmod {mode}")
    except Exception as e:
        logger(f"[FAIL] {target} chmod: {e}")

def safe_exists(path):
    try:
        return path.exists()
    except PermissionError:
        # 권한 없으면 존재는 한다고 간주 (권한 관리 목적으로)
        return True

def set_permissions(
    project_root: Path = None,
    config_file: Path = None,
    logger=print
):
    """
    permissions.yml에 정의된 모든 폴더/파일/템플릿/인증서의 권한을 일괄 변경
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parents[2]
    if config_file is None:
        config_file = project_root / "config/permissions.yml"
    perm_cfg = load_permission_config(config_file)

    logger("===[권한 변경(chown & chmod) 시작]===")

    for key, item in perm_cfg.items():
        if isinstance(item, dict) and "path" in item:
            # 파일/템플릿/인증서 등 (경로 지정)
            target = project_root / item["path"]
            owner = item.get("owner", "1000:1000")
            mode = item.get("mode", "770")
            if not safe_exists(target):
                logger(f"[SKIP] {target} (존재하지 않음)")
                continue
            set_permission_and_mode(target, owner, mode, logger=logger)
        elif isinstance(item, dict) and "owner" in item and "mode" in item:
            # 디렉토리(폴더명은 서비스별 관례에 맞게 직접 경로로 입력)
            # 예: bitwarden-bw-data → docker/bitwarden/bw-data
            # 또는 elk → docker/elk 등 실제 경로로 config에 직접 명시 권장
            # 여기선 키가 상대경로(폴더)라고 가정
            target = project_root / "docker" / key.replace("-", "/")
            owner = item.get("owner", "1000:1000")
            mode = item.get("mode", "770")
            if not safe_exists(target):
                logger(f"[SKIP] {target} (존재하지 않음)")
                continue
            set_permission_and_mode(target, owner, mode, logger=logger)

    logger("[완료] 권한 변경 작업 종료.")
