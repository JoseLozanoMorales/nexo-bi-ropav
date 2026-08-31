#!/bin/sh
set -eu
echo "Restaurando backup RopaV..."
pg_restore --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --no-owner --no-privileges /backup/ROPA_VACANA2.backup
echo "Backup RopaV restaurado."
