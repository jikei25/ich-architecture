# Staging deployment

Four servers, one Docker Compose project each. No high availability, no Keycloak, no cloud backup, no GPU.

| Server | Directory | Services | Published ports |
|---|---|---|---|
| PACS | `pacs/` | dcm4chee-arc-light 5.35.2, OpenLDAP, OHIF Viewer (nginx) | 80 (HTTP), 11112 (DICOM), 2575 (HL7), 11113 (AI results) |
| Gateway | `gateway/` | Orthanc 26.9.1 (PostgreSQL index, S3 storage, DICOMweb) | 4242 (DICOM), 8042 (HTTP) |
| Database | `database/` | PostgreSQL 17: databases `pacsdb` and `orthanc` | 5432 |
| Storage | `storage/` | SeaweedFS 4.47: buckets `pacs`, `orthanc`, `research` | 8333 (S3) |

## Data directories

All persistent data lives under `DATA_ROOT` (default `/data/apps`), one directory per component:

| Server | Directory | Owner (uid:gid) |
|---|---|---|
| Database | `medical-ai-postgresql/data` | 999:999 |
| Storage | `medical-ai-seaweedfs/data` | 0:0 |
| PACS | `medical-ai-openldap/data`, `medical-ai-openldap/config` | 100:101 |
| PACS | `medical-ai-dcm4chee/wildfly`, `medical-ai-dcm4chee/storage` | 1023:1023 |
| Gateway | `medical-ai-orthanc/db` | 0:0 |

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

## Local test on one machine

Run the four projects on one host and let them reach each other through the Docker bridge:

```bash
sed -e 's/^\(PACS\|GATEWAY\|DATABASE\|STORAGE\)_HOST=.*/\1_HOST=host.docker.internal/' \
    -e "s|^DATA_ROOT=.*|DATA_ROOT=$HOME/medical-ai-staging-data|" \
    -e 's/^BIND_ADDRESS=.*/BIND_ADDRESS=172.17.0.1/' -e 's/^ARC_JAVA_HEAP=.*/ARC_JAVA_HEAP=1g/' \
    servers.env.example > servers.env
```

Then follow the installation steps above; the viewer is at `http://172.17.0.1/`, and the loader needs
`--add-host host.docker.internal:host-gateway --host host.docker.internal`.
