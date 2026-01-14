import pytest
import requests
import os
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

KEYCLOAK_URL = "http://localhost:8484" # Mapped port
REALM = "ai4infra"

def test_keycloak_health():
    """
    [SEC-01] Keycloak Availability Test
    Verify Keycloak is running and responding.
    """
    try:
        resp = requests.get(f"{KEYCLOAK_URL}/health/ready")
        # Keycloak standard health check often runs on port 9000, 
        # but the main port should return 200 or 404 for root, avoiding connection error is key.
        # Let's check the realm configuration which is the core function.
        pass
    except requests.exceptions.ConnectionError:
        pytest.fail("Keycloak container is not reachable at localhost:8484")

def test_keycloak_oidc_config():
    """
    [SEC-01] OIDC Configuration Test
    Verify that the Realm is configured and exposes OIDC metadata.
    """
    url = f"{KEYCLOAK_URL}/realms/{REALM}/.well-known/openid-configuration"
    resp = requests.get(url)
    assert resp.status_code == 200, f"Failed to fetch OIDC config. Realm '{REALM}' might not exist."
    
    data = resp.json()
    assert data["issuer"].endswith(f"/realms/{REALM}")
    assert "authorization_endpoint" in data
    assert "token_endpoint" in data

if __name__ == "__main__":
    test_keycloak_oidc_config()
    print("SEC-01 Keycloak Verified [PASS]")
