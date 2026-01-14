#!/usr/bin/env python3
import os
import sys
import time
import requests
from glob import glob

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Configuration ---
VAULT_ADDR = os.getenv("VAULT_ADDR", "https://127.0.0.1:8200") # Default to HTTPS
USB_MOUNT_PATH = os.getenv("USB_MOUNT_PATH", "/mnt/usb")
MAX_RETRIES = 5
RETRY_DELAY = 2

def log(msg):
    print(f"[Auto-Unseal] {msg}")

def check_vault_status():
    """Vault 상태 확인 (Sealed 여부)"""
    try:
        resp = requests.get(f"{VAULT_ADDR}/v1/sys/health", verify=False)
        # 200: Active, 429: Standby, 501: Not Init, 503: Sealed
        code = resp.status_code
        if code == 200:
            return "ACTIVE"
        elif code == 503:
            return "SEALED"
        elif code == 501:
            return "NOT_INIT"
        else:
            return f"UNKNOWN ({code})"
    except requests.exceptions.ConnectionError:
        return "DOWN"
    except Exception as e:
        log(f"Connection Error: {e}")
        return "DOWN"

def find_key_files():
    """USB 경로에서 키 파일 검색 (*.key, *.enc)"""
    if not os.path.exists(USB_MOUNT_PATH):
        log(f"USB Mount path not found: {USB_MOUNT_PATH}")
        return []
    
    # 단순화를 위해 .key 파일을 평문 Unseal Key로 가정 (실전에서는 GPG Decrypt 필요)
    keys = glob(f"{USB_MOUNT_PATH}/*.key")
    return keys

def unseal_vault(keys):
    """키를 사용하여 Unseal 시도"""
    for key_file in keys:
        try:
            with open(key_file, "r") as f:
                key = f.read().strip()
            
            payload = {"key": key}
            resp = requests.post(f"{VAULT_ADDR}/v1/sys/unseal", json=payload, verify=False)
            
            if resp.status_code == 200:
                data = resp.json()
                if not data.get("sealed"):
                    log("Vault Unsealed Successfully!")
                    return True
                else:
                    progress = data.get("progress", 0)
                    threshold = data.get("t", 0)
                    log(f"Unseal Key Accepted. Progress: {progress}/{threshold}")
            else:
                log(f"Failed to submit key: {resp.text}")
        except Exception as e:
            log(f"Error reading key file {key_file}: {e}")
    
    return False

def main():
    log("Starting Auto-Unseal Process...")
    
    # 1. Connection Check
    for i in range(MAX_RETRIES):
        status = check_vault_status()
        if status != "DOWN":
            break
        log(f"Vault is down. Retrying ({i+1}/{MAX_RETRIES})...")
        time.sleep(RETRY_DELAY)
    
    if status == "DOWN":
        log("Error: Vault is unreachable.")
        sys.exit(1)
    
    if status == "ACTIVE":
        log("Vault is already ACTIVE (Unsealed).")
        sys.exit(0)
        
    if status == "NOT_INIT":
        log("Vault is NOT INITIALIZED. Please run 'vault operator init' manually.")
        sys.exit(1)
        
    # 2. Key Discovery
    log(f"Scanning for keys in {USB_MOUNT_PATH}...")
    keys = find_key_files()
    if not keys:
        log("No key files found in USB path. Skipping Auto-Unseal.")
        sys.exit(0) # Not an error, just skip
        
    # 3. Unseal Execution
    if unseal_vault(keys):
        log("Operation Completed: Vault is now Active.")
    else:
        log("Operation Finished: Vault remains Sealed (Insufficient keys).")

if __name__ == "__main__":
    main()
