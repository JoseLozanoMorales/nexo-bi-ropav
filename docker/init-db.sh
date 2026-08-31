#!/bin/sh
set -eu
echo "Restaurando backup en $POSTGRES_DB..."
pg_restore --exit-on-error --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --no-owner --no-privileges /backup/ROPA_VACANA2-2.backup
echo "Backup restaurado en $POSTGRES_DB."
