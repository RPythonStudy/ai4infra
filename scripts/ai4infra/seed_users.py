#!/usr/bin/env python3
import os
import sys
import subprocess
import codecs

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.append(os.path.join(PROJECT_ROOT, "src"))

from common.logger import log_info, log_error

USERS = [
    {"name": "Kevin Kim", "id": "rmchair", "email": "rmchair@r.python.study"}, # 김의학 -> Kevin Kim (English for LDAP safety)
    {"name": "Lee Pseudo", "id": "rmpseudo", "email": "rmpseudo@r.python.study"}, # 이가명
    {"name": "Park Security", "id": "rmsec", "email": "rmsec@r.python.study"}, # 박보안
    {"name": "Choi Server", "id": "rminfra", "email": "rminfra@r.python.study"}, # 최서버
    {"name": "Kang DE", "id": "rmdengineer", "email": "rmdengineer@r.python.study"}, # 강데엔
    {"name": "Han Info", "id": "rminfo", "email": "rminfo@r.python.study"}, # 한정보
    {"name": "Jung Curator", "id": "rmcurator", "email": "rmcurator@r.python.study"}, # 정큐레
    {"name": "Oh Clinical", "id": "rmclin", "email": "rmclin@r.python.study"}, # 오임상
    {"name": "Yoo AI", "id": "rmai", "email": "rmai@r.python.study"}, # 유AI
    {"name": "Moon Researcher", "id": "rmairesearcher", "email": "rmairesearcher@r.python.study"}, # 문에이
    {"name": "Jang AppDev", "id": "rmappdev", "email": "rmappdev@r.python.study"}, # 장앱
    {"name": "Shim IRB", "id": "rmirb", "email": "rmirb@r.python.study"}, # 심IRB
    {"name": "Researcher Sample", "id": "researcher01", "email": "researcher01@r.python.study"}, # researcherXX
]

LDIF_FILE = os.path.join(PROJECT_ROOT, "users_seed.ldif")

def generate_ldif():
    with codecs.open(LDIF_FILE, "w", "utf-8") as f:
        for user in USERS:
            uid = user["id"]
            cn = user["name"]
            sn = user["name"].split()[-1] # Last token as surname
            mail = user["email"]
            # Default password logic: [ID]_ldap
            password = f"{uid}_ldap"
            
            entry = f"""dn: uid={uid},dc=ai4infra,dc=internal
changetype: add
objectClass: inetOrgPerson
objectClass: organizationalPerson
objectClass: top
cn: {cn}
sn: {sn}
uid: {uid}
mail: {mail}
userPassword: {password}

"""
            f.write(entry)
    log_info(f"Generated LDIF file at: {LDIF_FILE}")

def apply_ldif():
    container_name = "ai4infra-ldap"
    target_path = "/tmp/users_seed.ldif"
    
    # Copy LDIF to container
    cmd_cp = ["sudo", "docker", "cp", LDIF_FILE, f"{container_name}:{target_path}"]
    subprocess.check_call(cmd_cp)
    
    # Run ldapadd
    # -x: Simple authentication
    # -D: Bind DN
    # -w: Password (admin) - ideally from env but hardcoded for this setup script as per config
    cmd_ldapadd = [
        "sudo", "docker", "exec", container_name,
        "ldapadd", "-x", "-D", "cn=admin,dc=ai4infra,dc=internal", "-w", "admin", "-H", "ldap://localhost", "-f", target_path, "-c"
    ]
    
    log_info("Applying LDIF to LDAP...")
    try:
        # -c continues on error (e.g. user already exists)
        subprocess.check_call(cmd_ldapadd)
        log_info("Users added successfully (errors ignored for existing users).")
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to add users: {e}")

def main():
    generate_ldif()
    apply_ldif()
    # Cleanup
    if os.path.exists(LDIF_FILE):
        os.remove(LDIF_FILE)

if __name__ == "__main__":
    main()
