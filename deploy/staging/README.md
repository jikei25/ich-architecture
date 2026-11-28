# Staging deployment

Five servers, one Docker Compose project each. No high availability, no Keycloak, no cloud backup, no GPU.

| Server | Directory | Services | Published ports |
|---|---|---|---|
| PACS | `pacs/` | dcm4chee-arc-light 5.35.2, OpenLDAP, OHIF Viewer (nginx) | 80 (HTTP), 11112 (DICOM), 2575 (HL7), 11113 (AI results) |
| Gateway | `gateway/` | Orthanc 26.9.1 (PostgreSQL index, S3 storage, DICOMweb), MONAI Label inference server (`hemorrhage_approved`) | 4242 (DICOM), 8042 (HTTP) |
| Database | `database/` | PostgreSQL 17: databases `pacsdb` and `orthanc` | 5432 |
| Storage | `storage/` | SeaweedFS 4.47: buckets `pacs`, `orthanc`, `research` | 8333 (S3) |
| Research | `research/` | Research Orthanc (de-identified CT, every label version), MONAI Label research server (`hemorrhage_dev`) | 8043 (HTTP), 8000 (MONAI Label) |

## Data directories

All persistent data lives under `DATA_ROOT` (default `/data/apps`), one directory per component:

| Server | Directory | Owner (uid:gid) |
|---|---|---|
| Database | `medical-ai-postgresql/data` | 999:999 |
| Storage | `medical-ai-seaweedfs/data` | 0:0 |
| PACS | `medical-ai-openldap/data`, `medical-ai-openldap/config` | 100:101 |
| PACS | `medical-ai-dcm4chee/wildfly`, `medical-ai-dcm4chee/storage` | 1023:1023 |
| Gateway | `medical-ai-orthanc/db`, `medical-ai-registry` | 0:0 |
| Research | `medical-ai-research/{orthanc,monai-cache,models,datasets}`, `medical-ai-registry` | 0:0 |

No Docker named volume is used, so `docker compose down -v` never deletes data. Deleting data requires removing these directories explicitly.

## First installation

On the administration machine, inside this directory:

```bash
cp servers.env.example servers.env    # set the four server addresses, DATA_ROOT, ports
./generate-env.sh                     # creates secrets.env once, then <server>/.env for each server
```

`secrets.env` holds every password and key, shared by the four servers. Keep a protected copy: a new
`secrets.env` no longer matches the existing databases and buckets. The script never prints secret values.

Copy this directory (with the generated `.env` files) to each server, then on each server, in this order:

```bash
./init-dirs.sh database && (cd database && docker compose up -d)
./init-dirs.sh storage  && (cd storage  && docker compose up -d)
./init-dirs.sh pacs     && (cd pacs     && docker compose up -d)
./init-dirs.sh gateway  && (cd gateway  && docker compose up -d)
./init-dirs.sh research && (cd research && docker compose up -d)
```

Each server only needs its own sub-directory, `init-dirs.sh` and its `.env`.

## Re-running

Every step can be run again without damage:

- `generate-env.sh` reuses `secrets.env` and only rewrites the `.env` files (for example after an address change).
- `init-dirs.sh` keeps existing directories and their content, and resets owner and mode.
- `docker compose up -d` re-runs the one-shot setup service of the server:
  - `postgresql-setup` creates or updates the `orthanc` role and database, and restricts each database to its own role.
  - `seaweedfs-setup` creates only the missing buckets.
  - `ldap-setup` applies `pacs/ldap/staging.ldif.in`: entries are added once, and values that depend on `.env` are replaced, then the running archive reloads its configuration.

## Configuration applied to the archive

`pacs/ldap/staging.ldif.in`, on top of the default dcm4chee configuration:

1. Image files go to the bucket `pacs` on the storage server.
2. AE `DCM4CHEE` accepts only the calling AE titles in `PACS_ACCEPTED_CALLING_AETS`.
3. Every CT series is exported to the Orthanc gateway (AE `ORTHANC`) 10 seconds after its last instance; export tasks are polled every 5 seconds.
4. AE `AI_RESULTS` on port 11113 accepts only calling AE `ORTHANC`, and only Secondary Capture, Segmentation and Comprehensive SR objects.

## Network

Docker publishes ports through its own iptables rules, which bypass UFW. Restrict access with `BIND_ADDRESS`
and with rules in the `DOCKER-USER` chain. The gateway must not reach PACS ports 11112 and 80; it reaches the
PACS only on port 11113.

## Loading a NIfTI dataset

`tools/` converts NIfTI head CT volumes into DICOM CT series with synthetic patient data and stores them to
the PACS as AE `DATASET_LOADER`. UIDs are derived from the file name, so loading a file again overwrites the
same instances instead of creating a new study.

```bash
docker build -t medical-ai-staging-tools tools
docker run --rm -v /path/to/ct_scans:/ct:ro medical-ai-staging-tools --host <PACS_HOST> /ct/049.nii /ct/066.nii
```

Viewer: `http://<PACS_HOST>/`. Archive UI: `http://<PACS_HOST>/dcm4chee-arc/ui2`.

## AI bridge (gateway plugin)

