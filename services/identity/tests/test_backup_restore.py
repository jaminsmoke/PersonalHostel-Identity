import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts import backup_restore


def write_valid_set(root: Path, name: str = "set-20260818T030000Z-abcdef1") -> Path:
    target = root / name
    target.mkdir()
    components = {}
    for filename in backup_restore.COMPONENTS:
        path = target / filename
        path.write_bytes(f"content-{filename}".encode())
        components[filename] = backup_restore.component_metadata(path)
    (target / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "status": "complete", "components": components}),
        encoding="utf-8",
    )
    return target


@pytest.mark.parametrize(
    "name",
    ["identity_camareros", "identity_negocio", "postgres", "anything", "Bad_restore_test"],
)
def test_restore_database_rejects_active_or_unsafe_names(name):
    with pytest.raises(backup_restore.BackupError, match="Destino rechazado"):
        backup_restore.validate_restore_database(name)


def test_restore_database_accepts_only_explicit_restore_suffix():
    assert (
        backup_restore.validate_restore_database("identity_camareros_restore_test")
        == "identity_camareros_restore_test"
    )


def test_manifest_detects_corruption_without_exposing_content(tmp_path):
    target = write_valid_set(tmp_path)
    backup_restore.verify_manifest(target)
    (target / "negocio.dump").write_bytes(b"corrupt")

    with pytest.raises(backup_restore.BackupError, match="tamaño inválido|Checksum inválido"):
        backup_restore.verify_manifest(target)


def test_manifest_rejects_missing_component(tmp_path):
    target = write_valid_set(tmp_path)
    (target / "fotos.tar.gz").unlink()

    with pytest.raises(backup_restore.BackupError, match="ausente"):
        backup_restore.verify_manifest(target)


def test_retention_never_removes_last_valid_set(tmp_path):
    old = write_valid_set(tmp_path)
    timestamp = (datetime.now(UTC) - timedelta(days=30)).timestamp()
    os.utime(old, (timestamp, timestamp))

    assert backup_restore.prune_valid_sets(tmp_path, now=datetime.now(UTC)) == []
    assert old.exists()


def test_retention_removes_old_set_when_new_valid_exists(tmp_path):
    old = write_valid_set(tmp_path)
    new = write_valid_set(tmp_path, "set-20260819T030000Z-bcdef12")
    timestamp = (datetime.now(UTC) - timedelta(days=30)).timestamp()
    os.utime(old, (timestamp, timestamp))

    assert backup_restore.prune_valid_sets(tmp_path, now=datetime.now(UTC)) == [old]
    assert not old.exists()
    assert new.exists()


def test_latest_set_rejects_path_traversal(tmp_path):
    (tmp_path / "latest").write_text("../outside\n", encoding="utf-8")

    with pytest.raises(backup_restore.BackupError, match="Puntero"):
        backup_restore.latest_set(tmp_path)
