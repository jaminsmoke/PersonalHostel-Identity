"""Procesador pequeño y reintentable de la outbox de email."""

import os
from datetime import UTC, datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.email import get_email_sender
from app.models import EmailOutbox, EmailOutboxEstado
from app.security import get_session_secret_env, unprotect_invitation_token


def process_pending_outbox(db: Session, limit: int = 20) -> int:
    processed = 0
    max_attempts = int(os.environ.get("EMAIL_MAX_ATTEMPTS", "5"))
    for _ in range(limit):
        row = (
            db.query(EmailOutbox)
            .filter(
                or_(
                    EmailOutbox.estado == EmailOutboxEstado.pendiente,
                    EmailOutbox.estado == EmailOutboxEstado.fallido,
                ),
                EmailOutbox.intentos < max_attempts,
            )
            .order_by(EmailOutbox.creado_en)
            .with_for_update(skip_locked=True)
            .first()
        )
        if row is None:
            break
        row.estado = EmailOutboxEstado.enviando
        row.intentos += 1
        db.commit()
        try:
            token = unprotect_invitation_token(
                row.payload["token_encrypted"], get_session_secret_env()
            )
            base_url = row.payload["invitation_url_base"].rstrip("/")
            link = f"{base_url}/{token}"
            get_email_sender().send_invitation(
                row.destinatario,
                link,
                row.payload["establishment_name"],
            )
            row.estado = EmailOutboxEstado.enviado
            row.enviado_en = datetime.now(UTC)
            row.ultimo_error = None
        except Exception as exc:  # sender failures must remain retryable
            row.estado = EmailOutboxEstado.fallido
            row.ultimo_error = str(exc)[:1000]
        db.commit()
        processed += 1
    return processed
