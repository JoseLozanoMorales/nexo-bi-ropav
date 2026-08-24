#!/bin/sh
set -eu
echo "Restaurando backup RopaV..."
pg_restore --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --no-owner --no-privileges /backup/RopaVacanaV2.sql
echo "Backup RopaV restaurado."
