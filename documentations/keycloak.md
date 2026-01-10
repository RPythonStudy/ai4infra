# Keycloak Service Guide

> **서비스명**: `ai4infra-keycloak`
> **역할**: 통합 인증 (IdP), SSO, 사용자 관리
> **URL**: `http://auth.ai4infra.internal`
> **계정**: `admin` / `.env`의 `KEYCLOAK_ADMIN_PASSWORD` (기본: `admin`)

## 1. Overview
Keycloak은 `ai4infra` 프로젝트의 **중앙 인증 서버(Identity Provider)**입니다.
OpenID Connect(OIDC) 및 SAML 2.0을 지원하며, **OpenLDAP**과 연동하여 사용자 정보를 동기화하고, **Kibana**, **Vaultwarden** 등 다른 서비스에 SSO(Single Sign-On)를 제공합니다.

## 2. Architecture
- **Proxy**: Nginx (`auth.ai4infra.internal`) -> Keycloak (`8080`)
  - `KC_PROXY=edge`: TLS Termination은 Nginx가 담당하고 내부 통신은 HTTP를 사용.
- **Database**: PostgreSQL (`ai4infra-postgres`)의 `keycloak` 데이터베이스 사용.
- **Cluster**: 현재는 단일 인스턴스이지만, Infinispan 분산 캐시가 내장되어 있어 향후 클러스터링 가능.

## 3. Installation & Operation

### 설치
```bash
make install-keycloak
```
> **Process**:
> 1. `ai4infra-cli.py`가 Postgres DB 접속 -> `keycloak` DB & User 자동 생성.
> 2. Keycloak 컨테이너 구동.
> 3. Nginx 재시작 (라우팅 적용).

### 환경 변수 (.env)
- `KEYCLOAK_ADMIN`: 초기 관리자 ID
- `KEYCLOAK_ADMIN_PASSWORD`: 초기 관리자 비밀번호
- `KEYCLOAK_DB_PASSWORD`: DB 접속 비밀번호 (Postgres 초기화 시에도 사용됨)
- `compose_vars`: 포트(`8080`), 메모리(`1g`) 설정 등은 `config/keycloak.yml` 참조.

## 4. Configuration Steps (Post-Install)

### A. Realm 생성
1. 관리자 콘솔 로그인 (`http://auth.ai4infra.internal`).
2. 좌측 상단 `Master` -> `Create Realm` -> `ai4infra` 생성.
   - **권장**: Master Realm은 관리용으로만 사용하고, 실제 서비스는 별도 Realm(`ai4infra`)에서 운영.

### B. User Federation (OpenLDAP 연동)
OpenLDAP에 저장된 사용자를 Keycloak에서도 로그인할 수 있게 설정합니다.

1. **User Federation** 메뉴 이동 -> `Add provider` -> `ldap` 선택.
2. **Settings**:
   - **Console Display Name**: `openldap`
   - **Vendor**: `Other`
   - **Connection URL**: `ldap://ai4infra-openldap:389`
   - **Bind Type**: `simple`
   - **Bind DN**: `cn=admin,dc=ai4infra,dc=net`
   - **Bind Credential**: `.env`의 `LDAP_ADMIN_PASSWORD`
   - **Users DN**: `ou=people,dc=ai4infra,dc=net`
   - **Username LDAP attribute**: `uid`
   - **RDN LDAP attribute**: `uid`
   - **UUID LDAP attribute**: `entryUUID`
   - **User Object Classes**: `inetOrgPerson, organizationalPerson`
3. **Synchronize Settings**:
   - `On`으로 설정하여 주기적 동기화.
4. **Test Connection** 및 **Test Authentication** 클릭하여 성공 확인.

### C. Client 생성 (SSO 대상 서비스)
예: Kibana SSO
1. **Clients** -> `Create client`.
2. **Client ID**: `kibana`
3. **Capability config**: `Client authentication`=On.
4. **Login settings**:
   - **Valid redirect URIs**: `http://kibana.ai4infra.internal/*`
   - **Web origins**: `+`

## 5. Troubleshooting
- **502 Bad Gateway**: Keycloak 부팅 중(1~2분 소요)이거나, 컨테이너가 죽었을 때.
- **DB Connection Fail**:
  - `KEYCLOAK_DB_PASSWORD` 환경변수가 올바르게 주입되었는지 확인 (`docker inspect ai4infra-keycloak`).
  - `.env`에 값이 있는지 확인.
- **Login Loop (HTTPS Issue)**:
  - 브라우저 쿠키 삭제.
  - `KC_PROXY=edge` 및 Nginx의 `X-Forwarded-Proto` 헤더 설정 확인.
