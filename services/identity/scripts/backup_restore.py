#!/usr/bin/env python3
"""Crea y restaura conjuntos integrales de backup de PersonalHostel.

Los restores solo aceptan bases terminadas en ``_restore_test``. Nunca extrae
fotos sobre el volumen activo y nunca imprime filas, rutas de fotos ni PII.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path("/opt/identity")
BACKUP_ROOT = ROOT / "backups"
COMPOSE = ("docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.prod.yml")
ACTIVE_DATABASES = frozenset({"identity_camareros", "identity_negocio", "postgres"})
RESTORE_SUFFIX = "_restore_test"
SET_PATTERN = re.compile(r"^set-(\d{8}T\d{6}Z)-([0-9a-f]{7,40})$")
COMPONENTS = ("camareros.dump", "negocio.dump", "fotos.tar.gz")


class BackupError(RuntimeError):
    """Error operativo seguro para mostrar sin datos sensibles."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_restore_database(name: str) -> str:
    if name in ACTIVE_DATABASES or not name.endswith(RESTORE_SUFFIX):
        raise BackupError("Destino rechazado: el nombre debe terminar en _restore_test")
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,62}", name):
        raise BackupError("Destino rechazado: nombre PostgreSQL no permitido")
    return name


def component_metadata(path: Path) -> dict[str, int | str]:
    return {"file": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def verify_manifest(set_dir: Path) -> dict:
    try:
        manifest = json.loads((set_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupError("Conjunto sin manifiesto válido") from exc
    if manifest.get("schema_version") != 1 or manifest.get("status") != "complete":
        raise BackupError("Conjunto incompleto o de versión no compatible")
    listed = manifest.get("components", {})
    if set(listed) != set(COMPONENTS):
        raise BackupError("El manifiesto no contiene todos los componentes")
    for filename in COMPONENTS:
        path = set_dir / filename
        expected = listed[filename]
        if not path.is_file() or path.stat().st_size != expected.get("bytes"):
            raise BackupError("Componente ausente o con tamaño inválido")
        if sha256_file(path) != expected.get("sha256"):
            raise BackupError("Checksum inválido en un componente")
    return manifest


def prune_valid_sets(root: Path, *, now: datetime, retention_days: int = 7) -> list[Path]:
    valid: list[Path] = []
    for candidate in root.glob("set-*"):
        if not candidate.is_dir() or not SET_PATTERN.fullmatch(candidate.name):
            continue
        try:
            verify_manifest(candidate)
        except BackupError:
            continue
        valid.append(candidate)
    valid.sort(key=lambda path: path.name)
    if len(valid) < 2:
        return []
    cutoff = now - timedelta(days=retention_days)
    removed: list[Path] = []
    for candidate in valid[:-1]:
        modified = datetime.fromtimestamp(candidate.stat().st_mtime, UTC)
        if modified < cutoff:
            shutil.rmtree(candidate)
            removed.append(candidate)
    return removed


def run(command: tuple[str, ...] | list[str], *, stdout=None, text=True) -> str:
    result = subprocess.run(command, check=True, stdout=stdout or subprocess.PIPE, text=text)
    return "" if stdout else result.stdout.strip()


def compose(*args: str) -> tuple[str, ...]:
    return (*COMPOSE, *args)


def pg_user() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("POSTGRES_USER="):
            return line.partition("=")[2].strip() or "hosteleria"
    return "hosteleria"


def database_scalar(user: str, database: str, sql: str) -> str:
    return run(
        compose("exec", "-T", "db", "psql", "-XAt", "-U", user, "-d", database, "-c", sql)
    )


def dump_database(user: str, database: str, target: Path) -> None:
    with target.open("wb") as output:
        run(
            compose("exec", "-T", "db", "pg_dump", "-Fc", "-U", user, database),
            stdout=output,
            text=False,
        )
    if target.stat().st_size == 0:
        raise BackupError("pg_dump produjo un componente vacío")


def archive_photos(target: Path) -> None:
    with target.open("wb") as output:
        run(
            compose(
                "exec", "-T", "identity-camareros", "tar", "-C", "/app/data/fotos", "-czf", "-", "."
            ),
            stdout=output,
            text=False,
        )


def create_backup(root: Path = BACKUP_ROOT) -> Path:
    os.umask(0o077)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    started = datetime.now(UTC)
    commit = run(("git", "rev-parse", "HEAD"))
    set_id = f"{started.strftime('%Y%m%dT%H%M%SZ')}-{commit[:12]}"
    final_dir = root / f"set-{set_id}"
    partial_dir = root / f".set-{set_id}.partial"
    if final_dir.exists() or partial_dir.exists():
        raise BackupError("El identificador de conjunto ya existe")
    partial_dir.mkdir(mode=0o700)
    try:
        user = pg_user()
        dump_database(user, "identity_camareros", partial_dir / "camareros.dump")
        dump_database(user, "identity_negocio", partial_dir / "negocio.dump")
        archive_photos(partial_dir / "fotos.tar.gz")
        completed = datetime.now(UTC)
        manifest = {
            "schema_version": 1,
            "status": "complete",
            "backup_set_id": set_id,
            "started_at": started.isoformat(),
            "completed_at": completed.isoformat(),
            "source_commit": commit,
            "postgres_version": database_scalar(user, "postgres", "SHOW server_version"),
            "alembic": {
                "camareros": database_scalar(
                    user, "identity_camareros", "SELECT version_num FROM alembic_version"
                ),
                "negocio": database_scalar(
                    user, "identity_negocio", "SELECT version_num FROM alembic_version"
                ),
            },
            "components": {name: component_metadata(partial_dir / name) for name in COMPONENTS},
        }
        (partial_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        verify_manifest(partial_dir)
        partial_dir.rename(final_dir)
        latest_tmp = root / ".latest.tmp"
        latest_tmp.write_text(final_dir.name + "\n", encoding="utf-8")
        latest_tmp.replace(root / "latest")
        prune_valid_sets(root, now=completed)
    except Exception:
        shutil.rmtree(partial_dir, ignore_errors=True)
        raise
    print(f"Backup integral OK: {set_id}")
    return final_dir


def psql_admin(user: str, sql: str) -> None:
    run(
        compose(
            "exec", "-T", "db", "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", user, "-d", "postgres", "-c", sql
        )
    )


def recreate_restore_database(user: str, database: str) -> None:
    safe = validate_restore_database(database)
    psql_admin(user, f'DROP DATABASE IF EXISTS "{safe}" WITH (FORCE)')
    psql_admin(user, f'CREATE DATABASE "{safe}"')


def restore_dump(user: str, database: str, dump: Path) -> None:
    command = compose(
        "exec", "-T", "db", "pg_restore", "--exit-on-error", "--no-owner", "-U", user, "-d", database
    )
    with dump.open("rb") as source:
        subprocess.run(command, check=True, stdin=source)


def query_lines(user: str, database: str, sql: str) -> set[str]:
    return {line for line in database_scalar(user, database, sql).splitlines() if line}


def photo_members(archive: Path) -> set[str]:
    with tarfile.open(archive, "r:gz") as bundle:
        names = set()
        for member in bundle.getmembers():
            normalized = member.name.removeprefix("./")
            if member.isfile():
                if not normalized or normalized.startswith("/") or ".." in Path(normalized).parts:
                    raise BackupError("Ruta insegura en el archivo de fotos")
                names.add(normalized)
        return names


def restore_drill(set_dir: Path, camareros_db: str, negocio_db: str) -> dict[str, int | float]:
    started = time.monotonic()
    validate_restore_database(camareros_db)
    validate_restore_database(negocio_db)
    if camareros_db == negocio_db:
        raise BackupError("Cada dominio requiere una base de restauración distinta")
    verify_manifest(set_dir)
    user = pg_user()
    recreate_restore_database(user, camareros_db)
    recreate_restore_database(user, negocio_db)
    try:
        restore_dump(user, camareros_db, set_dir / "camareros.dump")
        restore_dump(user, negocio_db, set_dir / "negocio.dump")
        camareros = query_lines(user, camareros_db, "SELECT id::text FROM camareros")
        referenced = query_lines(
            user, negocio_db, "SELECT DISTINCT camarero_id::text FROM membresias"
        )
        foto_keys = query_lines(
            user, camareros_db, "SELECT foto_clave FROM camareros WHERE foto_clave IS NOT NULL"
        )
        photos = photo_members(set_dir / "fotos.tar.gz")
        if referenced - camareros or foto_keys - photos or photos - foto_keys:
            raise BackupError(
                "Invariantes fallidas: referencias o fotos no corresponden con sus metadatos"
            )
        for database in (camareros_db, negocio_db):
            if not database_scalar(user, database, "SELECT version_num FROM alembic_version"):
                raise BackupError("Revisión Alembic ausente tras restore")
        result = {
            "camareros": len(camareros),
            "membresias_referenciadas": len(referenced),
            "fotos": len(photos),
            "duration_seconds": round(time.monotonic() - started, 3),
        }
        print(json.dumps({"ok": True, **result}, ensure_ascii=False))
        return result
    finally:
        for database in (camareros_db, negocio_db):
            try:
                psql_admin(user, f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
            except subprocess.CalledProcessError:
                print("AVISO: no se pudo retirar una base aislada de restore", file=sys.stderr)


def latest_set(root: Path) -> Path:
    try:
        name = (root / "latest").read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise BackupError("No existe puntero al último conjunto válido") from exc
    candidate = root / name
    if not SET_PATTERN.fullmatch(name) or candidate.parent != root or not candidate.is_dir():
        raise BackupError("Puntero al último conjunto no válido")
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("backup", help="Crea y publica atómicamente un conjunto completo")
    verify_parser = subparsers.add_parser("verify", help="Verifica manifiesto y checksums")
    verify_parser.add_argument("set_dir", nargs="?", type=Path)
    restore_parser = subparsers.add_parser(
        "restore-drill", help="Restaura en bases aisladas y las retira"
    )
    restore_parser.add_argument("set_dir", nargs="?", type=Path)
    restore_parser.add_argument("--camareros-db", default="identity_camareros_restore_test")
    restore_parser.add_argument("--negocio-db", default="identity_negocio_restore_test")
    args = parser.parse_args()
    try:
        if args.command == "backup":
            create_backup()
        elif args.command == "verify":
            verify_manifest(args.set_dir or latest_set(BACKUP_ROOT))
            print("Conjunto válido")
        else:
            restore_drill(
                args.set_dir or latest_set(BACKUP_ROOT), args.camareros_db, args.negocio_db
            )
    except (BackupError, OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
