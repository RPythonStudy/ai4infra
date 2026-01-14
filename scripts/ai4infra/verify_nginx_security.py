#!/usr/bin/env python3
import subprocess
import sys
import requests
import time

def log_info(msg):
    print(f"[INFO] {msg}")

def log_error(msg):
    print(f"[ERROR] {msg}")

def log_success(msg):
    print(f"[PASS] {msg}")

def test_waf():
    log_info("Testing WAF functionality (XSS Block)...")
    url = "http://localhost:80/?param=<script>alert(1)</script>"
    try:
        response = requests.get(url)
        if response.status_code == 403:
            log_success("WAF blocked malicious request (403 Forbidden).")
            return True
        else:
            log_error(f"WAF failed to block request. Status Code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        log_error(f"Failed to connect to Nginx: {e}")
        return False

def test_immutable():
    log_info("Testing Immutable Infrastructure (Read-only Root FS)...")
    container_name = "ai4infra-nginx"
    command = ["sudo", "docker", "exec", container_name, "touch", "/root_test_file"]
    
    try:
        # We expect this command to FAIL with exit code non-zero
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0 and "Read-only file system" in result.stderr:
            log_success("Root filesystem is read-only.")
            return True
        elif result.returncode == 0:
            log_error("Root filesystem is WRITABLE! (Security Violation)")
            # Clean up if it succeeded
            subprocess.run(["sudo", "docker", "exec", container_name, "rm", "/root_test_file"])
            return False
        else:
            # Failed for some other reason, but likely still read-only or permission denied which is good
            if "Permission denied" in result.stderr or "Read-only" in result.stderr:
                 log_success(f"Write failed as expected: {result.stderr.strip()}")
                 return True
            
            log_error(f"Unexpected result: {result.stderr}")
            return False
            
    except Exception as e:
        log_error(f"Failed to execute docker command: {e}")
        return False

def main():
    log_info("Starting Nginx Security Verification...")
    
    waf_result = test_waf()
    immutable_result = test_immutable()
    
    if waf_result and immutable_result:
        log_success("All Nginx security tests passed!")
        sys.exit(0)
    else:
        log_error("Some security tests failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
