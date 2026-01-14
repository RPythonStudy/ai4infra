#!/usr/bin/env python3
import os
import subprocess
import json
import secrets
import string
import re
from dotenv import load_dotenv

# Path Setup
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

# Load existing .env
load_dotenv(ENV_PATH)

KEYCLOAK_CONTAINER = "ai4infra-keycloak"
KEYCLOAK_URL = "http://localhost:8080"
KEYCLOAK_ADMIN = os.getenv("KEYCLOAK_ADMIN", "admin")
KEYCLOAK_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD")

REALM_NAME = "ai4infra"
CLIENT_ID = "nginx"

def generate_random_string(length=32):
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))

def update_env_var(key, value):
    """Update or append a variable in .env file safely."""
    with open(ENV_PATH, "r") as f:
        content = f.read()

    # Check if key exists
    pattern = re.compile(rf"^{key}=.*$", re.MULTILINE)
    if pattern.search(content):
        # Update existing
        new_content = pattern.sub(f"{key}={value}", content)
    else:
        # Append new
        new_content = content + f"\n{key}={value}\n"
    
    with open(ENV_PATH, "w") as f:
        f.write(new_content)
    print(f"   Updated .env: {key}=***")

def run_kcadm(args):
    cmd = ["docker", "exec", KEYCLOAK_CONTAINER, "/opt/keycloak/bin/kcadm.sh"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip()

def main():
    print(">>> [Keycloak Setup] Starting automation...")

    # 1. Login
    print("1. Logging into Keycloak Admin CLI...")
    run_kcadm(["config", "credentials", "--server", KEYCLOAK_URL, "--realm", "master", "--user", KEYCLOAK_ADMIN, "--password", KEYCLOAK_PASSWORD])

    # 2. Setup Realm
    print(f"2. Ensuring Realm '{REALM_NAME}' exists...")
    try:
        run_kcadm(["get", f"realms/{REALM_NAME}"])
        print(f"   Realm '{REALM_NAME}' already exists.")
    except subprocess.CalledProcessError:
        print(f"   Creating Realm '{REALM_NAME}'...")
        run_kcadm(["create", "realms", "-s", f"realm={REALM_NAME}", "-s", "enabled=true"])

    # 3. Setup Client
    print(f"3. Ensuring Client '{CLIENT_ID}' exists...")
    client_json = None
    try:
        out = run_kcadm(["get", "clients", "-r", REALM_NAME, "-q", f"clientId={CLIENT_ID}"])
        clients = json.loads(out)
        if clients:
            print(f"   Client '{CLIENT_ID}' already exists. Updating configuration...")
            client_json = clients[0]
            # Ensure Direct Grant is enabled (Fixed for Pytest)
            run_kcadm(["update", f"clients/{client_json['id']}", "-r", REALM_NAME, "-s", "directAccessGrantsEnabled=true"])
        else:
            raise Exception("Client not found")
    except Exception:
        print(f"   Creating Client '{CLIENT_ID}'...")
        # Create standard OIDC client for Nginx (confidential access type)
        run_kcadm(["create", "clients", "-r", REALM_NAME, 
                   "-s", f"clientId={CLIENT_ID}", 
                   "-s", "enabled=true",
                   "-s", "clientAuthenticatorType=client-secret", 
                   "-s", "secret=", # Let Keycloak generate
                   "-s", "redirectUris=[\"https://ai4infra.internal/*\", \"https://localhost/*\"]", 
                   "-s", "webOrigins=[\"+\"]",
                   "-s", "standardFlowEnabled=true",
                   "-s", "directAccessGrantsEnabled=true", # [Fixed] Allow Direct Grant for Testing
                   "-s", "publicClient=false"]) # Confidential
        
        # Reload to get ID
        out = run_kcadm(["get", "clients", "-r", REALM_NAME, "-q", f"clientId={CLIENT_ID}"])
        client_json = json.loads(out)[0]


    # 4. Get/Rotate Secret
    print("4. Retrieving Client Secret...")
    client_uuid = client_json['id']
    # Get secret
    out = run_kcadm(["get", f"clients/{client_uuid}/client-secret", "-r", REALM_NAME])
    secret_data = json.loads(out)
    client_secret = secret_data['value']
    
    # 5. Update .env (OIDC config)
    print("5. Updating .env with OIDC configuration...")
    update_env_var("OIDC_PROVIDER", "keycloak")
    update_env_var("OIDC_CLIENT_ID", CLIENT_ID)
    update_env_var("OIDC_CLIENT_SECRET", client_secret)

    # Ensure Cookie Secret exists
    if not os.getenv("OIDC_COOKIE_SECRET"):
        print("   Generating new OIDC_COOKIE_SECRET...")
        update_env_var("OIDC_COOKIE_SECRET", generate_random_string(32))
    
    # 6. Configure MFA (OTP)
    print("6. Configuring MFA (OTP) Policy...")
    # 6-1. Set OTP Policy
    run_kcadm(["update", f"realms/{REALM_NAME}", 
               "-s", "otpPolicyType=totp", 
               "-s", "otpPolicyAlgorithm=HmacSHA1",
               "-s", "otpPolicyDigits=6",
               "-s", "otpPolicyPeriod=30"])
    
    # 6-2. Enforce CONFIGURE_TOTP for all new users (Default Action)
    # Check if enabled
    try:
        run_kcadm(["update", f"authentication/required-actions/CONFIGURE_TOTP", 
                   "-r", REALM_NAME, 
                   "-s", "enabled=true", 
                   "-s", "defaultAction=true"])
        print("   MFA Requirement configured: CONFIGURE_TOTP is now default action.")
    except Exception as e:
        print(f"   Warning: Failed to set CONFIGURE_TOTP default: {e}")

    # 7. Create Test User (Optional)
    print("7. Ensuring 'testuser' exists...")
    try:
        out = run_kcadm(["get", "users", "-r", REALM_NAME, "-q", "username=testuser"])
        users = json.loads(out)
        if not users:
            print("   Creating 'testuser'...")
            run_kcadm(["create", "users", "-r", REALM_NAME, "-s", "username=testuser", "-s", "enabled=true"])
            # Set password
            run_kcadm(["set-password", "-r", REALM_NAME, "--username", "testuser", "--new-password", "testpassword"])
        else:
            print("   'testuser' already exists.")
    except Exception:
        pass

    # 7-1. Create Guest User (for negative testing)
    print("7-1. Ensuring 'guestuser' exists...")
    try:
        out = run_kcadm(["get", "users", "-r", REALM_NAME, "-q", "username=guestuser"])
        users = json.loads(out)
        if not users:
            print("   Creating 'guestuser'...")
            run_kcadm(["create", "users", "-r", REALM_NAME, "-s", "username=guestuser", "-s", "enabled=true"])
            # Set password
            run_kcadm(["set-password", "-r", REALM_NAME, "--username", "guestuser", "--new-password", "guestpassword"])
            
            # [Fix for Pytest] Remove Required Actions (MFA Setup) to allow Direct Grant login
            # Get User ID
            out = run_kcadm(["get", "users", "-r", REALM_NAME, "-q", "username=guestuser"])
            guest_id = json.loads(out)[0]['id']
            # Clear required actions
            run_kcadm(["update", f"users/{guest_id}", "-r", REALM_NAME, "-s", "requiredActions=[]"])
            print("   'guestuser' required actions cleared (MFA bypassed for testing).")
        else:
            print("   'guestuser' already exists.")
            # Ensure required actions are cleared even if exists
            out = run_kcadm(["get", "users", "-r", REALM_NAME, "-q", "username=guestuser"])
            guest_id = json.loads(out)[0]['id']
            run_kcadm(["update", f"users/{guest_id}", "-r", REALM_NAME, "-s", "requiredActions=[]"])

    except Exception:
        pass

    # 8. [SEC-04] RBAC: Roles & Mappers
    print("8. Configuring RBAC (Roles & Mappers)...")
    roles = ["admin", "user"]
    for role in roles:
        try:
            run_kcadm(["create", "roles", "-r", REALM_NAME, "-s", f"name={role}"])
            print(f"   Role '{role}' created.")
        except Exception:
            print(f"   Role '{role}' already exists.")
    
    # 8-1. Assign 'admin' role to 'testuser'
    print("   Assigning 'admin' role to 'testuser'...")
    try:
        run_kcadm(["add-roles", "-r", REALM_NAME, "--uusername", "testuser", "--rolename", "admin"])
    except Exception as e:
        print(f"   Failed to assign role (maybe already assigned): {e}")

    # 8-2. Add Mapper to include roles in ID Token (Important for Nginx/Lua)
    # Check existing mappers
    print("   Configuring Role Mapper for Client...")
    mapper_name = "realm roles"
    try:
        # Create a protocol mapper to add realm roles to the ID token
        # This is often default, but ensuring it maps to specific claim 'realm_access.roles' or plain 'roles'
        # Let's map it to top-level claim 'roles' for easier Lua parsing
        run_kcadm(["create", "clients", "-r", REALM_NAME, 
                   "-c", CLIENT_ID, 
                   "-s", f"name={mapper_name}",
                   "-s", "protocol=openid-connect",
                   "-s", "protocolMapper=oidc-usermodel-realm-role-mapper", 
                   "-s", "consentRequired=false",
                   "-s", "config.\"multivalued\"=true",
                   "-s", "config.\"user.attribute\"=foo", 
                   "-s", "config.\"id.token.claim\"=true", 
                   "-s", "config.\"access.token.claim\"=true", 
                   "-s", "config.\"claim.name\"=roles", 
                   "-s", "config.\"jsonType.label\"=String"])
        print("   Role Mapper created (roles claim).")
    except Exception:
        print("   Role Mapper might already exist.")

    # 8-3. [SEC-04] Fix: Add Audience Mapper to ensure aud=nginx in Access Token
    print("   Configuring Audience Mapper (aud=nginx)...")
    try:
        # Check if mapper exists
        out = run_kcadm(["get", f"clients/{client_uuid}/protocol-mappers/models", "-r", REALM_NAME])
        if "audience-mapping" not in out:
            run_kcadm(["create", f"clients/{client_uuid}/protocol-mappers/models", "-r", REALM_NAME,
                "-s", "name=audience-mapping",
                "-s", "protocol=openid-connect",
                "-s", "protocolMapper=oidc-audience-mapper",
                "-s", "config.\"included.client.audience\"=nginx",
                "-s", "config.\"id.token.claim\"=false",
                "-s", "config.\"access.token.claim\"=true"])
            print("   Audience Mapper created.")
        else:
            print("   Audience Mapper already exists.")
    except Exception as e:
        print(f"   Failed to create Audience Mapper: {e}")

    print(">>> [Keycloak Setup] Completed Successfully!")

if __name__ == "__main__":
    main()
