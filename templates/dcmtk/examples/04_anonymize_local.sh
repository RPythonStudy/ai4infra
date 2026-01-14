#!/bin/bash
# 04_anonymize_local.sh - Local Anonymization Example using dcmodify
# Usage: ./04_anonymize_local.sh /workspace/data/target_folder

TARGET_PATH=${1:-"/workspace/data"}

echo "=== Local DICOM Anonymization (dcmodify) ==="

if [ ! -d "$TARGET_PATH" ] && [ ! -f "$TARGET_PATH" ]; then
    echo "Error: Path not found: $TARGET_PATH"
    exit 1
fi

echo "Anonymizing: $TARGET_PATH"

# 태그 수정 (PatientName, PatientID 제거 또는 변경)
find "$TARGET_PATH" -name "*.dcm" -exec dcmodify \
    -m "(0010,0010)=ANONYMOUS" \
    -m "(0010,0020)=99999" \
    -e "(0010,0030)" \
    -e "(0010,1010)" \
    {} +

echo "✓ Anonymization complete!"
