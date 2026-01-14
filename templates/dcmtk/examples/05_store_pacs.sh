#!/bin/bash
# 05_store_pacs.sh - Store local DICOM to PACS using storescu
# Usage: ./05_store_pacs.sh /workspace/data/target_folder RAW_PACS

TARGET_PATH=${1:-"/workspace/data"}
DEST_AE=${2:-"RAW_PACS"}
DEST_HOST="ai4infra-orthanc-$(echo $DEST_AE | tr '[:upper:]' '[:lower:]' | cut -d'_' -f1)"

echo "=== Store DICOM to PACS (storescu) ==="

if [ ! -d "$TARGET_PATH" ] && [ ! -f "$TARGET_PATH" ]; then
    echo "Error: Path not found: $TARGET_PATH"
    exit 1
fi

echo "Dest AE: $DEST_AE ($DEST_HOST:4242)"
echo "Storing files from: $TARGET_PATH"

storescu -v -aet CLIENT -aec $DEST_AE $DEST_HOST 4242 +r "$TARGET_PATH"/*.dcm

echo "✓ Store operation complete!"
