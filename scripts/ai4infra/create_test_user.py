#!/usr/bin/env python3
import os
import sys
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
PROJECT_ROOT = os.getenv("PROJECT_ROOT")
KEYCLOAK_PORT = os.getenv("KEYCLOAK_PORT", "8484")
KEYCLOAK_URL = f"http://localhost:{KEYCLOAK_PORT}"
ADMIN_USER = os.getenv("KEYCLOAK_ADMIN", "admin")
ADMIN_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")
REALM_NAME = "ai4infra"

def get_admin_token():
    url = f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token"
    payload = {
        "client_id": "admin-cli",
        "username": ADMIN_USER,
        "password": ADMIN_PASSWORD,
        "grant_type": "password"
    }
    try:
        resp = requests.post(url, data=payload)
        resp.raise_for_status()
        return resp.json()["access_token"]
    except Exception as e:
        print(f"Failed to get admin token: {e}")
        sys.exit(1)

def create_local_user(token, username, password):
    url = f"{KEYCLOAK_URL}/admin/realms/{REALM_NAME}/users"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # payload
    payload = {
        "username": username,
        "enabled": True,
        "email": f"{username}@test.local",
        "firstName": "Test",
        "lastName": "User",
        "credentials": [{
            "type": "password",
            "value": password,
            "temporary": False
        }]
    }
    
    resp = requests.post(url, json=payload, headers=headers)
    if resp.status_code == 201:
        print(f"User '{username}' created successfully.")
    elif resp.status_code == 409:
        print(f"User '{username}' already exists.")
        # If exists, reset password
        # Get User ID
        users = requests.get(url, headers=headers, params={"username": username}).json()
        user_id = users[0]["id"]
        pwd_url = f"{KEYCLOAK_URL}/admin/realms/{REALM_NAME}/users/{user_id}/reset-password"
        requests.put(pwd_url, headers=headers, json={"type": "password", "value": password, "temporary": False})
        print(f"Password reset for '{username}'.")
    else:
        print(f"Failed to create user: {resp.text}")

if __name__ == "__main__":
    token = get_admin_token()
    create_local_user(token, "testuser", "testpassword")
