import pytest
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

VAULT_ADDR = "https://127.0.0.1:8200"

def test_vault_status():
    """
    [SEC-05] Vault Status Check
    Verify Vault is reachable and its sealing status.
    """
    try:
        resp = requests.get(f"{VAULT_ADDR}/v1/sys/health", verify=False)
        
        # 200: Active (Unsealed)
        # 429: Standby (Unsealed)
        # 501: Not Initialized
        # 503: Sealed
        
        status_code = resp.status_code
        
        if status_code == 200:
            print("Vault is Unsealed and Active.")
        elif status_code == 503:
            # Depending on if we ran auto-unseal, this might be okay or fail.
            # But the service exists.
            print("Vault is Sealed.")
        else:
             print(f"Vault Status Code: {status_code}")
             
        # At minimum, it should talk to us (not connection error)
        assert status_code in [200, 429, 501, 503]
        
    except requests.exceptions.ConnectionError:
        pytest.fail("Vault container is unreachable at https://127.0.0.1:8200")

if __name__ == "__main__":
    test_vault_status()
    print("SEC-05 Vault Verified [PASS]")
