# Security Architecture & Deployment Strategy

> **목적**: 이 문서는 AI4INFRA 프로젝트가 제공하는 모든 인프라 서비스(Vault, DB 등)가 준수해야 할 최상위 보안 원칙과 타겟 운영 환경에 대한 전략을 정의합니다.

## 1. 보안 원칙 (Security Principles)

### 1.1 의료 정보 보호 (Medical Data Protection)
본 인프라는 추후 **의료 정보(민감 정보)**를 다루는 가명화 프로젝트 등의 기반이 되므로, 일반적인 IT 서비스보다 **더 높고 엄격한 보안 기준**을 적용합니다.

### 1.2 권한 분리 (Separation of Duties & Least Privilege)
시스템의 안전성을 위해 **설치(Installation)**와 **운영(Operation)**의 권한을 엄격히 분리합니다.

- **설치자 (Administrator)**:
    - **역할**: 시스템 초기 구축, Docker/WSL2 설치, 서비스 데몬 등록 등 시스템 레벨의 변경 권한을 가짐.
    - **권한**: Windows Administrator 권한 필요.
- **운영자/사용자 (Standard User)**:
    - **역할**: 구축된 서비스를 실행하고, 가명화 작업 등을 수행하는 실무자.
    - **권한**: **표준 사용자(Standard User)** 권한만으로 모든 기능을 불편 없이 사용할 수 있어야 함. (Sudo 등 관리자 권한 요구 금지)

---

## 2. 타겟 운영 환경 (Target Environment Strategy)

### 2.1 운영체제 (OS)
- **Target OS**: **Microsoft Windows**
    - **이유**: 병원 및 공공 기관의 PC 환경이 대부분 Windows 기반임.

### 2.2 실행 환경 (Execution Environment)
성능과 호환성을 고려하여 두 가지 트랙으로 개발을 진행하되, 우선순위는 다음과 같습니다.

- **Plan A (우선순위): WSL2 (Windows Subsystem for Linux 2)**
    - **장점**: Linux Native에 가까운 성능, Docker와의 완벽한 호환성, 개발 용이성.
    - **제약 사항**: DICOM 서버 연동 등 일부 로우레벨 네트워크 통신에서 호환성 문제 발생 가능성 있음.
- **Plan B (대안): Windows Native**
    - **조건**: 만약 WSL2 환경에서 필수적인 네트워크 통신(예: DICOM Protocol) 테스트가 실패하거나 불안정할 경우, Windows Native 환경으로 전환.

### 2.3 네트워크 환경 (Network Constraints)
- **폐쇄망 (Internet Air-gapped)**:
    - 운영 환경은 외부 인터넷 연결이 차단된 **폐쇄망**일 가능성이 매우 높음.
    - **영향**:
        - **오프라인 설치(Offline Installation)** 및 **USB 기반 물리적 키 관리** 전략이 필수.

---

## 3. 데이터 보호 및 백업 전략 (Data Protection & Backup Strategy)
서비스 안정성과 데이터 무결성을 위해 상황에 따라 두 가지 백업 방식을 혼용하여 운영합니다.

### 3.1 Cold Backup (정지 백업)
- **시점**: 초기 설치, 버전 업그레이드, 마이그레이션 등 시스템 변경 작업 전.
- **방식**: 서비스 컨테이너를 **완전히 중단(Stop)** 한 후, 데이터 볼륨 폴더 전체를 복사/압축.
- **장점**: 가장 확실한 데이터 정합성 보장.

### 3.2 Hot Backup (가동 중 백업)
- **시점**: 일일 자동 백업 등 서비스 운영 중.
- **방식**: 서비스가 제공하는 자체 백업 기능(예: Vault Raft Snapshot, Postgres pg_dump)을 사용하여 서비스 중단 없이 수행.
- **장점**: 서비스 가용성(Uptime) 유지.

### 3.3 Backup Isolation (백업 격리)
- **경로 원칙**: 백업 파일은 서비스 폴더(`BASE_DIR/<service>`) 내부가 아닌, **별도의 독립된 경로(`BASE_DIR/backup/<service>`)**에 저장합니다.
- **이유**: 서비스 오류로 인해 해당 서비스 폴더를 전체 삭제(rm -rf)하고 재설치하더라도, 백업 데이터가 함께 삭제되는 치명적인 사고를 방지하기 위함입니다.
