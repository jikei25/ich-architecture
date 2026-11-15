#!/bin/sh
set -e
shell() { echo "$1" | weed shell -master=seaweedfs:9333 -filer=seaweedfs:8888 2>/dev/null; }

until shell "s3.bucket.list" >/dev/null; do sleep 2; done
existing=$(shell "s3.bucket.list")
for bucket in pacs orthanc research; do
  if echo "$existing" | grep -qw "$bucket"; then
    echo "bucket $bucket exists"
  else
    shell "s3.bucket.create -name $bucket" >/dev/null
    echo "bucket $bucket created"
  fi
done
