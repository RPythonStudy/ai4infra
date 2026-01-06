# Vaultwarden Service Guide

> **목적**: AI4INFRA 프로젝트 운영진 및 개발자들이 사용하는 **비밀번호 및 공용 자격 증명(Credential)** 을 안전하게 관리하고 공유하기 위한 패스워드 매니저 서비스입니다.

## 1. 선정 배경 (Rationale for Selection)
본 프로젝트는 초기 비트워든(Bitwarden) 공식 서버 도입을 고려하였으나, 다음과 같은 이유로 **Vaultwarden**을 최종 채택하였습니다.

1.  **표준 준수 (Standard Compliance)**:
    - 공식 Bitwarden은 전용 설치 스크립트(`bitwarden.sh`)와 복잡한 구조를 강제하여, 본 프로젝트의 디렉토리 표준(`BASE_DIR/service`)과 `docker-compose` 단일 템플릿 정책을 적용하기 어려움.
    - **Vaultwarden**은 단일 Docker 이미지로 구동되며 표준 `docker-compose.yml` 구성이 가능하여, **별도의 예외 처리 없이** 프로젝트 표준을 100% 준수할 수 있음.
2.  **경량화 (Lightweight)**: 병원/폐쇄망 등 리소스가 제한된 환경에서도 최소한의 메모리(~60MB)로 원활하게 동작.
3.  **호환성 (Compatibility)**: 공식 Bitwarden 클라이언트(Web, App, Browser Extension)와 완벽 호환.

## 2. 서비스 아키텍처
- **Image**: `vaultwarden/server` (Rust implementation)
- **Database**: `PostgreSQL` (프로젝트 공용 DB 또는 전용 DB 사용 가능, 현재 SQLite/Postgres 선택 가능)
- **Port**: `80` (Internal), Reverse Proxy를 통해 SSL 적용 필수.

## 3. 데이터 및 백업 정책
본 서비스는 `documentations/security-architecture.md`의 데이터 보호 정책을 따릅니다.

- **Data Path**: `BASE_DIR/vaultwarden/data` (코드 레벨 고정)
- **Backup Path**: `BASE_DIR/backup/vaultwarden` (격리 보관)
- **Backup Strategy**: Cold Backup (초기/점검 시) 및 Hot Backup (운영 시, DB Dump or SQLite Backup).
