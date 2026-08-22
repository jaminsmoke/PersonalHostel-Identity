#!/bin/sh
set -e

SERVICE="${SERVICE:-camareros}"

case "$SERVICE" in
  negocio)
    alembic -c alembic_negocio.ini upgrade head
    exec python -m app.serve
    ;;
  email-worker)
    exec python -m app.email_worker
    ;;
  *)
    alembic upgrade head
    exec python -m app.serve
    ;;
esac
