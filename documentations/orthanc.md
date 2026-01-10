# Orthanc Service Guide

> **Orthanc**는 경량화된 오픈소스 DICOM 서버(PACS)입니다. 
> `ai4infra` 프로젝트에서는 의료 영상 데이터의 저장, 조회(OHIF), 전송을 담당합니다.

## 1. Architecture

### Components
- **Orthanc Server (Container)**: `jodogne/orthanc-plugins` 이미지를 사용하며, PostgreSQL, OHIF Viewer, DicomWeb 플러그인이 포함되어 있습니다.
- **PostgreSQL (Database)**: 메타데이터 인덱싱을 담당합니다. (`ai4infra-postgres`)
- **FileSystem (Storage)**: 대용량 DICOM 파일은 로컬 디스크(`data/`)에 직접 저장합니다.
- **Nginx (Gateway)**: `pacs.ai4infra.internal` 도메인을 통해 웹 UI 접근을 중계합니다.

### Custom Entrypoint Strategy
`jodogne/orthanc` 이미지가 환경변수 오버라이드를 일부 제한하거나, 복잡한 JSON 설정 시 파싱 문제가 있어 **Custom Entrypoint**를 사용합니다.
- **Config**: `templates/orthanc/orthanc.json` (Read-only Template)
- **Script**: `templates/orthanc/entrypoint.sh`
- **Logic**: 실행 시 템플릿을 `/tmp`로 복사하고, `sed`를 사용하여 `.env`의 비밀번호 변수를 치환한 후 Orthanc를 실행합니다.

## 2. Installation

```bash
make install-orthanc
```
- **Postgres DB**: `orthanc` 유저와 DB가 없으면 자동 생성합니다.
- **Nginx Config**: `conf.d/orthanc.conf`를 복사하고 Nginx를 재시작합니다.

## 3. Configuration

### Environment Variables (`.env`)
- `ORTHANC_ADMIN_PASSWORD`: 웹 UI(`admin`) 접속 비밀번호.
- `ORTHANC_DB_PASSWORD`: Postgres 연결 비밀번호.

### Service Config (`config/orthanc.yml`)
- 포트 및 메모리 제한 등을 설정합니다.
- `env_vars`에 Entrypoint에서 사용할 변수들을 매핑해두어야 합니다.

### Orthanc JSON (`templates/orthanc/orthanc.json`)
- Orthanc의 핵심 설정 파일입니다.
- **Plugins**: `/usr/share/orthanc/plugins` 경로 명시 필수.
- **PostgreSQL**: `EnableIndex: true`, `EnableStorage: false`.
- **DicomWeb & OHIF**: 활성화 설정.

## 4. Usage

- **Web UI**: [http://pacs.ai4infra.internal](http://pacs.ai4infra.internal) (ID: admin / PW: .env 참조)
- **DICOM Port**: `localhost:4242` (AET: ORTHANC)
- **OHIF Viewer**: 웹 UI 내에서 `OHIF` 버튼 클릭 또는 `/ohif/` 경로.

## 5. Troubleshooting

### `fe_sendauth: no password supplied`
- **원인**: Entrypoint 스크립트가 환경변수를 제대로 치환하지 못했음.
- **해결**: `.env` 파일이 올바르게 로드되었는지, `config/orthanc.yml`의 `env_vars`에 해당 변수(`ORTHANC_DB_PASSWORD`)가 선언되어 있는지 확인.

### `Plugin ... No available configuration`
- **원인**: `orthanc.json`에서 `Plugins` 경로 리스트가 누락됨.
- **해결**: `["/usr/share/orthanc/plugins", ...]` 추가.

### `HTTP 404 Not Found` (Nginx)
- **원인**: Nginx 설정 파일(`orthanc.conf`)이 컨테이너에 없거나 오타.
- **해결**: `make install-orthanc`를 다시 실행하여 설정 파일을 복사하고 Nginx 리로드.
