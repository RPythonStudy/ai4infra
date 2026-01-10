#!/bin/bash
set -e

# Configuration Injection via Helper Script
# Since the official image might lack 'envsubst', we use 'sed' for substitution.
# The template config is mounted at /etc/orthanc/orthanc.json (Read-Only).

CONFIG_FILE="/tmp/orthanc.json"

echo "[Entrypoint] DB Pass len: ${#ORTHANC_DB_PASSWORD}"
echo "[Entrypoint] Admin Pass len: ${#ORTHANC_ADMIN_PASSWORD}"

echo "[Entrypoint] Preparing Orthanc configuration..."
cp /etc/orthanc/orthanc.json "$CONFIG_FILE"

# Substitute Secrets
# Using | delimiter to avoid issues with specialized characters if any (though passwords should be simple)
sed -i "s|\${ORTHANC_ADMIN_PASSWORD}|$ORTHANC_ADMIN_PASSWORD|g" "$CONFIG_FILE"
sed -i "s|\${ORTHANC_DB_PASSWORD}|$ORTHANC_DB_PASSWORD|g" "$CONFIG_FILE"
sed -i "s|\${ORTHANC_AET}|$ORTHANC_AET|g" "$CONFIG_FILE"
sed -i "s|__DB_NAME__|$ORTHANC_DB_NAME|g" "$CONFIG_FILE"

echo "[Entrypoint] Secrets injected."
echo "[Entrypoint] DB NAME: $ORTHANC_DB_NAME"

# Debug: Show PostgreSQL config
echo "[Entrypoint] PostgreSQL Database setting:"
grep -A 8 '"PostgreSQL"' "$CONFIG_FILE"

# Execute Orthanc
echo "[Entrypoint] Starting Orthanc..."
exec Orthanc "$CONFIG_FILE"
