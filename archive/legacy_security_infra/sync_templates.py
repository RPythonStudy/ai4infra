# src/security_infra/sync_templates.py

import shutil
from pathlib import Path
from typing import Callable

def sync_templates(
    project_root: Path = None,
    logger: Callable[[str], None] = print
) -> str:
    """
    templates/{elk,vault}/ 설정 파일을 프로젝트 루트 docker/ 경로로 복사.
    (권한/퍼미션은 건드리지 않음)
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parents[2]

    provision_list = [
        # (템플릿 원본, 복사 대상)
        (
            project_root / "templates/elk/logstash.conf",
            project_root / "docker/elk/logstash/pipeline/logstash.conf"
        ),
        (
            project_root / "templates/vault/vault.hcl",
            project_root / "docker/vault/config/vault.hcl"
        ),
    ]

    copied, errors = [], []

    for src, dst in provision_list:
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            logger(f"[OK] {src.relative_to(project_root)} → {dst.relative_to(project_root)}")
            copied.append(str(dst.relative_to(project_root)))
        except Exception as e:
            logger(f"[FAIL] {src} → {dst}: {e}")
            errors.append(f"{src} → {dst}: {e}")

    summary = []
    summary.append("템플릿 복사 요약:")
    for f in copied:
        summary.append(f"  [복사] {f}")
    if errors:
        summary.append("[경고] 복사 실패:")
        for err in errors:
            summary.append(f"  {err}")

    return "\n".join(summary)

if __name__ == "__main__":
    print(provision_templates())
