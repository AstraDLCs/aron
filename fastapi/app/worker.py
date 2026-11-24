"""Worker de clasificación: toma postulaciones 'En cola' de a una y las clasifica con OpenRouter.

Las unidades (`process_one`, `recover_stuck`) reciben la sesión; solo `run_forever` abre `SessionLocal`.
Se ejecuta con `python -m app.worker`. Límites: `WORKER_RATE_PER_MINUTE` clasificaciones por minuto, 3 intentos
por postulación (espera `30·2^intentos` s entre ellos) y pausa hasta el reinicio diario ante un 429 diario.
Nunca se registra la clave de la API ni el texto de los CVs.
"""
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.audit import log_action
from app.config import get_settings
from app.constants import AI_ACTOR
from app.models.people import Candidate
from app.services.app_settings import get_app_settings
from app.services.classifier import ClassificationFormatError, classify_candidate
from app.services.openrouter import (
    DailyLimitReached,
    OpenRouterClient,
    OpenRouterError,
    PerMinuteRateLimit,
    make_client,
    next_utc_midnight,
)

try:  # la revisión de la carpeta del servidor la agrega la Tarea 8
    from app.services import server_scan
except ImportError:  # pragma: no cover - hasta entonces no hace nada
    server_scan = None

logger = logging.getLogger("app.worker")

MAX_ATTEMPTS = 3
RETRY_BASE_S = 30
IDLE_WAIT_S = 5
ERROR_MESSAGE_MAX = 500

Outcome = Literal["idle", "processed", "paused", "error"]


def recover_stuck(db: Session) -> int:
    """Devuelve a 'En cola' las postulaciones que quedaron 'Procesando' (el worker se cayó a mitad)."""
    result = db.execute(
        update(Candidate).where(Candidate.ai_status == "Procesando").values(ai_status="En cola"),
        execution_options={"synchronize_session": False},
    )
    db.commit()
    return result.rowcount or 0


def _failure_text(exc: Exception) -> str:
    """Mensaje para `ai_error`: solo textos propios; un error inesperado no expone sus datos."""
    if isinstance(exc, (OpenRouterError, ClassificationFormatError)):
        return str(exc)[:ERROR_MESSAGE_MAX]
    return f"Error interno al clasificar ({type(exc).__name__})"


def _pause_daily(db: Session, candidate: Candidate, reset_at: datetime, now: datetime) -> None:
    if reset_at <= now:  # un reinicio ya vencido no pausa nada: se usa el siguiente a las 00:00 UTC
        reset_at = next_utc_midnight(now)
    settings = get_app_settings(db)
    candidate.ai_status = "En cola"
    if settings.ai_paused_until != reset_at:
        settings.ai_paused_until = reset_at
        log_action(
            db, actor=AI_ACTOR, action="ai.daily_limit", entity_type="settings", entity_id="1",
            summary=f"Se alcanzó el límite diario de OpenRouter: la cola queda en pausa hasta {reset_at.isoformat()}",
            details={"pausedUntil": reset_at.isoformat()},
        )


def _record_failure(db: Session, candidate: Candidate, exc: Exception, now: datetime) -> None:
    candidate.ai_attempts = (candidate.ai_attempts or 0) + 1
    message = _failure_text(exc)
    if candidate.ai_attempts >= MAX_ATTEMPTS:
        candidate.ai_status = "Error IA"
        candidate.ai_error = message
        candidate.ai_next_attempt_at = None
        log_action(
            db, actor=AI_ACTOR, action="ai.classify_error", entity_type="candidate", entity_id=candidate.id,
            summary=f"La IA no pudo clasificar la postulación tras {candidate.ai_attempts} intentos",
            details={"error": message, "attempts": candidate.ai_attempts},
        )
    else:
        candidate.ai_status = "En cola"
        candidate.ai_error = message
        candidate.ai_next_attempt_at = now + timedelta(seconds=RETRY_BASE_S * 2**candidate.ai_attempts)


