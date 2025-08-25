# src/security_infra/debug_vault_token.py
"""
Vault Agent가 발급한 토큰의 상태 및 정책을 직접 진단하는 디버그 스크립트
"""

import os
import requests
import subprocess

VAULT_ADDR = "https://127.0.0.1:8200"
VAULT_TOKEN_PATH = "/etc/vault-agent/vault-token"
VAULT_CACERT = "/etc/ssl/certs/vault.crt"

def get_vault_token(token_path=VAULT_TOKEN_PATH):
    with open(token_path, "r") as f:
        return f.read().strip()

def print_token_and_policy():
    token = get_vault_token()
    print(">> [DEBUG] 토큰 값 앞 20글자:", token[:20], "...")
    try:
        # vault CLI를 통해 정책/상태 조회
        result = subprocess.run(
            ["vault", "token", "lookup", token],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "VAULT_ADDR": VAULT_ADDR, "VAULT_CACERT": VAULT_CACERT},
            text=True,
        )
        print(">> [DEBUG] vault token lookup 결과:")
        print(result.stdout)
        if result.stderr:
            print(">> [DEBUG] stderr:", result.stderr)
    except Exception as e:
        print("[ERROR] vault token lookup 실행 중 에러:", e)

    # REST API로도 확인
    url = f"{VAULT_ADDR}/v1/auth/token/lookup"
    headers = {"X-Vault-Token": token}
    resp = requests.post(url, headers=headers, json={"token": token}, verify=VAULT_CACERT)
    print(">> [DEBUG] REST API token lookup 응답:", resp.status_code)
    try:
        print(resp.json())
    except Exception:
        print(resp.text)

if __name__ == "__main__":
    try:
        print_token_and_policy()
    except Exception as e:
        print(f"[ERROR] 토큰 디버깅 코드 실패: {e}")