`gateway/plugin/ai_bridge.py` runs inside Orthanc when `AI_SEGMENT_URL` is set. For each CT series that
becomes stable (no new slice for `STABLE_AGE` seconds), the plugin:

1. converts the series to one NIfTI volume (int16 HU, RAS affine) with `nifti_bridge.series_to_nifti`;
2. posts it to `AI_SEGMENT_URL` (MONAI Label `/infer/hemorrhage_approved`, multipart field `file`) and
   receives a gzip NIfTI mask on the same grid, whose header names the model version;
3. rejects a mask whose shape or affine differs from the volume, then builds a DICOM SEG that references
   every source slice (UIDs derived from the source series and the model version, so a rerun of the same
   version replaces the previous result);
4. stores the SEG in Orthanc and sends it to the PACS AE `AI_RESULTS`, where the viewer overlays it;
5. when `RESEARCH_URL` is set, de-identifies the series with Orthanc (basic profile, UIDs and patient ID
   replaced by a keyed hash with `DEID_KEY`), builds the same mask as a SEG on the copy, and stores both on
   the research Orthanc with the SEG labelled `draft`.

Self-checks of the conversion (run after any change to `nifti_bridge.py`):

```bash
docker compose -f gateway/docker-compose.yml build
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v "$PWD:/staging" --entrypoint python3 \
  medical-ai/orthanc-ai:26.9.1 /staging/gateway/plugin/test_nifti_bridge.py
```

`tools/mock_ai.py` stands in for the AI service with the same API: it answers with the CT-ICH ground-truth
mask of the received volume, matched by voxel content, so a correct overlay confirms the geometry end to end.

```bash
docker run -d --name medical-ai-mock-ai -p 8000:8000 -v /path/to/CT-ICH-PhysioNet:/data:ro \
  --entrypoint python medical-ai-staging-tools /usr/local/bin/mock_ai.py --dataset /data
# servers.env: AI_SEGMENT_URL=http://<host of the mock>:8000/infer/hemorrhage_approved, then ./generate-env.sh and recreate the gateway
```

## MONAI Label, label store and registry

One app (`monai/app`) runs as two servers that differ only in `--conf models`:

- the inference server (gateway project) runs `hemorrhage_approved`, the version named in
  `medical-ai-registry/hemorrhage/approved`. Its datastore is an empty folder: each volume arrives in the
  request and its temporary file is deleted after the response.
- the research server (research project) runs `hemorrhage_dev` for 3D Slicer (MONAILabel extension) and
  training. Its datastore is the research Orthanc over DICOMweb; `/cache` holds downloaded copies only.

The research Orthanc is the label store. Each SEG series has one Orthanc label for its status: `draft` (AI
result, opened by Slicer as the image's original label), `unreviewed` (a save from MONAI Label, author in
the request params) or `reviewed`. Training copies the newest reviewed label of each CT into
`medical-ai-research/datasets/<dataset>` with a manifest, trains, and publishes a `candidate` version to the
registry. A version reaches patients only after approval; the inference server reloads it without restart.

```bash
# seed the label store with CT-ICH ground truth as reviewed labels, keeping three cases for the clinical path
RESEARCH_PASSWORD=... docker run --rm --network host -e RESEARCH_USER=gateway -e RESEARCH_PASSWORD \
  -v "$PWD/tools:/tools:ro" -v "$PWD/gateway/plugin:/plugin:ro" -v /path/to/CT-ICH-PhysioNet:/data:ro \
  --entrypoint python medical-ai/monai-label:0.8.8 /tools/seed_research.py --orthanc http://<RESEARCH_HOST>:8043 \
  --dataset /data --exclude 054 070 078
# train: POST http://<RESEARCH_HOST>:8000/train/hemorrhage_dev (params: max_epochs, device, ...)
docker compose -f research/docker-compose.yml exec monai python /app/lib/research.py list       # label versions
docker compose -f research/docker-compose.yml exec monai python /app/lib/research.py review <SEG UID>
docker compose -f research/docker-compose.yml exec monai python /app/lib/registry.py approve v1
```

Self-checks of the app (the mask keeps the input grid; the registry serves only the approved version):

```bash
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v "$PWD/monai/test_app.py:/test_app.py:ro" --entrypoint python \
  medical-ai/monai-label:0.8.8 /test_app.py
```

## Local test on one machine

Run the five projects on one host and let them reach each other through the Docker bridge:

```bash
sed -e 's/^\(PACS\|GATEWAY\|DATABASE\|STORAGE\|RESEARCH\)_HOST=.*/\1_HOST=host.docker.internal/' \
    -e "s|^DATA_ROOT=.*|DATA_ROOT=$HOME/medical-ai-staging-data|" \
    -e 's/^BIND_ADDRESS=.*/BIND_ADDRESS=172.17.0.1/' -e 's/^ARC_JAVA_HEAP=.*/ARC_JAVA_HEAP=1g/' \
    -e 's|^RESEARCH_URL=.*|RESEARCH_URL=http://host.docker.internal:8043|' \
    servers.env.example > servers.env
```

Then follow the installation steps above; the viewer is at `http://172.17.0.1/`, and the loader needs
`--add-host host.docker.internal:host-gateway --host host.docker.internal`.
