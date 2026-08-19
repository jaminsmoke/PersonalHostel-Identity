#!/usr/bin/env bash
# Gestiona el stack de observabilidad apilando SIEMPRE los 3 compose del VPS.
#
# Uso (desde la raíz del checkout, en el VPS /opt/identity):
#   bash services/identity/scripts/obs_up.sh
#   bash services/identity/scripts/obs_up.sh up
#   bash services/identity/scripts/obs_up.sh up prometheus node-exporter
#   bash services/identity/scripts/obs_up.sh ps
#   bash services/identity/scripts/obs_up.sh stop
#
# Anti-orphan: NUNCA ejecutes `docker compose down` (ni prune de "orphans")
# sin incluir `-f docker-compose.observability.yml` o este wrapper. Si el
# compose activo solo conoce docker-compose.yml + docker-compose.prod.yml,
# Docker marca prometheus/grafana/loki/... como huérfanos y un down los borra
# (los volúmenes *-data se conservan si no pasas -v).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

COMPOSE=(
  docker compose
  -f docker-compose.yml
  -f docker-compose.prod.yml
  -f docker-compose.observability.yml
)

OBS_SERVICES=(
  prometheus
  alertmanager
  grafana
  loki
  alloy
  node-exporter
  postgres-exporter
)

cmd="${1:-up}"
if [ "$#" -gt 0 ]; then
  shift
fi

case "$cmd" in
  up)
    if [ "$#" -eq 0 ]; then
      "${COMPOSE[@]}" up -d "${OBS_SERVICES[@]}"
    else
      "${COMPOSE[@]}" up -d "$@"
    fi
    ;;
  ps | stop | restart | logs | config | pull)
    "${COMPOSE[@]}" "$cmd" "$@"
    ;;
  down)
    echo "AVISO: down del project completo (core + observabilidad)." >&2
    echo "Para solo parar obs: bash services/identity/scripts/obs_up.sh stop" >&2
    "${COMPOSE[@]}" down "$@"
    ;;
  *)
    echo "Uso: $0 [up|ps|stop|restart|logs|config|pull|down] [args...]" >&2
    exit 2
    ;;
esac
