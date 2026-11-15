#!/bin/sh
# Applies staging.ldif.in on top of the default archive configuration. Idempotent: entries are added once
# (an "Already exists" error is expected on later runs) and every value that depends on the environment is
# set with "replace", so a changed address or key takes effect on the next run.
set -eu

BIND="-x -H ldap://ldap -D cn=admin,dc=dcm4che,dc=org -w $LDAP_ROOTPASS"
ARCHIVE_DEVICE="dicomDeviceName=dcm4chee-arc,cn=Devices,cn=DICOM Configuration,dc=dcm4che,dc=org"

until ldapsearch $BIND -b "$ARCHIVE_DEVICE" -s base dn >/dev/null 2>&1; do
  echo "waiting for the default archive configuration"
  sleep 2
done

accepted=""
for aet in $PACS_ACCEPTED_CALLING_AETS; do
  accepted="${accepted}dcmAcceptedCallingAETitle: $aet
"
done

ldif=/tmp/staging.ldif
umask 077
sed -e "s|@PACS_S3_ACCESS_KEY@|$PACS_S3_ACCESS_KEY|" \
    -e "s|@PACS_S3_SECRET_KEY@|$PACS_S3_SECRET_KEY|" \
    -e "s|@STORAGE_HOST@|$STORAGE_HOST|" \
    -e "s|@S3_PORT@|$S3_PORT|" \
    -e "s|@GATEWAY_HOST@|$GATEWAY_HOST|" \
    -e "s|@ORTHANC_DICOM_PORT@|$ORTHANC_DICOM_PORT|" \
    /setup/staging.ldif.in | awk -v accepted="$accepted" '$0 == "@ACCEPTED_CALLING_AETS@" {printf "%s", accepted; next} {print}' > "$ldif"

output=$(ldapmodify -c $BIND -f "$ldif" 2>&1 || true)
rm -f "$ldif"
added=$(echo "$output" | grep -c '^adding new entry' || true)
present=$(echo "$output" | grep -c 'Already exists (68)' || true)
modified=$(echo "$output" | grep -c '^modifying entry' || true)
echo "entries added: $((added - present)), already present: $present, modified: $modified"
failures=$(echo "$output" | grep -E '^ldap_(add|modify)' | grep -v 'Already exists (68)' || true)
if [ -n "$failures" ]; then
  echo "$output" | grep -E -A1 '^ldap_(add|modify)' | grep -v 'Already exists' >&2
  exit 1
fi

if wget -q -O /dev/null --post-data='' http://arc:8080/dcm4chee-arc/ctrl/reload 2>/dev/null; then
  echo "archive reloaded"
else
  echo "archive not running yet: it reads the configuration when it starts"
fi
