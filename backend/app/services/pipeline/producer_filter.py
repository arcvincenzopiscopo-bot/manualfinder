"""
Filtraggio dei candidati produttore prima del download.
Rimuove URL e titoli palesemente non industriali o non pertinenti.
Estratto da analyze._pipeline per migliorare la testabilità.
"""
from __future__ import annotations
import logging
from typing import Optional

_logger = logging.getLogger(__name__)


def is_industrial_url(url: str, machine_type: Optional[str] = None) -> bool:
    """
    Restituisce True se l'URL è plausibilmente un manuale industriale.
    Scarta domini non-industriali (ospedali, scuole, uffici, cataloghi puri).
    """
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.lower()
    full = domain + path

    NON_INDUSTRIAL_DOMAINS = [
        "ospedale", "hospital", "clinic", "sanit", "medic", "salute",
        "infermier", "farmac", "bambin", "pediatr",
        "universit", "scuola", "school", "college", "accadem", "istruzion",
        "news", "giornale", "corriere", "gazzett", "notizie", "stampa",
        "comune.", "provincia.", "regione.", "governo.", "pubblica-amminist",
        "tribunale", "prefettura", "questura",
    ]
    if any(p in domain for p in NON_INDUSTRIAL_DOMAINS):
        return False

    OFFICE_EQUIPMENT = [
        "ricoh", "canon", "epson", "brother", "xerox", "konica", "kyocera",
        "streampunch", "laminator", "shredder", "binder", "binding",
        "fellowes", "gbc.com", "acco.", "leitz", "rexel",
        "printer", "copier", "scanner", "fax",
    ]
    if any(p in full for p in OFFICE_EQUIPMENT):
        return False

    CATALOG_URL_SIGNALS = [
        "tooling_catalog", "tooling-catalog", "tooling_guide",
        "parts_catalog", "parts-catalog", "spare_parts",
        "catalogo_ricambi", "catalogo_attrezzature", "catalogo_utensili",
        "price_list", "listino_prezzi",
        "depliant", "flyer", "leaflet",
        "product-line", "product_line", "productline", "lineup", "line-up",
        "tv-product", "range-overview", "portfolio",
    ]
    if any(p in path.replace(" ", "_").replace("%20", "_") for p in CATALOG_URL_SIGNALS):
        return False

    try:
        from app.services.search_service import _EXCLUDE_DOMAINS
        if any(d in domain for d in _EXCLUDE_DOMAINS):
            return False
    except Exception:
        pass

    # Regole dinamiche apprese dai feedback ispettori (cache 15 min)
    try:
        from app.services.feedback_analyzer_service import get_dynamic_rules
        _dyn_domains, _dyn_fragments, _ = get_dynamic_rules()
        if any(d in domain for d in _dyn_domains):
            return False
        if any(f in path for f in _dyn_fragments):
            return False
    except Exception as e:
        _logger.debug("dynamic rules non disponibili: %s", e)

    # URL segnalati dagli ispettori
    try:
        from app.services.saved_manuals_service import (
            get_blocked_urls, get_context_blocked_urls
        )
        if url in get_blocked_urls():
            return False
        if machine_type:
            mt_lower = machine_type.lower().strip()
            if (url, mt_lower) in get_context_blocked_urls():
                return False
    except Exception as e:
        _logger.debug("blocked urls non disponibili: %s", e)

    return True


def title_is_plausible(candidate, brand: str) -> bool:
    """
    Restituisce True se il titolo del candidato non contraddice il brand cercato.
    Scarta risultati con brand chiaramente estranei (es. stampanti Ricoh in una
    ricerca di escavatori Komatsu).
    """
    title = candidate.title.lower()
    brand_l = brand.lower()
    try:
        from app.services.config_service import get_list as _get_list
        _office_brands = _get_list("office_brands_in_title", {
            "ricoh", "canon", "epson", "brother", "xerox", "konica", "kyocera",
            "streampunch", "fellowes", "leitz", "rexel", "acco", "dymo",
            "samsung", "lg", "sony", "philips", "siemens home",
        })
    except Exception:
        _office_brands = set()
    if any(b in title for b in _office_brands):
        return brand_l in title
    return True


def filter_producer_candidates(
    candidates: list,
    brand: str,
    model: str,
    machine_type: Optional[str] = None,
) -> list:
    """
    Applica entrambi i filtri (industrial URL + title plausibility) ai candidati produttore.
    """
    result = [c for c in candidates if is_industrial_url(c.url, machine_type=machine_type)]
    result = [c for c in result if title_is_plausible(c, brand)]
    return result
