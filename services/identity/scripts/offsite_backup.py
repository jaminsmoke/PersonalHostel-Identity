#!/usr/bin/env python3
"""Replica conjuntos integrales a un repositorio restic cifrado en Cloudflare R2."""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

try:
    from scripts.backup_restore import BACKUP_ROOT, BackupError, latest_set, verify_manifest
except ModuleNotFoundError:  # ejecución directa desde services/identity/scripts
    from backup_restore import BACKUP_ROOT, BackupError, latest_set, verify_manifest

ROOT = Path("/opt/identity")
ENV_FILE = ROOT / ".env"
STATUS_FILE = BACKUP_ROOT / "offsite-status.json"
METRICS_DIR = BACKUP_ROOT / "metrics"
METRICS_FILE = METRICS_DIR / "offsite.prom"
RESTIC_BIN = Path("/usr/local/bin/restic")
REQUIRED = ("R2_ACCOUNT_ID", "R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")


def read_env(path: Path = ENV_FILE) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key] = value.strip()
    return values


def restic_environment(values: dict[str, str]) -> dict[str, str]:
    missing = [key for key in REQUIRED if not values.get(key)]
    password_file = Path(values.get("RESTIC_PASSWORD_FILE", str(ROOT / ".restic-password")))
    if missing:
        raise BackupError("Configuración R2 incompleta: faltan variables requeridas")
    if not password_file.is_file() or stat.S_IMODE(password_file.stat().st_mode) != 0o600:
        raise BackupError("La contraseña restic debe existir en un fichero con modo 0600")
    if not RESTIC_BIN.is_file():
        raise BackupError("restic no está instalado en la ruta versionada")
    account = values["R2_ACCOUNT_ID"]
    bucket = values["R2_BUCKET"]
    if not account.replace("-", "").isalnum() or not bucket.replace("-", "").isalnum():
        raise BackupError("Identificador de cuenta o bucket R2 no permitido")
    return {
        **os.environ,
        "AWS_ACCESS_KEY_ID": values["R2_ACCESS_KEY_ID"],
        "AWS_SECRET_ACCESS_KEY": values["R2_SECRET_ACCESS_KEY"],
        "RESTIC_PASSWORD_FILE": str(password_file),
        "RESTIC_REPOSITORY": f"s3:https://{account}.r2.cloudflarestorage.com/{bucket}",
    }


def run_restic(*args: str, env: dict[str, str], capture=True) -> str:
    result = subprocess.run(
        (str(RESTIC_BIN), *args),
        check=True,
        env=env,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=True,
    )
    return result.stdout.strip() if capture else ""


def initialize(values: dict[str, str]) -> None:
    env = restic_environment(values)
    run_restic("init", env=env)
    print("Repositorio externo inicializado")


def write_status(snapshot_id: str, set_name: str) -> None:
    now = datetime.now(UTC)
    payload = {
        "schema_version": 1,
        "last_success_at": now.isoformat(),
        "snapshot_id": snapshot_id,
        "backup_set": set_name,
    }
    temp = STATUS_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temp.chmod(0o600)
    temp.replace(STATUS_FILE)
    publish_metrics(enabled=True, last_success=now)


def publish_metrics(*, enabled: bool, last_success: datetime | None = None) -> None:
    if last_success is None and STATUS_FILE.is_file():
        try:
            payload = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
            last_success = datetime.fromisoformat(payload["last_success_at"])
        except KeyError, ValueError, json.JSONDecodeError:
            last_success = None
    METRICS_DIR.mkdir(mode=0o755, parents=True, exist_ok=True)
    METRICS_DIR.chmod(0o755)
    metric_temp = METRICS_FILE.with_suffix(".tmp")
    metric_temp.write_text(
        "# HELP personalhostel_offsite_backup_enabled Whether offsite backup is enabled.\n"
        "# TYPE personalhostel_offsite_backup_enabled gauge\n"
        f"personalhostel_offsite_backup_enabled {int(enabled)}\n"
        "# HELP personalhostel_offsite_backup_last_success_timestamp_seconds "
        "Unix timestamp of the last verified offsite backup upload.\n"
        "# TYPE personalhostel_offsite_backup_last_success_timestamp_seconds gauge\n"
        "personalhostel_offsite_backup_last_success_timestamp_seconds "
        f"{last_success.timestamp() if last_success else 0:.0f}\n",
        encoding="utf-8",
    )
    metric_temp.chmod(0o644)
    metric_temp.replace(METRICS_FILE)


def upload_latest(values: dict[str, str]) -> str:
    env = restic_environment(values)
    current = latest_set(BACKUP_ROOT)
    verify_manifest(current)
    output = run_restic(
        "backup",
        "--json",
        "--tag",
        "personalhostel-daily",
        str(current),
        env=env,
    )
    summary = None
    for line in output.splitlines():
        item = json.loads(line)
        if item.get("message_type") == "summary":
            summary = item
    snapshot_id = (summary or {}).get("snapshot_id")
    if not snapshot_id:
        raise BackupError("restic no devolvió un snapshot verificable")
    run_restic(
        "forget",
        "--tag",
        "personalhostel-daily",
        "--keep-daily",
        "30",
        "--prune",
        env=env,
    )
    write_status(snapshot_id, current.name)
    print("Copia externa cifrada OK")
    return snapshot_id


def verify_download(values: dict[str, str]) -> None:
    env = restic_environment(values)
    with tempfile.TemporaryDirectory(prefix="identity-offsite-verify-") as temp:
        target = Path(temp)
        run_restic(
            "restore",
            "latest",
            "--tag",
            "personalhostel-daily",
            "--target",
            str(target),
            env=env,
            capture=False,
        )
        manifests = list(target.rglob("manifest.json"))
        if len(manifests) != 1:
            raise BackupError("La descarga externa no contiene un único manifiesto")
        verify_manifest(manifests[0].parent)
    run_restic("check", env=env)
    print("Descarga externa y checksums verificados")


def check_freshness(max_hours: int = 30, status_file: Path = STATUS_FILE) -> None:
    try:
        payload = json.loads(status_file.read_text(encoding="utf-8"))
        last_success = datetime.fromisoformat(payload["last_success_at"])
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise BackupError("No existe estado externo válido") from exc
    if datetime.now(UTC) - last_success.astimezone(UTC) > timedelta(hours=max_hours):
        raise BackupError("La última copia externa válida supera el umbral")
    print("Antigüedad de copia externa OK")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init")
    subparsers.add_parser("upload")
    subparsers.add_parser("verify-download")
    subparsers.add_parser("publish-metrics")
    freshness = subparsers.add_parser("freshness")
    freshness.add_argument("--max-hours", type=int, default=30)
    args = parser.parse_args()
    try:
        values = read_env()
        if args.command == "init":
            initialize(values)
        elif args.command == "upload":
            upload_latest(values)
        elif args.command == "verify-download":
            verify_download(values)
        elif args.command == "publish-metrics":
            publish_metrics(enabled=values.get("OFFSITE_BACKUP_ENABLED", "").lower() == "true")
        else:
            check_freshness(args.max_hours)
    except (BackupError, OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
