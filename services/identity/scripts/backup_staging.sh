#!/bin/bash
# Entrada estable para cron y deploy. La implementación comprobable vive en Python.
set -euo pipefail
umask 077

cd /opt/identity || exit 1
exec python3 services/identity/scripts/backup_restore.py backup
