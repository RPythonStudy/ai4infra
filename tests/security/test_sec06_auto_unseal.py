import pytest
import subprocess
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT_PATH = os.path.join(PROJECT_ROOT, "scripts/ai4infra/auto_unseal.py")
VENV_PYTHON = os.path.join(PROJECT_ROOT, ".venv/bin/python")

def test_auto_unseal_script_execution():
    """
    [SEC-06] Auto Unseal Script Execution
    Verify the script runs without syntax errors and attempts to connect.
    """
    # Environment Setup for Test
    env = os.environ.copy()
    env["USB_MOUNT_PATH"] = os.path.join(PROJECT_ROOT, "mock_usb") # Point to local mock usb
    env["VAULT_ADDR"] = "https://127.0.0.1:8200"

    try:
        result = subprocess.run(
            [VENV_PYTHON, SCRIPT_PATH],
            env=env,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Check standard output for success markers
        stdout = result.stdout
        print("Script Output:", stdout)
        
        # Success if it says "Active" (Already unsealed) or "Unsealed Successfully"
        success_markers = ["Active (Unsealed)", "Unsealed Successfully", "already ACTIVE"]
        assert any(marker in stdout for marker in success_markers), "Auto-Unseal script did not report success."
        
        assert result.returncode == 0, "Script exited with error code"

    except subprocess.TimeoutExpired:
        pytest.fail("Auto-Unseal script timed out.")
    except Exception as e:
        pytest.fail(f"Execution failed: {e}")

if __name__ == "__main__":
    test_auto_unseal_script_execution()
    print("SEC-06 Auto-Unseal Verified [PASS]")
