# OpenLDAP Service Guide

> **OpenLDAP**은 조직의 사용자, 컴퓨터, 정책 정보를 중앙에서 관리하는 **디렉토리 서비스(Directory Service)**입니다.
> AI4INFRA 프로젝트에서는 모든 서비스의 **통합 계정 저장소(Identity Provider)**로 사용됩니다.

## 1. Architecture

### 1.1 Service Layout
*   **Service Name**: `openldap` / `phpldapadmin`
*   **Container Names**: 
    *   `ai4infra-ldap`: 실제 데이터가 저장되는 LDAP 서버.
    *   `ai4infra-ldap-admin`: 웹 기반 관리 도구 (phpLDAPadmin).
*   **Images**:
    *   `osixia/openldap:1.5.0`
    *   `osixia/phpldapadmin:0.9.0`
*   **Internal Ports**: 
    *   LDAP: 389 (Plain/StartTLS), 636 (LDAPS)
    *   Admin: Nginx Proxy Only (No direct exposure)
*   **External Access**: 
    *   LDAP Client: `ldap.ai4infra.internal:389`
    *   Web Admin: `http://ldap-admin.ai4infra.internal`

### 1.2 Data Storage
*   **Backend**: MDB (Memory-Mapped Database)
*   **Data Volume**: `/opt/ai4infra/ldap/data` (LDAP 데이터베이스)
*   **Config Volume**: `/opt/ai4infra/ldap/config` (`cn=config` 설정)

## 2. Configuration Strategy

### 2.1 Configuration Files
*   **`config/ldap.yml`**: 서비스 활성화 및 조직 도메인 정보.
    *   `LDAP_ORGANISATION`: "AI4INFRA"
    *   `LDAP_DOMAIN`: "ai4infra.internal"
*   **`.env` Access**:
    *   `LDAP_ADMIN_PASSWORD`: 관리자 비밀번호 (초기 설치 시 적용).
    *   `LDAP_CONFIG_PASSWORD`: 서버 설정 변경용 비밀번호.

### 2.2 Nginx Integration (Admin Tool)
*   **Domain**: `ldap-admin.ai4infra.internal`
*   **Security**: 내부망(Intranet)에서만 접근 가능한 관리자 도구.

## 3. Operations

### 3.1 Installation
```bash
# 1. 설치 (LDAP + Admin)
make install-ldap

# 2. Nginx 반영 (Web Admin 라우팅)
make install-nginx
sudo docker restart ai4infra-nginx
```

### 3.2 Administrative Access (Web)
*   **URL**: `http://ldap-admin.ai4infra.internal`
*   **Login DN**: `cn=admin,dc=ai4infra,dc=internal`
*   **Password**: `.env`의 `LDAP_ADMIN_PASSWORD` 값 (기본: `admin`)

### 3.3 Adding Users
1.  phpLDAPadmin 로그인.
2.  `dc=ai4infra,dc=internal` -> `Create a child entry`.
3.  `Generic: User Account` 또는 `Posix Group` 선택하여 생성.
4.  생성된 계정은 향후 Jenkins, Grafana, VPN 등의 로그인에 사용됨.
