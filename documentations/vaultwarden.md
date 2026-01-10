# Vaultwarden Service Guide

> **Vaultwarden**은 Bitwarden의 경량화된 오픈소스 서버 구현체입니다.
> AI4INFRA 프로젝트에서는 팀원 간의 **보안 자격 증명(Password, API Key) 공유** 및 관리를 위해 사용합니다.

## 1. Architecture

### 1.1 Service Layout
*   **Service Name**: `vaultwarden`
*   **Container Name**: `ai4infra-vaultwarden`
*   **Image**: `vaultwarden/server:1.32.0-alpine` (Pinned Version)
*   **Internal Port**: `80`
*   **External Access**: Nginx (`vaultwarden.ai4infra.internal`)를 통해서만 접근.

### 1.2 Data Storage
*   **Database**: `ai4infra-postgres` (PostgreSQL) 사용.
    *   **DB Name**: `vaultwarden`
    *   **User**: `postgres` (공통)
    *   **Reason**: SQLite(기본값)는 파일 락 이슈 등으로 동시성 처리에 한계가 있어, 안정적인 Postgres를 백엔드로 사용합니다.
*   **Data Volume**: `/opt/ai4infra/vaultwarden/data` (첨부파일, 아이콘 캐시 등 저장)

## 2. Configuration Strategy

### 2.1 Configuration Files
*   **`config/vaultwarden.yml`**: 서비스 활성화 여부 및 백업 정책.
    *   `enable: true`
    *   `backup.schedule`: DB 백업은 Postgres에서 통합 관리하므로, 여기서는 파일 데이터(Data Volume) 백업만 고려하면 됩니다.
*   **`templates/vaultwarden/docker-compose.yml`**:
    *   **Paths**: 데이터 경로는 `/opt/ai4infra/vaultwarden/data`로 하드코딩 (Convention).
    *   **Database**: `DATABASE_URL` 환경변수를 통해 Postgres 연결.

### 2.2 Nginx Integration
*   **Domain**: `vaultwarden.ai4infra.internal`
*   **Protocol**: HTTP (Nginx -> Vaultwarden). Vaultwarden 자체는 평문으로 통신하지만, Nginx가 HTTPS Termination을 수행해야 합니다.
*   **WebSockets**: 알림 동기화를 위해 WebSocket 지원 설정(`Upgrade`, `Connection` 헤더) 필수.

## 3. Operations

### 3.1 Installation
```bash
# 1. DB 생성 (최초 1회)
sudo docker exec -i ai4infra-postgres psql -U postgres -c "CREATE DATABASE vaultwarden;"

# 2. 서비스 설치
make install-vaultwarden

# 3. Nginx 반영
make install-nginx
sudo docker restart ai4infra-nginx
```

### 3.2 Troubleshooting
*   **502 Bad Gateway**: Nginx가 Vaultwarden 컨테이너를 찾지 못함. 컨테이너 상태(`make status`) 확인.
*   **DB Connection Fail**: Postgres 비밀번호 불일치. `docker logs ai4infra-vaultwarden` 확인 후 `config/vaultwarden.yml` 비밀번호 수정.
