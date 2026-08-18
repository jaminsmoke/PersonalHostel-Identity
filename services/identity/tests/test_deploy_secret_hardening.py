from pathlib import Path

from scripts import deploy_staging


class FakeEntry:
    def __init__(self, filename):
        self.filename = filename


class FakeRemoteFile:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self.payload


class FakeSftp:
    def __init__(self, payload: bytes = b"", entries=None):
        self.payload = payload
        self.entries = entries or []
        self.chmods = []
        self.closed = False

    def open(self, _path, _mode):
        return FakeRemoteFile(self.payload)

    def chmod(self, path, mode):
        self.chmods.append((path, mode))

    def listdir_attr(self, _path):
        return self.entries

    def close(self):
        self.closed = True


class FakeClient:
    def __init__(self, sftp):
        self.sftp = sftp

    def open_sftp(self):
        return self.sftp


def test_read_remote_env_decodes_without_logging(capsys):
    sftp = FakeSftp(b"SESSION_SECRET=not-logged\n")

    assert deploy_staging.read_remote_env(FakeClient(sftp)) == "SESSION_SECRET=not-logged\n"
    assert capsys.readouterr().out == ""
    assert sftp.closed is True


def test_harden_remote_env_permissions_forces_0600():
    sftp = FakeSftp(
        entries=[
            FakeEntry(".env"),
            FakeEntry(".env.bak-20260818"),
            FakeEntry(".env.deploy-tmp"),
            FakeEntry(".env.example"),
            FakeEntry("README.md"),
        ]
    )

    deploy_staging.harden_remote_env_permissions(FakeClient(sftp))

    assert sftp.chmods == [
        (f"{deploy_staging.REMOTE_DIR}/.env", 0o600),
        (f"{deploy_staging.REMOTE_DIR}/.env.bak-20260818", 0o600),
        (f"{deploy_staging.REMOTE_DIR}/.env.deploy-tmp", 0o600),
    ]
    assert sftp.closed is True


def test_deploy_exposes_isolated_backup_restore_drill():
    source = Path(deploy_staging.__file__).read_text(encoding="utf-8")

    assert '"--backup-restore-drill"' in source
    assert "backup_restore.py restore-drill" in source
