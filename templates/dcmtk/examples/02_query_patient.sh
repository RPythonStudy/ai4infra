#!/bin/bash
# C-FIND Query: 환자 ID로 Study 검색
# Usage: docker exec ai4infra-dicom-tools /examples/02_query_patient.sh <PATIENT_ID>

set -e

PATIENT_ID=${1:-"*"}

echo "=== Querying Mock PACS for Patient: $PATIENT_ID ==="

findscu -v \
  -aet CLIENT \
  -aec MOCK_PACS \
  ai4infra-orthanc-mock 4242 \
  -k QueryRetrieveLevel=STUDY \
  -k PatientID="$PATIENT_ID" \
  -k PatientName \
  -k StudyInstanceUID \
  -k StudyDate \
  -k Modality \
  -k StudyDescription

echo "✓ Query completed"
