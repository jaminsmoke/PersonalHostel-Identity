#!/bin/bash
# Entrada estable para cron y deploy. La implementación comprobable vive en Python.
set -euo pipefail
umask 077
# No generar __pycache__ root en el checkout (rompe ruff format --check del runner aislado).
export PYTHONDONTWRITEBYTECODE=1

cd /opt/identity || exit 1
python3 services/identity/scripts/backup_restore.py backup
python3 services/identity/scripts/offsite_backup.py publish-metrics

if grep -q '^OFFSITE_BACKUP_ENABLED=true$' .env; then
    python3 services/identity/scripts/offsite_backup.py upload
fi
