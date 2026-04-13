"""
Helper per uniformare la gestione degli errori nei router e nei service.

- internal_error / service_unavailable: per router, evita info-disclosure.
- log_and_swallow: per service che devono swalloware eccezioni senza silenzio totale.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException


def internal_error(
    logger: logging.Logger,
    exc: BaseException,
    *,
    context: str = "",
    status_code: int = 500,
    public_message: Optional[str] = None,
) -> HTTPException:
    """
    Logga l'eccezione con stack trace e ritorna un HTTPException con messaggio
    generico per il client. Uso tipico nei router:

        try:
            ...
        except Exception as e:
            raise internal_error(logger, e, context="upsert prompt rule")

    Args:
        logger: logger del modulo chiamante.
        exc: l'eccezione catturata.
        context: breve descrizione dell'operazione, usata nel log.
        status_code: HTTP status da restituire (default 500).
        public_message: messaggio generico per il client; se omesso, default
                        in base al codice (503 → servizio non disponibile,
                        altri → errore interno).
    """
    logger.exception("%s: %s", context or "errore interno", exc)
    if public_message is None:
        if status_code == 503:
            public_message = "Servizio non disponibile"
        elif status_code == 400:
            public_message = "Richiesta non valida"
        else:
            public_message = "Errore interno"
    return HTTPException(status_code=status_code, detail=public_message)


def log_and_swallow(
    logger: logging.Logger,
    exc: BaseException,
    *,
    context: str = "",
    level: int = logging.WARNING,
) -> None:
    """
    Logga l'eccezione e la inghiotte. Per i service che usano `except: pass`.

        try:
            ...
        except Exception as e:
            log_and_swallow(logger, e, context="resolve machine type")
    """
    logger.log(level, "%s: %s", context or "swallowed", exc, exc_info=(level >= logging.ERROR))


def service_unavailable(
    logger: logging.Logger,
    exc: BaseException,
    *,
    context: str = "",
    public_message: Optional[str] = None,
) -> HTTPException:
    """Scorciatoia per errori 503 (es. DB offline, RuntimeError di config)."""
    return internal_error(
        logger, exc, context=context, status_code=503, public_message=public_message
    )
