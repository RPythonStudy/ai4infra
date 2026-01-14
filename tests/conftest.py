import pytest
import urllib3
import warnings

@pytest.fixture(autouse=True)
def suppress_insecure_request_warning():
    """
    Globally suppress InsecureRequestWarning for tests.
    We are intentionally using self-signed certificates in the dev environment.
    """
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    warnings.simplefilter('ignore', urllib3.exceptions.InsecureRequestWarning)
