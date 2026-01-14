# OpenREM Service Guide

> **OpenREM** (Open Radiation Exposure Monitoring)은 환자가 검사 중에 받는 방사선량을 모니터링하고 분석하기 위한 오픈소스 플랫폼입니다. 
> DICOM RDSR(Radiation Dose Structured Report) 및 이미지 헤더에서 데이터를 추출하여 선량 관리를 지원합니다.

## 1. Architecture

- **App Server**: `openrem/openrem:1.0.0b2` (Django 기반)
- **Worker**: Celery를 사용하여 백그라운드에서 DICOM 추출 및 처리 수행.
- **Broker**: `Redis`를 메시지 브로커로 사용합니다.
- **Database**: `PostgreSQL`을 메인 저장소로 사용합니다.
- **Gateway**: Nginx를 통해 `openrem.ai4infra.internal` 도메인으로 서비스됩니다.

## 2. Installation

OpenREM은 Redis가 필요하므로 순서대로 설치합니다.

```bash
# 1. Redis 설치 (이미 설치되어 있다면 생략 가능)
python scripts/ai4infra/ai4infra-cli.py install redis

# 2. OpenREM 설치
python scripts/ai4infra/ai4infra-cli.py install openrem
```

## 3. Configuration

### Environment Variables (`config/openrem.yml`)
- `OPENREM_PORT`: 호스트 내부 포트 (기본: 8086).
- `OPENREM_VERSION`: 이미지 버전 (기본: 1.0.0b2).
- `ALLOWED_HOSTS`: 허용할 도메인 설정.

## 4. Usage

### 🌐 Web Access
- **URL**: [http://openrem.ai4infra.internal](http://openrem.ai4infra.internal)
- **Initial Setup**: 최초 접속 시 관리자 계정 생성이 필요할 수 있습니다. 
  컨테이너 내부에서 다음 명령으로 생성 가능합니다:
  ```bash
  sudo docker exec -it ai4infra-openrem python manage.py createsuperuser
  ```

### 📡 DICOM Reception
- OpenREM은 DICOM 데이터를 받아야 선량 분석이 가능합니다.
- 기본적으로 웹 인터페이스에서 DICOM 리스너를 설정하거나, `ai4infra-dcmtk`를 사용하여 데이터를 전송할 수 있습니다.

## 5. Typical Workflow

1. **데이터 수집**: Orthanc(Mock/Raw)에 저장된 데이터를 OpenREM의 DICOM 리스너로 전송(C-MOVE/C-STORE)합니다.
2. **자동 추출**: OpenREM Worker가 백그라운드에서 선량 정보를 추출하여 DB에 저장합니다.
3. **분석 및 리포팅**: 웹 UI에서 환자별, 장비별, 검사 프로토콜별 선량 통계를 확인합니다.
