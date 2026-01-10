#!/bin/bash
# C-ECHO Test: DICOM 연결 테스트
# Usage: docker exec ai4infra-dicom-tools /examples/01_echo_test.sh

set -e

echo "=== DICOM C-ECHO Test ==="

# Mock PACS
echo "[1/3] Testing Mock PACS..."
echoscu -v \
  -aet CLIENT \
  -aec MOCK_PACS \
  ai4infra-orthanc-mock 4242

# Raw PACS
echo "[2/3] Testing Raw PACS..."
echoscu -v \
  -aet CLIENT \
  -aec RAW_PACS \
  ai4infra-orthanc-raw 4242

# Pseudo PACS
echo "[3/3] Testing Pseudo PACS..."
echoscu -v \
  -aet CLIENT \
  -aec PSEUDO_PACS \
  ai4infra-orthanc-pseudo 4242

echo "✓ All PACS connections OK!"
