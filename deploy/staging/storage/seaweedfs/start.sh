#!/bin/sh
# Builds the S3 identity file from the environment at each start, so no key is written to the data directory.
# The PACS uses bucket pacs; the gateway uses buckets orthanc and research. Anonymous requests are refused.
set -e
umask 077
cat > /tmp/s3.json <<JSON
{
  "identities": [
    {"name": "pacs",
     "credentials": [{"accessKey": "$PACS_S3_ACCESS_KEY", "secretKey": "$PACS_S3_SECRET_KEY"}],
     "actions": ["Read:pacs", "List:pacs", "Write:pacs", "Tagging:pacs"]},
    {"name": "gateway",
     "credentials": [{"accessKey": "$GATEWAY_S3_ACCESS_KEY", "secretKey": "$GATEWAY_S3_SECRET_KEY"}],
     "actions": ["Read:orthanc", "List:orthanc", "Write:orthanc", "Tagging:orthanc",
                 "Read:research", "List:research", "Write:research"]}
  ]
}
JSON
# volume.max=0 sizes the number of 1 GB volumes from the free space of /data.
exec weed server -dir=/data -ip.bind=0.0.0.0 -master.volumeSizeLimitMB=1024 -volume.max=0 \
  -s3 -s3.port=8333 -s3.config=/tmp/s3.json
