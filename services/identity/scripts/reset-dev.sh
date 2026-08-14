#!/bin/sh
# Resetea los datos de desarrollo de Identity:
#   - TRUNCATE de las dos BD nuevas (identity_camareros, identity_negocio).
#   - DROP de la BD legacy `identity` (huérfana tras el split en dos servicios).
#
# Uso (desde cualquier sitio, no requiere psql local):
#   sh services/identity/scripts/reset-dev.sh

set -e

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)
cd "$REPO_ROOT"

USER="${POSTGRES_USER:-hosteleria}"

echo "> Truncando identity_camareros ..."
docker compose exec -T db psql -U "$USER" -d identity_camareros \
  -c "TRUNCATE camareros, credenciales CASCADE;"

echo "> Truncando identity_negocio ..."
docker compose exec -T db psql -U "$USER" -d identity_negocio \
  -c "TRUNCATE cuentas_negocio, establecimientos, layouts_establecimiento, membresias, invitaciones, email_outbox CASCADE;"

echo "> Borrando BD legacy 'identity' si existe ..."
docker compose exec -T db psql -U "$USER" -d postgres \
  -c "DROP DATABASE IF EXISTS identity;"

echo "Reset de desarrollo completado."
