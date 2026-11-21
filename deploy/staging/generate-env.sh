#!/usr/bin/env bash
# Writes the .env file of each server from servers.env and secrets.env.
# secrets.env is generated once and reused on every run, so the servers always share the same secrets.
# No secret value is printed.
set -euo pipefail
cd "$(dirname "$0")"

[ -f servers.env ] || { echo "servers.env is missing: copy servers.env.example and set the server addresses" >&2; exit 1; }

umask 077
if [ ! -f secrets.env ]; then
  secret() { openssl rand -hex 24; }
  {
    echo "PACS_DB_PASSWORD=$(secret)"
    echo "ORTHANC_DB_PASSWORD=$(secret)"
    echo "LDAP_ROOTPASS=$(secret)"
    echo "LDAP_CONFIGPASS=$(secret)"
    echo "PACS_S3_ACCESS_KEY=pacs$(openssl rand -hex 8)"
    echo "PACS_S3_SECRET_KEY=$(secret)"
    echo "GATEWAY_S3_ACCESS_KEY=gateway$(openssl rand -hex 8)"
    echo "GATEWAY_S3_SECRET_KEY=$(secret)"
    echo "ORTHANC_AI_PASSWORD=$(secret)"
  } > secrets.env
  echo "generated secrets.env (keep a protected copy: losing it locks the databases and buckets)"
fi

set -a
. ./servers.env
. ./secrets.env
set +a

write_env() {
  local server=$1
  shift
  for name in "$@"; do printf '%s="%s"\n' "$name" "${!name}"; done > "$server/.env"
  echo "wrote $server/.env"
}

COMMON=(DATA_ROOT BIND_ADDRESS)
write_env database "${COMMON[@]}" DB_PORT PACS_DB_PASSWORD ORTHANC_DB_PASSWORD
write_env storage "${COMMON[@]}" S3_PORT PACS_S3_ACCESS_KEY PACS_S3_SECRET_KEY GATEWAY_S3_ACCESS_KEY GATEWAY_S3_SECRET_KEY
write_env pacs "${COMMON[@]}" DATABASE_HOST STORAGE_HOST GATEWAY_HOST HTTP_PORT DICOM_PORT HL7_PORT AI_RESULTS_PORT \
  DB_PORT S3_PORT ORTHANC_DICOM_PORT PACS_ACCEPTED_CALLING_AETS ARC_JAVA_HEAP \
  PACS_DB_PASSWORD LDAP_ROOTPASS LDAP_CONFIGPASS PACS_S3_ACCESS_KEY PACS_S3_SECRET_KEY
write_env gateway "${COMMON[@]}" PACS_HOST DATABASE_HOST STORAGE_HOST AI_RESULTS_PORT DB_PORT S3_PORT \
  ORTHANC_DICOM_PORT ORTHANC_HTTP_PORT AI_SEGMENT_URL ORTHANC_DB_PASSWORD GATEWAY_S3_ACCESS_KEY GATEWAY_S3_SECRET_KEY ORTHANC_AI_PASSWORD
