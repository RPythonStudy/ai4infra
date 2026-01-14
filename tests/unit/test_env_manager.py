import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add paths to allow imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT / "scripts" / "ai4infra"))
sys.path.append(str(PROJECT_ROOT / "src"))

# Mock dotenv before importing env_manager to avoid side effects
with patch("dotenv.load_dotenv"):
    from utils.container import env_manager

class TestEnvManager:
    @pytest.fixture
    def mock_env_content(self):
        return """
# ORTHANC
ORTHANC_DB_NAME=orthanc_db
# ANOTHER
OTHER_VAR=value
"""

    def test_extract_env_vars(self, mock_env_content):
        """Verify extracting variables from a specific section in .env"""
        with patch("builtins.open", new_callable=MagicMock) as mock_open:
            # Setup mock file reading
            mock_open.return_value.__enter__.return_value = mock_env_content.splitlines()
            
            # Execute
            vars = env_manager.extract_env_vars("dummy_path", "ORTHANC")
            
            # Verify
            assert vars.get("ORTHANC_DB_NAME") == "orthanc_db"
            assert "OTHER_VAR" not in vars  # Should not extract other sections

    def test_merging_priority(self):
        """
        Verify priority: .env < compose_vars < env_vars < entry_vars
        """
        base_env = {"COMMON": "base", "OVERRIDE_ME": "base_val"}
        config_data = {
            "compose_vars": {"COMPOSE": "val", "OVERRIDE_ME": "compose_val"},
            "env_vars": {"ENV": "val", "OVERRIDE_ME": "env_val"},
            "entry_vars": {"ENTRY": "val", "OVERRIDE_ME": "final_val"}
        }

        # Mock dependencies of generate_env
        with patch("utils.container.env_manager.extract_env_vars", return_value=base_env), \
             patch("utils.container.env_manager.extract_config_vars", return_value=config_data), \
             patch("utils.container.env_manager.subprocess.run") as mock_run, \
             patch("utils.container.env_manager.Path.exists", return_value=True), \
             patch("tempfile.NamedTemporaryFile") as mock_temp:
             
            # Setup mock temp file
            mock_temp_obj = MagicMock()
            mock_temp.return_value.__enter__.return_value = mock_temp_obj
            mock_temp_obj.name = "/tmp/dummy"

            # Execute
            env_manager.generate_env("test_service")

            # Capture all content written to file
            full_content = ""
            for call in mock_temp_obj.write.call_args_list:
                full_content += call[0][0]
            
            # Verify Priority (OVERRIDE_ME should be 'final_val' from entry_vars)
            assert "OVERRIDE_ME=final_val" in full_content
            
            # Verify Inclusion
            assert "ENTRY=val" in full_content
            assert "ENV=val" in full_content
            assert "COMPOSE=val" in full_content
            assert "COMMON=base" in full_content

    def test_standard_paths_injection(self):
        """Verify DATA_DIR, CONF_DIR, CERTS_DIR are automatically injected."""
        with patch("utils.container.env_manager.extract_env_vars", return_value={}), \
             patch("utils.container.env_manager.extract_config_vars", return_value={}), \
             patch("utils.container.env_manager.subprocess.run"), \
             patch("utils.container.env_manager.Path.exists", return_value=True), \
             patch("tempfile.NamedTemporaryFile") as mock_temp:
            
            mock_temp_obj = MagicMock()
            mock_temp.return_value.__enter__.return_value = mock_temp_obj
            
            # Mock BASE_DIR for predictable paths
            env_manager.BASE_DIR = "/opt/test"
            
            env_manager.generate_env("myservice")
            
            full_content = ""
            for call in mock_temp_obj.write.call_args_list:
                full_content += call[0][0]
                
            assert "DATA_DIR=/opt/test/myservice/data" in full_content
            assert "CONF_DIR=/opt/test/myservice/config" in full_content
            assert "CERTS_DIR=/opt/test/myservice/certs" in full_content
