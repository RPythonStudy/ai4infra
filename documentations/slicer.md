# 3D Slicer Service Guide

> **3D Slicer**는 의료 영상 분석, 시각화 및 알고리즘 개발을 위한 강력한 오픈소스 플랫폼입니다. 
> `ai4infra` 프로젝트는 웹 기반 UI와 Python 자동화 환경을 포함한 3D Slicer 서비스를 제공합니다.

## 1. Architecture

- **Slicer Server**: `slicer/slicer-base:5.6` 이미지를 사용합니다.
- **Web UI (noVNC)**: 브라우저를 통해 3D Slicer 데스크탑 환경에 접속할 수 있습니다.
- **Python Scripting**: 컨테이너 내부의 Slicer Python 인터프리터를 사용하여 자동화가 가능합니다.
- **Gateway**: Nginx를 통해 `slicer.ai4infra.internal` 도메인으로 접근하며, WebSocket 통신을 지원합니다.

## 2. Installation

```bash
python scripts/ai4infra/ai4infra-cli.py install slicer
```

## 3. Configuration

### Environment Variables (`config/slicer.yml`)
- `SLICER_PORT`: 호스트에서 접속할 포트 (기본: 8085).
- `SLICER_MEM_LIMIT`: 컨테이너 메모리 제한 (기본: 4g).

## 4. Usage

### 🌐 Web Access
- **URL**: [http://slicer.ai4infra.internal](http://slicer.ai4infra.internal)
- 별도의 비밀번호 없이 즉시 Slicer 데스크탑 화면이 나타납니다.

### 🐍 Python Automation

Slicer 내부에서 파이썬 스크립트를 실행하는 방법:

**1. 컨테이너 내부에서 스크립트 실행**
```bash
sudo docker exec ai4infra-slicer Slicer --no-main-window --python-script /home/slicer/data/myscript.py
```

**2. Python 인터렉티브 셀**
```bash
sudo docker exec -it ai4infra-slicer Slicer --no-main-window --python-code "print(slicer.app.version)"
```

### 📁 Data Mapping
- 호스트의 `/opt/ai4infra/slicer/data` 폴더가 컨테이너의 `/home/slicer/data`에 마운트됩니다.
- 연구 데이터 및 파이썬 스크립트를 이 폴더에 넣고 작업하십시오.

## 5. Typical Workflow

1. **DICOM 데이터 준비**: `ai4infra-dcmtk`를 사용하여 `raw` 또는 `pseudo` PACS에서 데이터를 가져와 `slicer/data` 폴더에 공유합니다.
2. **자동화 스크립트 작성**: `slicer/data/process_dicom.py` 파일을 작성합니다.
3. **실행**: Headless 모드(`--no-main-window`)로 스크립트를 실행하여 대량의 데이터를 배치 처리합니다.
4. **결과 확인**: 브라우저로 접속하여 시각적으로 처리 결과를 검토합니다.
