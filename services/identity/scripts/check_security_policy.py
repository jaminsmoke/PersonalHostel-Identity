"""Validate supply-chain reports against the repository security policy."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

BLOCKING_SEVERITIES = {"HIGH", "CRITICAL"}
REQUIRED_EXCEPTION_FIELDS = {"tool", "component", "reason", "owner", "expires"}


@dataclass(frozen=True)
class Finding:
    tool: str
    finding_id: str
    component: str
    detail: str
    blocking: bool

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.tool, self.finding_id, self.component.lower())


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_exceptions(path: Path, today: date | None = None) -> dict[tuple[str, str, str], dict]:
    today = today or date.today()
    payload = _read_json(path)
    if payload.get("schema_version") != 1 or not isinstance(payload.get("exceptions"), list):
        raise ValueError("La política debe usar schema_version=1 y una lista exceptions")

    result: dict[tuple[str, str, str], dict] = {}
    for index, item in enumerate(payload["exceptions"]):
        missing = REQUIRED_EXCEPTION_FIELDS - set(item)
        if missing:
            raise ValueError(f"Excepción {index}: faltan campos {sorted(missing)}")
        if not all(
            isinstance(item[field], str) and item[field].strip()
            for field in REQUIRED_EXCEPTION_FIELDS
        ):
            raise ValueError(f"Excepción {index}: todos los campos deben ser textos no vacíos")
        ids = item.get("ids")
        if (
            not isinstance(ids, list)
            or not ids
            or not all(isinstance(finding_id, str) and finding_id.strip() for finding_id in ids)
        ):
            raise ValueError(f"Excepción {index}: ids debe ser una lista no vacía de textos")
        try:
            expiry = date.fromisoformat(item["expires"])
        except ValueError as exc:
            raise ValueError(f"Excepción {index}: expires no es una fecha ISO válida") from exc
        if expiry < today:
            raise ValueError(f"Excepción {index}: caducó el {expiry.isoformat()}")
        for finding_id in ids:
            key = (item["tool"], finding_id, item["component"].lower())
            if key in result:
                raise ValueError(f"Excepción duplicada: {key}")
            result[key] = item
    return result


def findings_from_pip_audit(path: Path) -> list[Finding]:
    payload = _read_json(path)
    dependencies = payload.get("dependencies", payload if isinstance(payload, list) else [])
    findings: list[Finding] = []
    for dependency in dependencies:
        component = dependency.get("name", "unknown")
        version = dependency.get("version", "unknown")
        for vulnerability in dependency.get("vulns", []):
            fixes = vulnerability.get("fix_versions") or []
            findings.append(
                Finding(
                    tool="pip-audit",
                    finding_id=vulnerability["id"],
                    component=component,
                    detail=f"{component} {version}; fixes={','.join(fixes) or 'none'}",
                    blocking=True,
                )
            )
    return findings


def findings_from_trivy(path: Path) -> list[Finding]:
    payload = _read_json(path)
    findings: list[Finding] = []
    for result in payload.get("Results") or []:
        for vulnerability in result.get("Vulnerabilities") or []:
            severity = vulnerability.get("Severity", "UNKNOWN").upper()
            fixed_version = vulnerability.get("FixedVersion", "")
            if severity not in BLOCKING_SEVERITIES:
                continue
            target = result.get("Target", "unknown")
            package = vulnerability.get("PkgName", "unknown")
            component = f"{target}:{package}"
            findings.append(
                Finding(
                    tool="trivy",
                    finding_id=vulnerability["VulnerabilityID"],
                    component=component,
                    detail=f"{severity}; fixed={fixed_version or 'unavailable'}",
                    blocking=bool(fixed_version),
                )
            )
        for misconfiguration in result.get("Misconfigurations") or []:
            severity = misconfiguration.get("Severity", "UNKNOWN").upper()
            status = misconfiguration.get("Status", "FAIL").upper()
            if severity not in BLOCKING_SEVERITIES or status == "PASS":
                continue
            findings.append(
                Finding(
                    tool="trivy-config",
                    finding_id=misconfiguration["ID"],
                    component=result.get("Target", "repository"),
                    detail=f"{severity}; {misconfiguration.get('Title', '')}",
                    blocking=True,
                )
            )
    return findings


def evaluate(
    findings: list[Finding], exceptions: dict[tuple[str, str, str], dict]
) -> tuple[list[Finding], list[Finding], list[Finding]]:
    blocked: list[Finding] = []
    excepted: list[Finding] = []
    visible: list[Finding] = []
    for finding in findings:
        if finding.key in exceptions:
            excepted.append(finding)
        elif finding.blocking:
            blocked.append(finding)
        else:
            visible.append(finding)
    return blocked, excepted, visible


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exceptions", type=Path, required=True)
    parser.add_argument("--pip-audit-report", type=Path, action="append", default=[])
    parser.add_argument("--trivy-report", type=Path, action="append", default=[])
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        exceptions = load_exceptions(args.exceptions)
        findings = [
            finding
            for report in args.pip_audit_report
            for finding in findings_from_pip_audit(report)
        ]
        findings.extend(
            finding for report in args.trivy_report for finding in findings_from_trivy(report)
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Política de seguridad inválida: {exc}", file=sys.stderr)
        return 2

    blocked, excepted, visible = evaluate(findings, exceptions)
    print(
        f"security-policy: blocked={len(blocked)} excepted={len(excepted)} "
        f"visible_unfixed={len(visible)}"
    )
    for finding in [*blocked, *excepted, *visible]:
        state = "BLOCK" if finding in blocked else "EXCEPTED" if finding in excepted else "VISIBLE"
        print(
            f"{state}: {finding.tool}:{finding.finding_id}:{finding.component} ({finding.detail})"
        )
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
