#!/bin/sh
set -e

SERVICE="${SERVICE:-camareros}"

case "$SERVICE" in
  negocio)
    alembic -c alembic_negocio.ini upgrade head
    exec uvicorn app.main_negocio:app --host 0.0.0.0 --port 8080
    ;;
  email-worker)
    exec python -m app.email_worker
    ;;
  *)
    alembic upgrade head
    exec uvicorn app.main:app --host 0.0.0.0 --port 8080
    ;;
esac
