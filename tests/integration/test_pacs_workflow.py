import pytest
import subprocess
import requests
import time
import os

# Configuration
DOCKER_CONTAINER = "ai4infra-dcmtk"
TARGET_PACS_HOST = "ai4infra-orthanc-mock"
TARGET_PACS_PORT = "4242"
TARGET_PACS_AET = "MOCK_PACS"
ORTHANC_API_URL = "http://localhost:8043"
ORTHANC_USER = "admin"
ORTHANC_PASSWORD = "orthanc"

def run_docker_cmd(cmd):
    """Run a command inside the DCMTK container."""
    full_cmd = f"docker exec {DOCKER_CONTAINER} {cmd}"
    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    return result

def test_container_running():
    """Ensure the DCMTK container is running."""
    result = subprocess.run(
        f"docker ps -q -f name={DOCKER_CONTAINER}",
        shell=True, capture_output=True, text=True
    )
    assert result.stdout.strip(), f"Container {DOCKER_CONTAINER} is not running."

def test_c_echo():
    """Test C-ECHO (Connectivity) to Orthanc."""
    cmd = f"echoscu -v {TARGET_PACS_HOST} {TARGET_PACS_PORT} -aec {TARGET_PACS_AET}"
    result = run_docker_cmd(cmd)
    
    print(f"C-ECHO Output:\n{result.stderr}") # echoscu often writes to stderr for verbose info
    assert result.returncode == 0, f"C-ECHO failed: {result.stderr}"

def test_c_store_and_verify():
    """Test C-STORE (Upload) and verify via API."""
    # 1. Create a minimal DICOM dump file content
    dataset_dump = """
    (0010,0010) PN [Test^Patient]
    (0010,0020) LO [123456]
    (0008,0020) DA [20260101]
    (0008,0060) CS [OT]
    (0020,000d) UI [1.2.3.4.5.6.7.8]
    (0020,000e) UI [1.2.3.4.5.6.7.8.2]
    (0008,0016) UI [1.2.840.10008.5.1.4.1.1.7]
    (0008,0018) UI [1.2.3.4.5.6.7.8.1]
    """
    
    dump_filename = "test_data.dump"
    dcm_filename = "test_data.dcm"
    
    # Write dump file to local temp
    with open(dump_filename, "w") as f:
        f.write(dataset_dump)
        
    try:
        # 2. Copy dump file to container
        subprocess.run(f"docker cp {dump_filename} {DOCKER_CONTAINER}:/tmp/{dump_filename}", shell=True, check=True)
        
        # 3. Convert dump to DICOM inside container
        convert_cmd = f"dump2dcm /tmp/{dump_filename} /tmp/{dcm_filename}"
        run_docker_cmd(convert_cmd)
        
        # 4. Send DICOM via C-STORE
        store_cmd = f"storescu -v -aec {TARGET_PACS_AET} {TARGET_PACS_HOST} {TARGET_PACS_PORT} /tmp/{dcm_filename}"
        result = run_docker_cmd(store_cmd)
        
        print(f"C-STORE Output:\n{result.stderr}")
        assert result.returncode == 0, f"C-STORE failed: {result.stderr}"
        
        # 5. Verify via Orthanc API
        # Wait a moment for indexing (Postgres)
        time.sleep(1)
        
        # Check if patient exists
        auth = (ORTHANC_USER, ORTHANC_PASSWORD)
        resp = requests.get(f"{ORTHANC_API_URL}/patients", auth=auth)
        assert resp.status_code == 200, "Failed to query Orthanc API"
        
        patients = resp.json()
        assert len(patients) > 0, "No patients found in Orthanc after upload"
        
        # Optional: Verify specific PatientID
        found = False
        for patient_id in patients:
            p_resp = requests.get(f"{ORTHANC_API_URL}/patients/{patient_id}", auth=auth)
            if p_resp.status_code == 200:
                p_data = p_resp.json()
                if "MainDicomTags" in p_data and p_data["MainDicomTags"].get("PatientID") == "123456":
                    found = True
                    break
        
        assert found, "Uploaded PatientID '123456' not found in Orthanc"

    finally:
        # Cleanup local file
        if os.path.exists(dump_filename):
            os.remove(dump_filename)
        # Cleanup container files (optional, but good practice)
        run_docker_cmd(f"rm /tmp/{dump_filename} /tmp/{dcm_filename}")

if __name__ == "__main__":
    # Allow running directly for debugging
    test_container_running()
    test_c_echo()
    test_c_store_and_verify()
    print("All integration tests passed manually.")
