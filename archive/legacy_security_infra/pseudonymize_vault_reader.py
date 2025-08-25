# src/security_infra/pseudonymize_vault_reader.py
"""
Vault Agent + AppRole 기반 가명화키(KEY, TWEAK) 안전 조회 예제
"""

import os
import requests

# 환경설정 (환경변수 또는 직접 경로 지정)
VAULT_ADDR = "https://127.0.0.1:8200"
VAULT_TOKEN_PATH = "/etc/vault-agent/vault-token"
VAULT_CACERT = "/etc/ssl/certs/vault.crt"     # Vault CA 인증서
SECRET_PATH = "pseudonymize/ff3"              # KV 엔진 경로 (예: kv-v2 엔진, pseudonymize/ff3)

# 1. Vault Agent가 발급한 임시 토큰 읽기
def get_vault_token(token_path=VAULT_TOKEN_PATH):
    with open(token_path, "r") as f:
        return f.read().strip()

# 2. Vault에서 가명화 키(예: KEY, TWEAK) 읽기
def read_pseudonymize_keys():
    token = get_vault_token()
    url = f"{VAULT_ADDR}/v1/{SECRET_PATH}"
    headers = {"X-Vault-Token": token}
    # KV v2라면 데이터는 .json()["data"]["data"]에 있음
    resp = requests.get(url, headers=headers, verify=VAULT_CACERT)
    resp.raise_for_status()
    vault_data = resp.json()
    # KV v2 엔진일 때는 data.data 구조임
    data = vault_data["data"]["data"]
    key = data.get("KEY")
    tweak = data.get("TWEAK")
    return key, tweak

if __name__ == "__main__":
    try:
        key, tweak = read_pseudonymize_keys()
        print(f"KEY: {key}")
        print(f"TWEAK: {tweak}")
    except Exception as e:
        print(f"[ERROR] Vault에서 가명화키를 읽어오는 데 실패했습니다: {e}")
