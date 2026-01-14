import re
import os
import yaml
import pytest
from pathlib import Path

# Project Root
PROJECT_ROOT = Path(__file__).parent.parent.parent

def get_services():
    """templates/ 폴더 내으 서비스 디렉토리 목록 반환"""
    templates_dir = PROJECT_ROOT / "templates"
    if not templates_dir.exists():
        return []
    return [d.name for d in templates_dir.iterdir() if d.is_dir()]

def extract_variables_from_compose(compose_path: Path) -> set:
    """
    docker-compose.yml에서 *필수* 변수만 추출
    - ${VAR} 또는 $VAR -> 추출 (필수)
    - ${VAR:-default} -> 무시 (옵션)
    - ${VAR:?error} -> 추출 (필수)
    """
    text = compose_path.read_text(encoding="utf-8")
    
    # 정규식 패턴:
    # 1. ${VAR:-...} : Optional -> Group 2 (VAR)
    # 2. ${VAR...} : Strict (simple or error) -> Group 1
    # 3. $VAR : Strict -> Group 3
    
    # We scan specifically for optional pattern first to avoid matching it as strict
    # Actually, finding all ${...} and analyzing content is safer
    
    variables = set()
    
    # 1. Find all ${...}
    braced_matches = re.finditer(r'\$\{([^}]+)\}', text)
    for m in braced_matches:
        content = m.group(1)
        if ":-" in content:
            # Has default value -> Optional
            continue
        # Remove :?error part if present
        var_name = content.split(":")[0]
        variables.add(var_name)
        
    # 2. Find all $VAR (without braces)
    # Be careful not to match existing ${...} again.
    # Simple strategy: remove all ${...} blocks from text first? 
    # Or just use a regex that asserts no leading {
    
    # Cleaning text of braced vars to avoid double counting or mismatched brackets
    # (Though logic-wise, double adding is fine since it's a Set)
    
    simple_matches = re.finditer(r'(?<!\{)\$([A-Z0-9_]+)', text)
    for m in simple_matches:
        variables.add(m.group(1))

    # Remove system vars
    for sys_var in ["PWD", "USER", "GID", "UID"]:
        if sys_var in variables:
            variables.remove(sys_var)
            
    return variables

def load_config_compose_vars(service_name: str) -> set:
    """config/{service}.yml의 compose_vars 키 목록 반환"""
    config_path = PROJECT_ROOT / "config" / f"{service_name}.yml"
    
    if not config_path.exists():
        return set()
        
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        compose_vars = data.get("compose_vars", {})
        return set(compose_vars.keys())
    except Exception:
        return set()

@pytest.mark.parametrize("service", get_services())
def test_template_variable_consistency(service):
    """
    [Integrity Check] 템플릿에서 사용하는 변수가 Config에 정의되어 있는지 검사
    """
    compose_file = PROJECT_ROOT / "templates" / service / "docker-compose.yml"
    
    if not compose_file.exists():
        pytest.skip(f"No docker-compose.yml in {service}")

    try:
        required_vars = extract_variables_from_compose(compose_file)
    except Exception as e:
        pytest.fail(f"Failed to parse {compose_file}: {e}")

    if not required_vars:
        return 

    defined_vars = load_config_compose_vars(service)
    
    # 3. Whitelist Update
    # - Global .env vars
    # - Auto-injected vars by env_manager.py
    global_whitelist = {
        "PROJECT_ROOT", "BASE_DIR", "PROJECT_NAME", "DOMAIN_NAME",
        # Auto-injected by env_manager
        "DATA_DIR", "CONF_DIR", "CERTS_DIR",
        # Credentials (usually in .env)
        "ORTHANC_ADMIN_PASSWORD", "ORTHANC_DB_PASSWORD", 
        "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB",
        "KEYCLOAK_ADMIN", "KEYCLOAK_ADMIN_PASSWORD",
        "VAULT_ADDR", "VAULT_TOKEN", "OPENREM_SECRET_KEY"
    }
    
    missing_vars = []
    for var in required_vars:
        if var in defined_vars:
            continue
        if var in global_whitelist:
            continue
            
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            if f"{var}=" in env_path.read_text():
                continue

        missing_vars.append(var)

    if missing_vars:
        pytest.fail(
            f"[{service}] Undefined variables in config/{service}.yml: {missing_vars}\n"
            f"Please define them in 'compose_vars' or ensure they are in .env"
        )
