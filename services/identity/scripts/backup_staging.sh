#!/bin/sh
# Backup de las dos BD de Identity en el VPS de staging.
# Se ejecuta desde cron (diario). Debe correr en /opt/identity.
set -eu

cd /opt/identity || exit 1
mkdir -p backups

PGUSER=$(grep -E '^POSTGRES_USER=' .env | cut -d= -f2- | tr -d '\r')
PGUSER=${PGUSER:-hosteleria}

TS=$(date -u +%Y%m%d-%H%M%S)
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

$COMPOSE exec -T db pg_dump -U "$PGUSER" identity_camareros | gzip > "backups/camareros-$TS.sql.gz"
$COMPOSE exec -T db pg_dump -U "$PGUSER" identity_negocio | gzip > "backups/negocio-$TS.sql.gz"

# Retención: 7 días
find backups -name '*.sql.gz' -mtime +7 -delete

echo "Backup OK: $TS"
