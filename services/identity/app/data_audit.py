"""Auditoría read-only de procedencia para las dos BDs de Identity."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterable
from typing import Any

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.db import camarero_engine, negocio_engine
from app.models import (
    Camarero,
    ConflictoSync,
    Credencial,
    CuentaNegocio,
    DataOrigin,
    EmailOutbox,
    Establecimiento,
    Invitacion,
    LayoutEstablecimiento,
    Membresia,
    NotificacionNegocio,
    OperacionSync,
    ProductoCatalogo,
)

ALLOWED_DATABASES = {
    "identity_camareros",
    "identity_negocio",
    "identity_camareros_test",
    "identity_negocio_test",
}
REDACTED = "[REDACTED]"


def _database_name(engine: Engine) -> str:
    return engine.url.database or ""


def _validate_database(engine: Engine, allow_unexpected: bool) -> dict[str, Any]:
    name = _database_name(engine)
    if not allow_unexpected and name not in ALLOWED_DATABASES:
        raise ValueError(
            f"Base de datos inesperada: {name or '<sin nombre>'}. "
            "Usa --allow-unexpected-database solo tras verificar el destino."
        )
    return {
        "host": engine.url.host,
        "port": engine.url.port,
        "database": name,
    }


def _has_test_suffix(values: Iterable[str | None]) -> bool:
    for value in values:
        if not value:
            continue
        candidate = value.split("@", 1)[0] if "@" in value else value
        if candidate.strip().casefold().endswith("test"):
            return True
    return False


def _visible(values: dict[str, str | None], show_pii: bool) -> dict[str, str | None]:
    if show_pii:
        return values
    return {key: REDACTED if value else None for key, value in values.items()}


def _origin_counts(rows: Iterable[Any]) -> dict[str, int]:
    counts = Counter(row.data_origin.value for row in rows)
    return {origin.value: counts.get(origin.value, 0) for origin in DataOrigin}


def _related_counts(db: Session, model, root, join_condition) -> dict[str, int]:
    rows = db.execute(
        select(root.data_origin, func.count())
        .join(model, join_condition)
        .group_by(root.data_origin)
    ).all()
    counts = {origin.value: count for origin, count in rows}
    return {origin.value: counts.get(origin.value, 0) for origin in DataOrigin}


def _legacy_findings(
    entity: str,
    rows: Iterable[Any],
    fields,
    show_pii: bool,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for row in rows:
        values = fields(row)
        suffix = _has_test_suffix(values.values())
        reason = None
        if row.data_origin is DataOrigin.real and suffix:
            reason = "sufijo_test_con_origen_real"
        elif row.data_origin is DataOrigin.test and not suffix:
            reason = "origen_test_sin_sufijo_legacy"
        if reason:
            findings.append(
                {
                    "kind": "legacy_mismatch",
                    "reason": reason,
                    "entity": entity,
                    "id": str(row.id),
                    "data_origin": row.data_origin.value,
                    "fields": _visible(values, show_pii),
                }
            )
    return findings


def audit_data(
    *,
    camareros: Engine = camarero_engine,
    negocio: Engine = negocio_engine,
    show_pii: bool = False,
    allow_unexpected_database: bool = False,
) -> dict[str, Any]:
    """Inspecciona procedencia y relaciones sin escribir en las BDs."""

    database_names = {
        "camareros": _validate_database(camareros, allow_unexpected_database),
        "negocio": _validate_database(negocio, allow_unexpected_database),
    }
    with camareros.connect() as camarero_conn, negocio.connect() as negocio_conn:
        camarero_tx = camarero_conn.begin()
        negocio_tx = negocio_conn.begin()
        try:
            camarero_conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            negocio_conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            with (
                Session(bind=camarero_conn) as camarero_db,
                Session(bind=negocio_conn) as negocio_db,
            ):
                waiters = list(camarero_db.scalars(select(Camarero)))
                accounts = list(negocio_db.scalars(select(CuentaNegocio)))
                establishments = list(negocio_db.scalars(select(Establecimiento)))
                products = list(negocio_db.scalars(select(ProductoCatalogo)))
                memberships = list(negocio_db.scalars(select(Membresia)))

                findings: list[dict[str, Any]] = []
                findings += _legacy_findings(
                    "camarero",
                    waiters,
                    lambda row: {
                        "nombre": row.nombre,
                        "apellidos": row.apellidos,
                        "nick": row.nick,
                        "email": row.email,
                    },
                    show_pii,
                )
                findings += _legacy_findings(
                    "cuenta_negocio",
                    accounts,
                    lambda row: {
                        "nombre_mostrar": row.nombre_mostrar,
                        "email": row.email,
                    },
                    show_pii,
                )
                findings += _legacy_findings(
                    "establecimiento",
                    establishments,
                    lambda row: {"nombre": row.nombre},
                    show_pii,
                )
                findings += _legacy_findings(
                    "producto",
                    products,
                    lambda row: {"nombre": row.nombre},
                    show_pii,
                )

                waiter_origin = {row.id: row.data_origin for row in waiters}
                account_origin = {row.id: row.data_origin for row in accounts}
                establishment_origin = {row.id: row.data_origin for row in establishments}

                for establishment in establishments:
                    parent = account_origin.get(establishment.cuenta_negocio_id)
                    if parent is None:
                        findings.append(
                            {
                                "kind": "orphan_reference",
                                "entity": "establecimiento",
                                "id": str(establishment.id),
                                "reference": "cuenta_negocio_id",
                            }
                        )
                    elif parent is not establishment.data_origin:
                        findings.append(
                            {
                                "kind": "mixed_origin",
                                "entity": "establecimiento",
                                "id": str(establishment.id),
                                "data_origin": establishment.data_origin.value,
                                "parent_origin": parent.value,
                            }
                        )
                for product in products:
                    parent = establishment_origin.get(product.establecimiento_id)
                    if parent is None:
                        findings.append(
                            {
                                "kind": "orphan_reference",
                                "entity": "producto",
                                "id": str(product.id),
                                "reference": "establecimiento_id",
                            }
                        )
                    elif parent is not product.data_origin:
                        findings.append(
                            {
                                "kind": "mixed_origin",
                                "entity": "producto",
                                "id": str(product.id),
                                "data_origin": product.data_origin.value,
                                "parent_origin": parent.value,
                            }
                        )
                for account in accounts:
                    if account.camarero_vinculado_id is None:
                        continue
                    linked = waiter_origin.get(account.camarero_vinculado_id)
                    if linked is None:
                        findings.append(
                            {
                                "kind": "orphan_cross_database_reference",
                                "entity": "cuenta_negocio",
                                "id": str(account.id),
                                "reference": "camarero_vinculado_id",
                            }
                        )
                    elif linked is not account.data_origin:
                        findings.append(
                            {
                                "kind": "mixed_cross_database_origin",
                                "entity": "cuenta_negocio",
                                "id": str(account.id),
                                "data_origin": account.data_origin.value,
                                "linked_origin": linked.value,
                            }
                        )
                for membership in memberships:
                    waiter = waiter_origin.get(membership.camarero_id)
                    establishment = establishment_origin.get(membership.establecimiento_id)
                    if waiter is None:
                        findings.append(
                            {
                                "kind": "orphan_cross_database_reference",
                                "entity": "membresia",
                                "id": str(membership.id),
                                "reference": "camarero_id",
                            }
                        )
                    elif establishment is not None and waiter is not establishment:
                        findings.append(
                            {
                                "kind": "mixed_cross_database_origin",
                                "entity": "membresia",
                                "id": str(membership.id),
                                "camarero_origin": waiter.value,
                                "establecimiento_origin": establishment.value,
                            }
                        )

                counts = {
                    "camareros": _origin_counts(waiters),
                    "cuentas_negocio": _origin_counts(accounts),
                    "establecimientos": _origin_counts(establishments),
                    "productos_catalogo": _origin_counts(products),
                }
                dependencies = {
                    "credenciales": _related_counts(
                        camarero_db,
                        Credencial,
                        Camarero,
                        Credencial.camarero_id == Camarero.id,
                    ),
                    "membresias": _related_counts(
                        negocio_db,
                        Membresia,
                        Establecimiento,
                        Membresia.establecimiento_id == Establecimiento.id,
                    ),
                    "layouts_establecimiento": _related_counts(
                        negocio_db,
                        LayoutEstablecimiento,
                        Establecimiento,
                        LayoutEstablecimiento.establecimiento_id == Establecimiento.id,
                    ),
                    "invitaciones": _related_counts(
                        negocio_db,
                        Invitacion,
                        Establecimiento,
                        Invitacion.establecimiento_id == Establecimiento.id,
                    ),
                    "operaciones_sync": _related_counts(
                        negocio_db,
                        OperacionSync,
                        Establecimiento,
                        OperacionSync.establecimiento_id == Establecimiento.id,
                    ),
                    "conflictos_sync": _related_counts(
                        negocio_db,
                        ConflictoSync,
                        Establecimiento,
                        ConflictoSync.establecimiento_id == Establecimiento.id,
                    ),
                    "notificaciones_negocio": _related_counts(
                        negocio_db,
                        NotificacionNegocio,
                        Establecimiento,
                        NotificacionNegocio.establecimiento_id == Establecimiento.id,
                    ),
                    "email_outbox_con_invitacion": negocio_db.scalar(
                        select(func.count(EmailOutbox.id)).where(
                            EmailOutbox.invitacion_id.is_not(None)
                        )
                    )
                    or 0,
                    "email_outbox_sin_raiz": negocio_db.scalar(
                        select(func.count(EmailOutbox.id)).where(
                            EmailOutbox.invitacion_id.is_(None)
                        )
                    )
                    or 0,
                }
                non_real_total = sum(
                    values[DataOrigin.test.value] + values[DataOrigin.demo.value]
                    for values in counts.values()
                )
                return {
                    "ok": not findings,
                    "databases": database_names,
                    "pii_redacted": not show_pii,
                    "counts": counts,
                    "dependencies": dependencies,
                    "non_real_total": non_real_total,
                    "findings": findings,
                    "detected": non_real_total > 0 or bool(findings),
                }
        finally:
            camarero_tx.rollback()
            negocio_tx.rollback()


def _human_report(report: dict[str, Any]) -> str:
    lines = [
        "Auditoría de procedencia de Identity (solo lectura)",
        (
            "BD camareros="
            f"{report['databases']['camareros']['host']}:"
            f"{report['databases']['camareros']['port']}/"
            f"{report['databases']['camareros']['database']} · negocio="
            f"{report['databases']['negocio']['host']}:"
            f"{report['databases']['negocio']['port']}/"
            f"{report['databases']['negocio']['database']}"
        ),
    ]
    for entity, counts in report["counts"].items():
        lines.append(
            f"- {entity}: real={counts['real']} test={counts['test']} demo={counts['demo']}"
        )
    lines.append("Dependencias (sin PII):")
    for entity, counts in report["dependencies"].items():
        if isinstance(counts, dict):
            lines.append(
                f"- {entity}: real={counts['real']} test={counts['test']} demo={counts['demo']}"
            )
        else:
            lines.append(f"- {entity}: {counts}")
    lines.append(f"Hallazgos de coherencia: {len(report['findings'])}")
    for finding in report["findings"]:
        lines.append(f"  - {finding['kind']} · {finding['entity']} · {finding['id']}")
    lines.append("PII redactada" if report["pii_redacted"] else "PII visible (uso manual)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--show-pii", action="store_true")
    parser.add_argument("--allow-unexpected-database", action="store_true")
    parser.add_argument(
        "--fail-on-detected",
        action="store_true",
        help="Devuelve 2 si existen datos no reales o incoherencias.",
    )
    args = parser.parse_args(argv)
    try:
        report = audit_data(
            show_pii=args.show_pii,
            allow_unexpected_database=args.allow_unexpected_database,
        )
    except Exception as exc:
        error = {"ok": False, "error": str(exc)}
        print(json.dumps(error, ensure_ascii=False) if args.format == "json" else error["error"])
        return 1
    print(
        json.dumps(report, ensure_ascii=False, indent=2)
        if args.format == "json"
        else _human_report(report)
    )
    return 2 if args.fail_on_detected and report["detected"] else 0


if __name__ == "__main__":
    sys.exit(main())
