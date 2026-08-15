import json
from datetime import date

import pytest
from scripts.check_security_policy import (
    Finding,
    evaluate,
    findings_from_pip_audit,
    findings_from_trivy,
    load_exceptions,
)


def write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_policy_rejects_expired_exception(tmp_path):
    path = write_json(
        tmp_path / "exceptions.json",
        {
            "schema_version": 1,
            "exceptions": [
                {
                    "tool": "pip-audit",
                    "ids": ["CVE-1"],
                    "component": "demo",
                    "reason": "Sin versión corregida",
                    "owner": "security",
                    "expires": "2026-01-01",
                }
            ],
        },
    )

    with pytest.raises(ValueError, match="caducó"):
        load_exceptions(path, today=date(2026, 8, 15))


def test_policy_matches_only_exact_scoped_exception(tmp_path):
    path = write_json(
        tmp_path / "exceptions.json",
        {
            "schema_version": 1,
            "exceptions": [
                {
                    "tool": "pip-audit",
                    "ids": ["CVE-1"],
                    "component": "demo",
                    "reason": "Sin versión corregida",
                    "owner": "security",
                    "expires": "2026-09-01",
                }
            ],
        },
    )
    exceptions = load_exceptions(path, today=date(2026, 8, 15))
    matching = Finding("pip-audit", "CVE-1", "Demo", "", True)
    other_package = Finding("pip-audit", "CVE-1", "other", "", True)

    blocked, excepted, visible = evaluate([matching, other_package], exceptions)

    assert excepted == [matching]
    assert blocked == [other_package]
    assert visible == []


def test_pip_audit_findings_always_block_without_exception(tmp_path):
    report = write_json(
        tmp_path / "pip.json",
        {
            "dependencies": [
                {
                    "name": "demo",
                    "version": "1.0",
                    "vulns": [{"id": "CVE-1", "fix_versions": []}],
                }
            ]
        },
    )

    finding = findings_from_pip_audit(report)[0]

    assert finding.blocking is True
    assert finding.component == "demo"


def test_trivy_blocks_fixable_and_keeps_unfixed_visible(tmp_path):
    report = write_json(
        tmp_path / "trivy.json",
        {
            "Results": [
                {
                    "Target": "image",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-FIX",
                            "PkgName": "fixed-package",
                            "Severity": "HIGH",
                            "FixedVersion": "2.0",
                        },
                        {
                            "VulnerabilityID": "CVE-NOFIX",
                            "PkgName": "unfixed-package",
                            "Severity": "CRITICAL",
                            "FixedVersion": "",
                        },
                    ],
                }
            ]
        },
    )

    blocked, excepted, visible = evaluate(findings_from_trivy(report), {})

    assert [finding.finding_id for finding in blocked] == ["CVE-FIX"]
    assert blocked[0].component == "image:fixed-package"
    assert excepted == []
    assert [finding.finding_id for finding in visible] == ["CVE-NOFIX"]
