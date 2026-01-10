# dcmtk Service

> **DCMTK 기반 DICOM 명령 실행 컨테이너**  
> `ai4infra`의 3-Tier PACS 환경에서 DICOM 작업을 수행하기 위한 인프라 서비스입니다.

## 🚀 Quick Start

### 1. 서비스 시작
```bash
python scripts/ai4infra/ai4infra-cli.py install dcmtk
```

### 2. 연결 테스트
```bash
docker exec ai4infra-dcmtk /examples/01_echo_test.sh
```

---

## 📖 Usage

### 기본 명령 실행
```bash
# 컨테이너에서 직접 DCMTK 명령 실행
docker exec ai4infra-dcmtk echoscu -v ai4infra-orthanc-mock 4242 -aec MOCK_PACS -aet CLIENT
```

### Example Scripts

#### 1. **C-ECHO** (연결 테스트)
```bash
docker exec ai4infra-dcmtk /examples/01_echo_test.sh
```

#### 2. **C-FIND** (환자 검색)
```bash
# 전체 환자 검색
docker exec ai4infra-dcmtk /examples/02_query_patient.sh

# 특정 환자 검색
docker exec ai4infra-dcmtk /examples/02_query_patient.sh "12345"
```

#### 3. **C-MOVE** (Study 이동)
```bash
docker exec ai4infra-dcmtk /examples/03_move_study.sh "1.2.840.113619.2.55.3..."
```

---

## 🔧 Advanced Usage (응용 서비스)

### Custom Script 작성
응용 서비스에서 자체 자동화 스크립트를 작성하여 사용:

**1. 프로젝트 디렉토리 구조**
```
my-dicom-project/
├── scripts/
│   ├── batch_download.sh     # CSV 기반 일괄 다운로드
│   ├── anonymize.py          # 가명화 스크립트
│   └── workflow.sh           # 전체 워크플로우
├── config/
│   └── patients.csv          # 대상 환자 리스트
└── data/                     # 다운로드 데이터 저장
```

**2. 스크립트 실행**
```bash
# workspace 마운트하여 실행
docker exec -w /workspace ai4infra-dcmtk bash /workspace/scripts/batch_download.sh
```

**3. Docker Compose 확장**
```yaml
# my-dicom-project/docker-compose.yml
services:
  dicom-automation:
    image: ai4infra-dcmtk:latest
    volumes:
      - ./scripts:/scripts
      - ./config:/config
      - ./data:/data
    networks:
      - ai4infra
    command: bash /scripts/workflow.sh

networks:
  ai4infra:
    external: true
```

---

## 📡 PACS Endpoints

| PACS | Container Name | AET | DICOM Port | Web UI |
|------|----------------|-----|------------|--------|
| Mock | `ai4infra-orthanc-mock` | MOCK_PACS | 4242 | `pacs-mock.ai4infra.internal` |
| Raw | `ai4infra-orthanc-raw` | RAW_PACS | 4242 | `pacs-raw.ai4infra.internal` |
| Pseudo | `ai4infra-orthanc-pseudo` | PSEUDO_PACS | 4242 | `pacs-pseudo.ai4infra.internal` |

**Note**: DICOM 포트는 모두 **컨테이너 내부 포트 4242**를 사용합니다. (Docker 네트워크 내부 통신)

---

## 🛠️ DCMTK Tools Reference

### 주요 명령어
- **echoscu**: C-ECHO (연결 테스트)
- **findscu**: C-FIND (검색)
- **movescu**: C-MOVE (데이터 이동)
- **storescu**: C-STORE (데이터 전송)
- **dcmdump**: DICOM 파일 내용 확인
- **dcmodify**: DICOM 태그 수정

### 공통 옵션
- `-aet <AET>`: Calling Application Entity Title (클라이언트 AET)
- `-aec <AET>`: Called Application Entity Title (서버 AET)
- `-v`: Verbose (상세 로그)
- `-d`: Debug mode

---

## 📝 Example: Batch Download Script

**응용 서비스에서 작성하는 스크립트 예시**:

```bash
#!/bin/bash
# scripts/batch_download.sh
# CSV 파일에서 환자 리스트를 읽어 일괄 다운로드

CSV_FILE="/config/patients.csv"

while IFS=, read -r patient_id study_date; do
  echo "Processing Patient: $patient_id"
  
  # 1. Query studies
  findscu -aet CLIENT -aec MOCK_PACS \
    ai4infra-orthanc-mock 4242 \
    -k PatientID="$patient_id" \
    -k StudyDate="$study_date" \
    > "/workspace/query_${patient_id}.txt"
  
  # 2. Extract Study UIDs and Move
  grep "StudyInstanceUID" "/workspace/query_${patient_id}.txt" | \
  while read -r line; do
    STUDY_UID=$(echo $line | cut -d'[' -f2 | cut -d']' -f1)
    
    movescu -aet CLIENT -aec MOCK_PACS \
      ai4infra-orthanc-mock 4242 \
      -aem RAW_PACS +P 4242 \
      -k StudyInstanceUID="$STUDY_UID"
  done
  
done < "$CSV_FILE"

echo "Batch download completed!"
```

---

## 🔍 Troubleshooting

### Connection Refused
```bash
# 네트워크 확인
docker network inspect ai4infra

# 컨테이너 상태 확인
docker ps | grep orthanc
```

### AET Mismatch
- Orthanc 설정에서 AET가 정확히 일치하는지 확인
- Mock: `MOCK_PACS`, Raw: `RAW_PACS`, Pseudo: `PSEUDO_PACS`

### Move Destination Error
- C-MOVE 시 Destination AET (`-aem`)가 Orthanc에 등록되어 있어야 함
- Orthanc Web UI > Configuration > DICOM Modalities 에서 확인

---

## 📚 References
- [DCMTK Documentation](https://dicom.offis.de/dcmtk.php.en)
- [Orthanc DICOM Guide](https://book.orthanc-server.com/users/dicom-guide.html)
- [ai4infra Orthanc Documentation](../../documentations/orthanc.md)
