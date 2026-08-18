import base64

from scripts.check_production_secrets import (
    KNOWN_DEFAULTS,
    main,
    parse_env,
    validate_env_text,
    validate_production_secrets,
)


def valid_values():
    return {
        "POSTGRES_PASSWORD": "postgres-password-strong-123",
        "SESSION_SECRET": "session-secret-with-at-least-forty-eight-characters-123456",
        "QR_SIGNING_KEY": base64.b64encode(b"q" * 32).decode(),
        "EMAIL_PASSWORD": "smtp-password-123",
        "GRAFANA_ADMIN_PASSWORD": "grafana-password-123",
        "ALLOW_NON_REAL_DATA": "false",
    }


def test_valid_configuration_passes():
    assert validate_production_secrets(valid_values()) == []


def test_rejects_missing_short_defaults_and_non_real_data():
    values = valid_values()
    values.pop("EMAIL_PASSWORD")
    values["POSTGRES_PASSWORD"] = "short"
    values["SESSION_SECRET"] = next(iter(KNOWN_DEFAULTS["SESSION_SECRET"]))
    values["ALLOW_NON_REAL_DATA"] = "true"

    errors = validate_production_secrets(values)

    assert "EMAIL_PASSWORD: ausente o vacío" in errors
    assert "POSTGRES_PASSWORD: longitud insuficiente" in errors
    assert "SESSION_SECRET: coincide con un default conocido" in errors
    assert "ALLOW_NON_REAL_DATA: debe ser false en producción" in errors


def test_rejects_invalid_qr_key():
    values = valid_values()
    values["QR_SIGNING_KEY"] = "x" * 44

    assert "QR_SIGNING_KEY: debe ser base64 de 32 bytes" in validate_production_secrets(values)


def test_parser_reports_duplicate_without_leaking_value():
    secret = "do-not-print-this-secret"
    values, duplicates = parse_env(f"EMAIL_PASSWORD={secret}\nEMAIL_PASSWORD=another-secret\n")
    errors = validate_production_secrets(values, duplicates)

    assert "EMAIL_PASSWORD: definición duplicada" in errors
    assert all(secret not in error for error in errors)


def test_cli_never_prints_secret_values(tmp_path, capsys, monkeypatch):
    secret = "visible-only-in-input"
    env_file = tmp_path / ".env"
    env_file.write_text(f"POSTGRES_PASSWORD={secret}\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["check_production_secrets.py", "--env-file", str(env_file)])

    assert main() == 1
    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err


def test_text_validation_detects_duplicate_required_key():
    values = valid_values()
    text = "\n".join(f"{key}={value}" for key, value in values.items())
    text += f"\nSESSION_SECRET={values['SESSION_SECRET']}\n"

    assert "SESSION_SECRET: definición duplicada" in validate_env_text(text)


def test_offsite_secrets_are_required_only_when_enabled():
    values = valid_values()
    values["OFFSITE_BACKUP_ENABLED"] = "true"

    errors = validate_production_secrets(values)

    assert "R2_ACCOUNT_ID: requerido cuando el backup externo está activo" in errors
    assert "R2_BUCKET: requerido cuando el backup externo está activo" in errors
    assert "R2_ACCESS_KEY_ID: requerido cuando el backup externo está activo" in errors
    assert "R2_SECRET_ACCESS_KEY: requerido cuando el backup externo está activo" in errors
    assert "RESTIC_PASSWORD_FILE: requerido cuando el backup externo está activo" in errors

    values.update(
        {
            "R2_ACCOUNT_ID": "account",
            "R2_BUCKET": "bucket",
            "R2_ACCESS_KEY_ID": "access",
            "R2_SECRET_ACCESS_KEY": "secret",
            "RESTIC_PASSWORD_FILE": "/opt/identity/.restic-password",
        }
    )
    assert validate_production_secrets(values) == []
