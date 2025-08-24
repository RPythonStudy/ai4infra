## Python 환경 및 로그 자동화 Makefile

# 1. 가상환경 생성은 가장 먼저 분리
venv:
	python scripts/setup/setup_venv.py
	@echo "[INFO] Python virtual environment created."

# 개별 실행 가능한 타겟 분리
env:
	python scripts/setup/setup_env.py
	@echo "[INFO] .env file setup complete."

logs:
ifeq ($(OS),Windows_NT)
	python scripts/setup/create_logs.py
else
	sudo `which python` scripts/setup/create_logs.py
endif
	@echo "[INFO] Log path and file creation complete."

syspath:
	python scripts/setup/setup_syspath.py
	@echo "[INFO] Python syspath setup complete."

urls:
	python scripts/setup/setup_repository_urls.py
	@echo "[INFO] Repository and wiki submodule URLs updated."

# 나머지 자동화 setup
setup: env logs syspath urls
	@echo "[INFO] All setup tasks completed."

restore:
	python scripts/setup/restore_backup.py
	@echo "[INFO] Backup restored."

# rlib: src/rlib의 파일을 src/r로 복사
rlib:
	python scripts/setup/copy_Rlib.py
	@echo "[INFO] src/rlib files copied to src/r."

check:
	python scripts/setup/check_syspath.py
	@echo "[INFO] syspath check complete."

# backup: 현재 폴더를 backup/{폴더명}-backup으로 복사 (.venv, renv 제외)
backup:
	python scripts/setup/backup.py

include Makefile_project