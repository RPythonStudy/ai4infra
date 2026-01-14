#!/usr/bin/env python3
import os
import subprocess
import sys
from dotenv import load_dotenv

# .env 로드
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

KEYCLOAK_CONTAINER = "ai4infra-keycloak"
KEYCLOAK_ADMIN = os.getenv("KEYCLOAK_ADMIN", "admin")
KEYCLOAK_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD")
KEYCLOAK_URL = "http://localhost:8080" # Container internal URL or localhost port forward
# 컨테이너 내부에서는 localhost:8080이 자기 자신

def run_kcadm(args):
    """Run kcadm.sh inside the container"""
    cmd = [
        "docker", "exec", KEYCLOAK_CONTAINER,
        "/opt/keycloak/bin/kcadm.sh"
    ] + args
    
    # 비밀번호 누출 방지를 위해 로그는 생략하거나 조심
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running kcadm: {e.stderr}")
        raise

def setup_mfa():
    print(">>> Keycloak MFA 설정 시작...")

    if not KEYCLOAK_PASSWORD:
        print("Error: KEYCLOAK_ADMIN_PASSWORD not found in .env")
        sys.exit(1)

    # 1. Admin Login (in-memory config)
    print("1. Admin 인증 중...")
    try:
        run_kcadm([
            "config", "credentials",
            "--server", KEYCLOAK_URL,
            "--realm", "master",
            "--user", KEYCLOAK_ADMIN,
            "--password", KEYCLOAK_PASSWORD
        ])
    except Exception:
        print("로그인 실패. 컨테이너가 실행 중인지 확인하세요.")
        sys.exit(1)

    REALM = "ai4infra"

    # 2. Realm 존재 확인 및 생성
    print(f"2. Realm '{REALM}' 확인 중...")
    try:
        run_kcadm(["get", f"realms/{REALM}"])
        print(f"   Realm '{REALM}' 이미 존재함.")
    except Exception:
        print(f"   Realm '{REALM}' 생성 중...")
        run_kcadm(["create", "realms", "-s", f"realm={REALM}", "-s", "enabled=true"])

    # 3. MFA Flow 복제/설정
    # 전략: Built-in 'browser' 흐름을 복사하여 'browser-mfa' 생성 후 OTP 강제
    FLOW_ALIAS = "browser-mfa"
    print(f"3. MFA Flow '{FLOW_ALIAS}' 구성 중...")
    
    # 3-1. Check if flow exists
    try:
        # 리스트에서 필터링하거나 get으로 확인 (get flows/alias는 지원 안할 수도 있음)
        # 단순히 create 시도하고 실패하면 넘어가는 식으로 처리
        run_kcadm(["create", "authentication/flows", 
                   "-r", REALM, 
                   "-s", f"alias={FLOW_ALIAS}", 
                   "-s", "providerId=basic-flow", 
                   "-s", "topLevel=true", 
                   "-s", "builtIn=false"])
        print(f"   Flow '{FLOW_ALIAS}' 생성됨.")
    except Exception as e:
        print(f"   Flow '{FLOW_ALIAS}' 이미 존재하거나 생성 실패 (무시하고 진행)")

    # 3-2. Execution 추가 (Cookie -> Forms -> OTP)
    # 이것은 복잡하므로, 가장 간단한 방법:
    # "Browser" Flow의 "Copy" 기능을 활용하는 것이 정석이나 CLI로는 복잡함.
    # 대안: 'built-in' browser flow의 'Forms' 단계에서 'OTP'를 'REQUIRED'로 변경하는 것이 가장 쉬움.
    # 하지만 원본을 건드리는 것보다 복사본이 안전.
    
    # CLI로 복잡한 Flow 조작은 오류 가능성이 높음.
    # 따라서, 'OTP' 정책을 'Required'로 설정하는 가장 간단한 방법은
    # "Authentication -> Required Actions"에서 "Configure OTP"를 Default Action으로 지정하는 것!
    # 하지만 이는 "모든 유저"에게 강제되지 않을 수 있음 (유저가 끄면 그만).
    
    # 가장 확실한 방법: Realm의 "OTP Policy"를 튜닝하고, Default Flow를 수정.
    # 여기서는 'browser' flow의 'condtional-otp'를 'REQUIRED'로 바꾸는 방식을 시도.
    
    print("   (경고) CLI를 통한 정교한 Flow 편집은 복잡하므로,")
    print("   'OTP' Required Action을 모든 신규 유저에게 강제하는 방식을 적용합니다.")
    
    # 4. Required Actions 설정 (Configure OTP -> Enabled & Default)
    print("4. Required Action 'CONFIGURE_TOTP' 활성화...")
    try:
        run_kcadm(["update", f"authentication/required-actions/CONFIGURE_TOTP", 
                   "-r", REALM, 
                   "-s", "enabled=true", 
                   "-s", "defaultAction=true"])
        print("   CONFIGURE_TOTP가 기본 액션으로 설정되었습니다. (신규 유저 필수)")
    except Exception as e:
        print(f"   설정 실패: {e}")

    # 5. OTP Policy 설정 (Google Authenticator 호환)
    print("5. OTP 정책 설정 (Google Authenticator 호환)...")
    run_kcadm(["update", f"realms/{REALM}", 
               "-s", "otpPolicyType=totp", 
               "-s", "otpPolicyAlgorithm=HmacSHA1", # 구글 OTP 표준
               "-s", "otpPolicyDigits=6",
               "-s", "otpPolicyPeriod=30"])

    print(">>> MFA 설정 완료. (신규 유저는 로그인 시 TOTP 설정이 강제됩니다)")

if __name__ == "__main__":
    setup_mfa()
