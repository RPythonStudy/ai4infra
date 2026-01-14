import os
import yaml
import pytest
from pathlib import Path

# Project Root
PROJECT_ROOT = Path(__file__).parent.parent.parent

def get_config_files():
    """config/ 폴더의 모든 .yml 파일 반환"""
    config_dir = PROJECT_ROOT / "config"
    return list(config_dir.glob("*.yml"))

@pytest.mark.parametrize("config_file", get_config_files())
def test_yaml_structure(config_file):
    """
    [Config Check] 모든 YAML 파일이 올바른 구조를 가지고 있는지 검사
    Core Principles: Extreme Maintenance Simplicity
    - 복잡한 스키마 라이브러리 대신, 직관적인 Python 로직으로 필수 키 검사
    """
    try:
        data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        pytest.fail(f"Invalid YAML Syntax in {config_file.name}: {e}")

    # 1. Top-Level Type Check
    assert isinstance(data, dict), f"{config_file.name} must be a dictionary at top level"

    # 2. Service Identity (Convention)
    # 모든 설정 파일은 'service' 키를 가져야 함 (Nginx 등 일부 예외가 있을 수 있으나 원칙상 권장)
    # 예외 허용: global config들이 있다면 여기서 제외 로직 추가
    if "service" in data:
        assert isinstance(data["service"], dict), "'service' section must be a dict"
        assert "enable" in data["service"], "'service.enable' key is missing"
        assert isinstance(data["service"]["enable"], bool), "'service.enable' must be boolean"

    # 3. Variable Sections (Optional but must be dict if present)
    for section in ["env_vars", "compose_vars", "entry_vars"]:
        if section in data:
            assert isinstance(data[section], dict), f"'{section}' must be a dictionary (key: value)"
            # Check values are strings or numbers (not lists/dicts)
            for k, v in data[section].items():
                assert isinstance(v, (str, int, float, bool)), \
                    f"Value for {section}.{k} must be scalar (str/int/bool), got {type(v)}"

    # 4. Image Section (Optional)
    if "image" in data:
        assert isinstance(data["image"], dict), "'image' section must be a dict"
        if "tag" in data["image"]:
             assert isinstance(data["image"]["tag"], (str, int, float)), "'image.tag' must be a string or number"

    print(f"✅ {config_file.name}: Schema Valid")
