"""
Servizio di ricerca email assistenza tecnica del produttore.

Usato da:
  - GET /machine-types/manufacturer-email (pannello admin + SafetyCard)

Strategia:
  1. Cache in-process per brand già cercati (evita query duplicate nella stessa sessione)
  2. Web search con query Italia-first
  3. Fetch pagina contatti + regex email con ranking Italia-first
  4. Fallback AI se nessuna email trovata via regex

Priorità email restituite:
  1. Dominio .it (assistenza@brand.it)
  2. Prefisso Italy/Italia (italy@brand.com, it.service@brand.com)
  3. Prefisso service/assistenza/support/after-sales
  4. Qualsiasi email tecnica (escluso noreply, privacy, marketing, ecc.)
  5. info@ come ultimo fallback
"""

import re
import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Cache in-process: brand.lower() → email trovata (o None se non trovata)
_email_cache: dict[str, Optional[str]] = {}

# Pattern regex email
_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')

# Prefissi — ora in DB (config_lists). Fallback statici usati se DB non disponibile.
_FB_REJECT_PREFIXES = {
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "privacy", "gdpr", "dpo", "legal", "compliance",
    "marketing", "press", "media", "pr", "comunicazione",
    "hr", "careers", "lavora", "jobs", "recruiting",
    "billing", "fatturazione", "amministrazione",
    "webmaster", "admin",
}
_FB_IT_PREFIXES = {"italy", "italia", "it.service", "it.support", "it.assistenza", "assistenza.it"}
_FB_SERVICE_PREFIXES = {
    "service", "assistenza", "support", "supporto", "tecnico", "tecnica",
    "after-sales", "aftersales", "post-vendita", "postvend",
    "customer.service", "customerservice", "helpdesk", "help-desk",
    "workshop", "officina",
}


def _reject_prefixes() -> set:
    from app.services.config_service import get_list
    return get_list("email_reject_prefixes", _FB_REJECT_PREFIXES)


def _it_prefixes() -> set:
    from app.services.config_service import get_list
    return get_list("email_it_prefixes", _FB_IT_PREFIXES)


def _service_prefixes() -> set:
    from app.services.config_service import get_list
    return get_list("email_service_prefixes", _FB_SERVICE_PREFIXES)


def _score_email(email: str) -> int:
    """
    Punteggio di preferenza (più alto = meglio).
    100 = dominio .it
    80  = prefisso Italia
    60  = prefisso service/assistenza
    20  = qualsiasi email tecnica accettabile
    10  = info@
    -1  = da scartare
    """
    local, domain = email.lower().split("@", 1)
    rej = _reject_prefixes()
    # Scarta
    if local in rej or any(local.startswith(p) for p in rej):
        return -1
    # Dominio .it
    if domain.endswith(".it"):
        return 100
    # Prefisso Italia
    it_p = _it_prefixes()
    if any(local == p or local.startswith(p) for p in it_p):
        return 80
    # Prefisso service/assistenza
    svc_p = _service_prefixes()
    if any(local == p or local.startswith(p) for p in svc_p):
        return 60
    # info@ come fallback
    if local == "info":
        return 10
    # Qualsiasi altra email accettabile
    return 20


def _extract_best_email(text: str) -> Optional[str]:
    """Estrae la miglior email assistenza tecnica da un testo HTML/plain."""
    found = _EMAIL_RE.findall(text)
    if not found:
        return None
    scored = [(email, _score_email(email)) for email in found]
    scored = [(e, s) for e, s in scored if s > 0]
    if not scored:
        return None
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0][0]


async def _fetch_page_text(url: str) -> Optional[str]:
    """Scarica una pagina web e restituisce il testo (strippato da tag HTML)."""
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; ManualFinder/1.0)"})
            if resp.status_code != 200:
                return None
            html = resp.text
            # Strip tag HTML
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text)
            return text[:6000]
    except Exception:
        return None


async def _find_via_web_search(brand: str, provider: str) -> Optional[str]:
    """
    Cerca tramite web search le pagine contatti del produttore, Italia-first.
    Tenta query in ordine di priorità e si ferma alla prima che produce un'email.
    """
    from app.services.search_service import _search_with_provider

    brand_norm = brand.strip()
    queries = [
        f'"{brand_norm}" Italy assistenza tecnica contatti email',
        f'"{brand_norm}" Italia service email assistenza',
        f'"{brand_norm}" contatti assistenza tecnica email',
        f'"{brand_norm}" contact service email support',
    ]

    for query in queries:
        try:
            results = await _search_with_provider(query, provider)
            for r in results[:3]:
                # Prova prima a estrarre l'email dallo snippet (veloce, senza fetch)
                if r.snippet:
                    email = _extract_best_email(r.snippet)
                    if email and _score_email(email) >= 20:
                        logger.debug("manufacturer_email: trovata via snippet per %s: %s", brand, email)
                        return email
                # Altrimenti fetch la pagina
                text = await _fetch_page_text(r.url)
                if text:
                    email = _extract_best_email(text)
                    if email and _score_email(email) >= 20:
                        logger.debug("manufacturer_email: trovata via fetch per %s: %s", brand, email)
                        return email
        except Exception:
            continue

    return None


async def _find_via_ai(brand: str, text: str, provider: str) -> Optional[str]:
    """Usa l'AI per estrarre l'email di assistenza tecnica italiana da un testo di pagina."""
    try:
        from app.services.analysis_service import _call_ai_with_text
        prompt = (
            f"Dal testo seguente della pagina web di {brand}, "
            "trova l'indirizzo email del servizio assistenza tecnica ITALIANO "
            "o del supporto post-vendita per l'Italia. "
            "Se non c'è un riferimento italiano specifico, trova l'email del servizio assistenza tecnica generale. "
            "Rispondi SOLO con l'indirizzo email (es: italy.service@brand.com). "
            "Se non trovi nessuna email di assistenza tecnica, rispondi: null"
        )
        result = await _call_ai_with_text(text, prompt, provider)
        # _call_ai_with_text ritorna un dict; per questa chiamata semplice gestiamo la risposta raw
        # Proviamo prima con il campo "email" o estraiamo dalla risposta raw
        if isinstance(result, dict):
            raw = str(result)
        else:
            raw = str(result)
        match = _EMAIL_RE.search(raw)
        if match and _score_email(match.group()) > 0:
            return match.group()
    except Exception as e:
        logger.debug("manufacturer_email: AI fallback fallito per %s: %s", brand, e)
    return None


async def find_manufacturer_email(brand: str, provider: str) -> Optional[str]:
    """
    Trova l'email di assistenza tecnica italiana del produttore.
    Risultato messo in cache per brand (per la durata della sessione).

    Ritorna: indirizzo email (str) o None se non trovato.
    """
    if not brand or not brand.strip():
        return None

    cache_key = brand.lower().strip()
    if cache_key in _email_cache:
        logger.debug("manufacturer_email: cache hit per %s → %s", brand, _email_cache[cache_key])
        return _email_cache[cache_key]

    logger.info("manufacturer_email: ricerca email per '%s'", brand)
    email = await _find_via_web_search(brand, provider)

    if not email:
        logger.info("manufacturer_email: nessuna email trovata via web per '%s'", brand)

    _email_cache[cache_key] = email
    return email
