#!/bin/bash
set -e

# .env에서 KEYCLOAK_DB_PASSWORD를 주입받지 못한 경우 기본값 사용 (보안상 주의)
KC_PASS=${KEYCLOAK_DB_PASSWORD:-keycloak}

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER keycloak WITH PASSWORD '$KC_PASS';
    CREATE DATABASE keycloak;
    GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak;
    -- Keycloak needs schema creation privileges
    ALTER DATABASE keycloak OWNER TO keycloak;
EOSQL
