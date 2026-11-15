-- Idempotent: safe to run on every start.
SELECT format('CREATE ROLE orthanc LOGIN PASSWORD %L', :'orthanc_pw')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'orthanc') \gexec
ALTER ROLE orthanc WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'orthanc_pw';

SELECT 'CREATE DATABASE orthanc OWNER orthanc'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'orthanc') \gexec

REVOKE CONNECT ON DATABASE pacsdb FROM PUBLIC;
REVOKE CONNECT ON DATABASE orthanc FROM PUBLIC;
GRANT CONNECT ON DATABASE orthanc TO orthanc;
