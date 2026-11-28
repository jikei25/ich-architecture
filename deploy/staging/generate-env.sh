#!/usr/bin/env bash
# Writes the .env file of each server from servers.env and secrets.env.
# secrets.env is generated once and reused on every run, so the servers always share the same secrets.
# No secret value is printed.
set -euo pipefail
cd "$(dirname "$0")"

[ -f servers.env ] || { echo "servers.env is missing: copy servers.env.example and set the server addresses" >&2; exit 1; }

umask 077
[ -f secrets.env ] || echo "generating secrets.env (keep a protected copy: losing it locks the databases and buckets)"
touch secrets.env
secret() { openssl rand -hex 24; }
# Adds a secret only when it is missing, so later additions never change the existing ones.
add_secret() { grep -q "^$1=" secrets.env || echo "$1=$2" >> secrets.env; }
add_secret PACS_DB_PASSWORD "$(secret)"
add_secret ORTHANC_DB_PASSWORD "$(secret)"
add_secret LDAP_ROOTPASS "$(secret)"
add_secret LDAP_CONFIGPASS "$(secret)"
add_secret PACS_S3_ACCESS_KEY "pacs$(openssl rand -hex 8)"
add_secret PACS_S3_SECRET_KEY "$(secret)"
add_secret GATEWAY_S3_ACCESS_KEY "gateway$(openssl rand -hex 8)"
add_secret GATEWAY_S3_SECRET_KEY "$(secret)"
add_secret ORTHANC_AI_PASSWORD "$(secret)"
add_secret RESEARCH_GATEWAY_PASSWORD "$(secret)"
add_secret RESEARCH_MONAI_PASSWORD "$(secret)"
add_secret DEID_KEY "$(openssl rand -hex 32)"

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
  ORTHANC_DICOM_PORT ORTHANC_HTTP_PORT AI_SEGMENT_URL ORTHANC_DB_PASSWORD GATEWAY_S3_ACCESS_KEY GATEWAY_S3_SECRET_KEY ORTHANC_AI_PASSWORD \
  RESEARCH_URL RESEARCH_GATEWAY_PASSWORD DEID_KEY
write_env research "${COMMON[@]}" RESEARCH_HTTP_PORT MONAI_RESEARCH_PORT RESEARCH_GATEWAY_PASSWORD RESEARCH_MONAI_PASSWORD
