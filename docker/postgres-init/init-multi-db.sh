#!/bin/bash
set -e

for database in "$CLAIMS_POSTGRES_DB" "$ORCHESTRATOR_POSTGRES_DB" "$LEGACY_POSTGRES_DB"; do
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" \
        --set=database="$database" <<-'EOSQL'
        SELECT 'CREATE DATABASE "' || :'database' || '"'
        WHERE NOT EXISTS (
            SELECT FROM pg_database WHERE datname = :'database'
        )\gexec
EOSQL
done