def process_one(db: Session, client: OpenRouterClient | None, now: datetime) -> Outcome:
    """Clasifica la siguiente postulación en cola.

    'idle': no hay nada que hacer (sin cliente, IA apagada o cola vacía). 'paused': pausa por el límite diario
    (o límite por minuto: la postulación se reintenta más tarde). 'processed': clasificada. 'error': falló.
    """
    settings = get_app_settings(db)
    if client is None or not settings.ai_enabled:
        return "idle"
    if settings.ai_paused_until is not None:
        if settings.ai_paused_until > now:
            return "paused"
        settings.ai_paused_until = None  # ya pasó el reinicio diario
        db.commit()

    candidate = db.scalar(
        select(Candidate)
        .where(Candidate.ai_status == "En cola", or_(Candidate.ai_next_attempt_at.is_(None), Candidate.ai_next_attempt_at <= now))
        .order_by(Candidate.created_at, Candidate.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if candidate is None:
        return "idle"
    candidate_id = candidate.id
    candidate.ai_status = "Procesando"
    db.commit()  # suelta el bloqueo: durante la llamada al modelo no se mantiene abierta la fila

    try:
        classify_candidate(db, candidate, client)
        db.commit()
        return "processed"
    except Exception as exc:  # noqa: BLE001 - cualquier fallo se anota en la postulación
        db.rollback()
        candidate = db.get(Candidate, candidate_id)
        if isinstance(exc, DailyLimitReached):
            _pause_daily(db, candidate, exc.reset_at, now)
            outcome: Outcome = "paused"
        elif isinstance(exc, PerMinuteRateLimit):
            candidate.ai_status = "En cola"
            candidate.ai_next_attempt_at = now + timedelta(seconds=exc.retry_after_s)
            outcome = "paused"
        else:
            if not isinstance(exc, (OpenRouterError, ClassificationFormatError)):
                logger.exception("Error inesperado al clasificar la postulación %s", candidate_id)
            _record_failure(db, candidate, exc, now)
            outcome = "error"
        db.commit()
        logger.warning("Postulación %s: %s", candidate_id, _failure_text(exc))
        return outcome


def _run_server_scan() -> None:
    """Revisa la carpeta de CVs del servidor (Tarea 8: `server_scan.scan_once(db)`)."""
    scan = getattr(server_scan, "scan_once", None)
    if scan is None:
        return
    from app.db import SessionLocal

    with SessionLocal() as db:
        scan(db)


def run_forever() -> None:
    from app.db import SessionLocal

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    client = make_client()
    delay_processed = 60 / max(1, settings.worker_rate_per_minute)
    logger.info(
        "Worker iniciado (IA %s, %s clasificaciones por minuto como máximo)",
        "configurada" if client else "no configurada: sin OPENROUTER_API_KEY, solo espera", settings.worker_rate_per_minute,
    )

    recovered = None
    while recovered is None:
        try:
            with SessionLocal() as db:
                recovered = recover_stuck(db)
        except Exception:  # noqa: BLE001 - la base puede no estar lista todavía
            logger.exception("No se pudo recuperar la cola; se reintenta")
            time.sleep(IDLE_WAIT_S)
    if recovered:
        logger.info("%s postulaciones 'Procesando' volvieron a la cola", recovered)

    last_scan: float | None = None
    last_outcome: Outcome | None = None
    while True:
        wait = IDLE_WAIT_S
        try:
            if last_scan is None or time.monotonic() - last_scan >= settings.server_scan_interval_s:
                last_scan = time.monotonic()
                _run_server_scan()
            with SessionLocal() as db:
                outcome = process_one(db, client, datetime.now(UTC))
            if outcome == "processed":
                wait = delay_processed
            elif outcome == "error":
                wait = delay_processed
            if outcome != last_outcome and outcome in ("idle", "paused"):
                logger.info("Cola %s: en espera", "vacía o IA apagada" if outcome == "idle" else "en pausa")
            last_outcome = outcome
        except Exception:  # noqa: BLE001 - una iteración fallida no debe tumbar el worker
            logger.exception("Falló una iteración del worker; continúa")
        time.sleep(wait)


if __name__ == "__main__":
    run_forever()
