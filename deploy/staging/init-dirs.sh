#!/usr/bin/env bash
# Creates the data directories of one server with the owner each container runs as.
# Safe to run repeatedly: existing directories and their content are kept.
# Usage: ./init-dirs.sh pacs|gateway|database|storage
set -euo pipefail
cd "$(dirname "$0")"

server=${1:-}
case "$server" in
  database) dirs=("medical-ai-postgresql/data:999:999:700") ;;
  storage)  dirs=("medical-ai-seaweedfs/data:0:0:750") ;;
  pacs)     dirs=("medical-ai-openldap/data:100:101:700" "medical-ai-openldap/config:100:101:700"
                  "medical-ai-dcm4chee/wildfly:1023:1023:750" "medical-ai-dcm4chee/storage:1023:1023:750") ;;
  gateway)  dirs=("medical-ai-orthanc/db:0:0:750") ;;
  *) echo "usage: $0 pacs|gateway|database|storage" >&2; exit 1 ;;
esac

[ -f "$server/.env" ] || { echo "$server/.env is missing: run ./generate-env.sh first" >&2; exit 1; }
data_root=$(sed -n 's/^DATA_ROOT="\(.*\)"$/\1/p' "$server/.env")
[ -n "$data_root" ] || { echo "DATA_ROOT is not set in $server/.env" >&2; exit 1; }

# A throwaway container creates the directories (Docker creates DATA_ROOT itself), so no sudo is needed.
script=""
for entry in "${dirs[@]}"; do
  IFS=: read -r path uid gid mode <<< "$entry"
  script+="mkdir -p /root-dir/$path && chown $uid:$gid /root-dir/$path && chmod $mode /root-dir/$path && echo $data_root/$path; "
done
docker run --rm -v "$data_root:/root-dir" alpine:3.22 sh -c "$script"
