import pytest
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

GATEWAY_URL = "https://127.0.0.1" # Nginx maps 443 -> 443

def test_gateway_enforces_auth():
    """
    [SEC-02] Gateway Authentication Enforcement
    Verify that accessing the internal service via Gateway redirects to Keycloak.
    """
    try:
        # We need to treat 127.0.0.1 as ai4infra.internal for the Host header
        headers = {"Host": "ai4infra.internal"}
        
        # Don't follow redirects, we want to see the 302 Found
        resp = requests.get(GATEWAY_URL, headers=headers, verify=False, allow_redirects=False)
        
        assert resp.status_code == 302, "Gateway should redirect unauthenticated requests"
        location = resp.headers.get("Location", "")
        assert "auth.ai4infra.internal" in location or "localhost" in location, "Redirect should point to Keycloak"
        
    except requests.exceptions.ConnectionError:
        pytest.fail("Gateway (Nginx) is unreachable at https://127.0.0.1")

if __name__ == "__main__":
    test_gateway_enforces_auth()
    print("SEC-02 Gateway Verified [PASS]")
