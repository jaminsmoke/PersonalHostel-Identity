import json
from datetime import UTC, datetime, timedelta

import pytest
from scripts import offsite_backup


def test_read_env_does_not_log_or_transform_secret(tmp_path, capsys):
    path = tmp_path / ".env"
    path.write_text("R2_SECRET_ACCESS_KEY=secret-value\nR2_BUCKET=backup-test\n", encoding="utf-8")

    values = offsite_backup.read_env(path)

    assert values["R2_SECRET_ACCESS_KEY"] == "secret-value"
    assert capsys.readouterr().out == ""


def test_restic_environment_requires_password_file_0600(tmp_path, monkeypatch):
    password = tmp_path / "password"
    password.write_text("not-a-real-password", encoding="utf-8")
    password.chmod(0o644)
    monkeypatch.setattr(offsite_backup, "RESTIC_BIN", tmp_path / "restic")
    (tmp_path / "restic").touch()
    values = {
        "R2_ACCOUNT_ID": "account",
        "R2_BUCKET": "bucket",
        "R2_ACCESS_KEY_ID": "access",
        "R2_SECRET_ACCESS_KEY": "secret",
        "RESTIC_PASSWORD_FILE": str(password),
    }

    with pytest.raises(offsite_backup.BackupError, match="modo 0600"):
        offsite_backup.restic_environment(values)


def test_restic_environment_maps_r2_without_leaking_secret(tmp_path, monkeypatch):
    password = tmp_path / "password"
    password.write_text("not-a-real-password", encoding="utf-8")
    password.chmod(0o600)
    binary = tmp_path / "restic"
    binary.touch()
    monkeypatch.setattr(offsite_backup, "RESTIC_BIN", binary)
    values = {
        "R2_ACCOUNT_ID": "account-123",
        "R2_BUCKET": "personalhostel-backups",
        "R2_ACCESS_KEY_ID": "access",
        "R2_SECRET_ACCESS_KEY": "secret",
        "RESTIC_PASSWORD_FILE": str(password),
    }

    env = offsite_backup.restic_environment(values)

    assert env["RESTIC_REPOSITORY"].endswith("/personalhostel-backups")
    assert env["AWS_ACCESS_KEY_ID"] == "access"
    assert env["AWS_SECRET_ACCESS_KEY"] == "secret"


def test_freshness_rejects_stale_status(tmp_path):
    status = tmp_path / "status.json"
    status.write_text(
        json.dumps({"last_success_at": (datetime.now(UTC) - timedelta(hours=31)).isoformat()}),
        encoding="utf-8",
    )

    with pytest.raises(offsite_backup.BackupError, match="supera el umbral"):
        offsite_backup.check_freshness(30, status)


def test_freshness_accepts_recent_status(tmp_path, capsys):
    status = tmp_path / "status.json"
    status.write_text(
        json.dumps({"last_success_at": datetime.now(UTC).isoformat()}), encoding="utf-8"
    )

    offsite_backup.check_freshness(30, status)

    assert "OK" in capsys.readouterr().out


def test_write_status_publishes_sanitized_prometheus_metric(tmp_path, monkeypatch):
    status = tmp_path / "offsite-status.json"
    metrics_dir = tmp_path / "metrics"
    metric = metrics_dir / "offsite.prom"
    monkeypatch.setattr(offsite_backup, "STATUS_FILE", status)
    monkeypatch.setattr(offsite_backup, "METRICS_DIR", metrics_dir)
    monkeypatch.setattr(offsite_backup, "METRICS_FILE", metric)

    offsite_backup.write_status("snapshot-secret", "set-with-private-path")

    metric_text = metric.read_text(encoding="utf-8")
    assert "personalhostel_offsite_backup_last_success_timestamp_seconds" in metric_text
    assert "snapshot-secret" not in metric_text
    assert "set-with-private-path" not in metric_text
    assert metric.stat().st_mode & 0o777 == 0o644


def test_publish_metrics_marks_disabled_without_remote_credentials(tmp_path, monkeypatch):
    metrics_dir = tmp_path / "metrics"
    metric = metrics_dir / "offsite.prom"
    monkeypatch.setattr(offsite_backup, "STATUS_FILE", tmp_path / "missing.json")
    monkeypatch.setattr(offsite_backup, "METRICS_DIR", metrics_dir)
    monkeypatch.setattr(offsite_backup, "METRICS_FILE", metric)

    offsite_backup.publish_metrics(enabled=False)

    metric_text = metric.read_text(encoding="utf-8")
    assert "personalhostel_offsite_backup_enabled 0" in metric_text
    assert "personalhostel_offsite_backup_last_success_timestamp_seconds 0" in metric_text
