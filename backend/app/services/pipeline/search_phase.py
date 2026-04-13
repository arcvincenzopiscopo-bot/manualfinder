"""
Fase 1 della pipeline analyze: ricerca manuali e safety alert.
Estratto da routers/analyze._pipeline per testabilità e leggibilità.
"""
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

_logger = logging.getLogger(__name__)


# ── Helpers anno ──────────────────────────────────────────────────────────────

def compute_year_flags(machine_year: Optional[str]) -> tuple[bool, bool]:
    """
    Ritorna (is_ante_ce, is_allegato_v) in base all'anno macchina.
    - is_allegato_v: costruita ante 1996 (ante prima Direttiva Macchine DPR 459/96)
    - is_ante_ce:    costruita 1996-2005 (vecchia direttiva 98/37/CE)
    """
    if not machine_year:
        return False, False
    try:
        year_int = int(machine_year)
        is_allegato_v = year_int < 1996
        is_ante_ce = 1996 <= year_int < 2006
        return is_ante_ce, is_allegato_v
    except (ValueError, TypeError):
        return False, False


def build_search_start_message(
    brand: str,
    model: str,
    machine_type: Optional[str],
    machine_year: Optional[str],
    is_ante_ce: bool,
    is_allegato_v: bool,
) -> str:
    msg = f"Ricerca manuale per {brand} {model}"
    if machine_type:
        msg += f" (tipo: {machine_type})"
    if machine_year:
        msg += f", anno {machine_year}"
        if is_allegato_v:
            msg += " ⚠ Allegato V D.Lgs.81"
        elif is_ante_ce:
            msg += " ⚠ Dir. 98/37/CE (ante 2006/42/CE)"
    return msg + "..."


# ── Risultato ─────────────────────────────────────────────────────────────────

@dataclass
class SearchPhaseResult:
    search_results: list = field(default_factory=list)
    search_warnings: list = field(default_factory=list)
    safety_alerts: list = field(default_factory=list)
    safety_alerts_data: list = field(default_factory=list)
    pdf_candidates: list = field(default_factory=list)
    local_manual_found: bool = False
    search_message: str = ""


# ── Funzione principale ───────────────────────────────────────────────────────

async def run_search_phase(
    brand: str,
    model: str,
    machine_type: Optional[str],
    machine_type_id: Optional[int],
    machine_year: Optional[str],
    serial_number: Optional[str],
    preferred_language: str,
    has_local_inail: bool,
    qr_url: Optional[str],
) -> SearchPhaseResult:
    """
    Esegue ricerca manuale + safety alerts in parallelo con timeout individuali.
    Ritorna SearchPhaseResult con tutti i dati necessari al passo successivo.
    """
    from app.services import search_service, safety_gate_service

    async def _search_with_timeout():
        try:
            results, warnings = await asyncio.wait_for(
                search_service.search_manual(
                    brand=brand,
                    model=model,
                    machine_type=machine_type,
                    lang=preferred_language,
                    machine_year=machine_year,
                    serial_number=serial_number,
                    machine_type_id=machine_type_id,
                    has_local_inail=has_local_inail,
                ),
                timeout=120,
            )
            return results, warnings
        except asyncio.TimeoutError:
            _logger.warning("search_manual timeout (120s) per %s %s", brand, model)
            return [], ["⏱ Timeout ricerca (120s): il provider di ricerca non ha risposto in tempo."]
        except Exception as e:
            _logger.warning("search_manual errore per %s %s: %s", brand, model, e)
            return [], [f"❌ Errore ricerca: {e}"]

    async def _alerts_with_timeout():
        try:
            return await asyncio.wait_for(
                safety_gate_service.check_safety_alerts(brand, model),
                timeout=30,
            )
        except asyncio.TimeoutError:
            _logger.warning("check_safety_alerts timeout (30s) per %s %s", brand, model)
            return []
        except Exception:
            return []

    (search_results, search_warnings), safety_alerts = await asyncio.gather(
        _search_with_timeout(),
        _alerts_with_timeout(),
    )

    pdf_candidates = [r for r in search_results if r.is_pdf]

    local_manual_found = has_local_inail or any(
        r.source_type == "inail" and "Locale" in r.title for r in search_results
    )

    # Costruisce il messaggio di completamento
    search_message = f"Trovati {len(search_results)} risultati ({len(pdf_candidates)} PDF)."
    if qr_url:
        search_message = "QR Code rilevato sulla targa — link diretto al manuale. " + search_message
    if has_local_inail:
        search_message = (
            f"Manuale INAIL locale disponibile per '{machine_type}' — ricerca INAIL online saltata. "
            + search_message
        )

    safety_alerts_data = [a.to_dict() for a in safety_alerts] if safety_alerts else []
    if safety_alerts:
        serious = [a for a in safety_alerts if a.risk_level == "serious"]
        alert_msg = f" ⚠ ATTENZIONE: {len(safety_alerts)} avviso/i Safety Gate EU"
        if serious:
            alert_msg = f" 🚨 ALERT: {len(serious)} avviso GRAVE Safety Gate EU per {brand} {model}!"
        search_message += alert_msg

    return SearchPhaseResult(
        search_results=search_results,
        search_warnings=search_warnings,
        safety_alerts=safety_alerts,
        safety_alerts_data=safety_alerts_data,
        pdf_candidates=pdf_candidates,
        local_manual_found=local_manual_found,
        search_message=search_message,
    )
