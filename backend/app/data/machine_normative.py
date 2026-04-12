"""
Normative applicabili per tipo macchina.

Design post-migrazione:
  - Le normative sono in DB (tabella machine_type_normative).
  - _NORMATIVE_MAP_SEED e _ALWAYS_APPLICABLE_SEED: usati SOLO da
    _seed_normative_if_empty() al primo avvio; non usati a runtime.
  - get_normative(machine_type) / get_normative_by_id(id): leggono da DB con cache.
"""
from typing import List, Optional
import logging
import threading
import time as _time

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Dati seed — usati SOLO dalla funzione di seed al primo avvio
# ─────────────────────────────────────────────────────────────────────────────

_ALWAYS_APPLICABLE_SEED: List[str] = [
    "Direttiva Macchine 2006/42/CE (D.Lgs. 17/2010)",
    "UNI EN ISO 12100:2010 — Sicurezza del macchinario: principi generali di progettazione",
    "D.Lgs. 81/2008 — Testo Unico Sicurezza sul Lavoro",
]

_NORMATIVE_MAP_SEED: dict[str, List[str]] = {
    "piattaforma aerea": [
        "EN 280:2013+A1:2015 — PLE con braccio mobile",
        "EN 1570-1:2011+A1:2014 — Tavole elevatori",
        "EN ISO 18878:2013 — Piattaforme elevabili mobili di lavoro: addestramento degli operatori",
        "D.Lgs. 81/2008 Allegato V e VII (verifiche periodiche annuali INAIL/ASL)",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori PLE (con/senza stabilizzatori)",
        "Circ. Min. Lav. 30/2011 — Modalità di effettuazione delle verifiche periodiche",
    ],
    "piattaforma a forbice": [
        "EN 1570-1:2011+A1:2014 — Tavole elevatori",
        "EN 280:2013+A1:2015 — PLE (se con braccio mobile)",
        "D.Lgs. 81/2008 Allegato V e VII",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori PLE",
    ],
    "carrello elevatore": [
        "EN ISO 3691-1:2015+A1:2020 — Carrelli industriali semoventi",
        "EN ISO 3691-4:2020 — Carrelli industriali senza conducente",
        "EN ISO 3691-5:2009 — Carrelli a presa anteriore con braccio telescopico",
        "EN 1551:2017 — Carrelli industriali con portata > 10 t",
        "D.Lgs. 81/2008 Allegato V e VII",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori carrelli elevatori",
    ],
    "sollevatore telescopico": [
        "EN ISO 3691-5:2009 — Carrelli a presa anteriore con braccio telescopico",
        "EN 1459-1:2017+A1:2020 — Carrelli telescopici",
        "D.Lgs. 81/2008 Allegato V e VII",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori carrelli telescopici",
    ],
    "gru mobile": [
        "EN 13000:2010+A1:2014 — Gru mobili",
        "EN 12999:2011+A1:2012 — Gru caricatrici",
        "UNI EN ISO 12100:2010",
        "D.Lgs. 81/2008 Allegato V e VII (verifica annuale/biennale INAIL)",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori gru mobili",
        "D.M. 11/04/2011 — Criteri generali verifica periodica attrezzature",
    ],
    "gru a torre": [
        "EN 14439:2009+A2:2011 — Gru a torre",
        "UNI EN ISO 12100:2010",
        "D.Lgs. 81/2008 Allegato V e VII",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori gru a torre",
    ],
    "gru": [
        "EN 13000:2010+A1:2014 — Gru mobili",
        "EN 14439:2009+A2:2011 — Gru a torre",
        "EN 13157:2004+A1:2009 — Gru azionate a mano",
        "D.Lgs. 81/2008 Allegato V e VII",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori gru",
    ],
    "escavatore": [
        "EN 474-1:2006+A4:2013 — Macchine per movimento terra: requisiti generali",
        "EN 474-5:2006+A3:2013 — Escavatori idraulici",
        "UNI EN ISO 12100:2010",
        "D.Lgs. 81/2008 Allegato V",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori escavatori idraulici/a fune",
    ],
    "pala caricatrice": [
        "EN 474-1:2006+A4:2013 — Requisiti generali macchine movimento terra",
        "EN 474-3:2006+A2:2012 — Pale caricatrici",
        "UNI EN ISO 12100:2010",
        "D.Lgs. 81/2008 Allegato V",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori pale caricatrici",
    ],
    "terna": [
        "EN 474-1:2006+A4:2013 — Requisiti generali",
        "EN 474-4:2006+A2:2012 — Terne",
        "UNI EN ISO 12100:2010",
        "D.Lgs. 81/2008 Allegato V",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori terne",
    ],
    "retroescavatore": [
        "EN 474-1:2006+A4:2013",
        "EN 474-4:2006+A2:2012 — Terne",
        "D.Lgs. 81/2008 Allegato V",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori terne",
    ],
    "bulldozer": [
        "EN 474-1:2006+A4:2013",
        "EN 474-2:2006+A1:2008 — Bulldozer",
        "D.Lgs. 81/2008 Allegato V",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori",
    ],
    "compressore": [
        "EN 1012-1:2010 — Compressori e pompe a vuoto: requisiti di sicurezza",
        "PED 2014/68/UE (Direttiva Attrezzature in Pressione) — se applicabile",
        "D.Lgs. 81/2008 Allegato V e VII (recipienti in pressione)",
        "D.M. 01/12/2004 n. 329 — Messa in servizio attrezzature a pressione",
    ],
    "generatore": [
        "EN IEC 60034-1:2010 — Macchine elettriche rotanti",
        "EN IEC 60204-1:2018 — Sicurezza macchine: equipaggiamento elettrico",
        "D.Lgs. 81/2008 Allegato V",
        "D.M. 37/2008 — Impianti elettrici nei cantieri",
    ],
    "pompa calcestruzzo": [
        "EN 12001:2012 — Macchine per convogliare calcestruzzo",
        "UNI EN ISO 12100:2010",
        "D.Lgs. 81/2008 Allegato V e VII",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori pompe calcestruzzo",
    ],
    "dumper": [
        "EN 474-1:2006+A4:2013",
        "EN 474-6:2006+A1:2009 — Dumper",
        "D.Lgs. 81/2008 Allegato V",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori dumper",
    ],
    "rullo compattatore": [
        "EN 500-1:2006+A1:2009 — Macchine per la costruzione di strade: requisiti generali",
        "EN 500-4:2011 — Rulli compattatori",
        "D.Lgs. 81/2008 Allegato V",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori rulli compattatori",
    ],
    "betoniera": [
        "EN 14268:2004+A1:2009 — Mescolatori per calcestruzzo",
        "UNI EN ISO 12100:2010",
        "D.Lgs. 81/2008 Allegato V",
    ],
    "pressa piegatrice": [
        "EN 12622:2009+A1:2013 — Sicurezza macchine utensili: presse piegatrici idrauliche",
        "EN ISO 13849-1:2015 — Sicurezza del macchinario: parti dei sistemi di comando",
        "UNI EN ISO 12100:2010",
        "D.Lgs. 81/2008 Allegato V",
    ],
    "saldatrice": [
        "EN 60974-1:2012+A1:2017 — Apparecchi per saldatura ad arco",
        "EN 60974-9:2010 — Installazione e uso",
        "UNI EN ISO 12100:2010",
        "D.Lgs. 81/2008 Allegato V",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Seed — chiamata da main.py al primo avvio (idempotente)
# ─────────────────────────────────────────────────────────────────────────────

def _seed_normative_if_empty() -> None:
    """
    Popola machine_type_normative da _NORMATIVE_MAP_SEED.
    Eseguito solo se la tabella è vuota.
    """
    try:
        from app.config import settings
        import psycopg2
        if not settings.database_url:
            return
        conn = psycopg2.connect(settings.database_url)
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM machine_type_normative")
            count = cur.fetchone()[0]
        if count > 0:
            conn.close()
            logger.info("machine_normative: tabella già popolata (%d norme)", count)
            return
        from app.services.machine_type_service import resolve_machine_type_id
        inserted = 0
        with conn.cursor() as cur:
            # Norme globali (machine_type_id = NULL)
            for i, norm in enumerate(_ALWAYS_APPLICABLE_SEED):
                cur.execute(
                    """
                    INSERT INTO machine_type_normative (machine_type_id, norm_text, display_order)
                    VALUES (NULL, %s, %s)
                    """,
                    (norm, i),
                )
                inserted += 1
            # Norme specifiche per tipo
            for type_name, norms in _NORMATIVE_MAP_SEED.items():
                mt_id = resolve_machine_type_id(type_name)
                if mt_id is None:
                    logger.warning("machine_normative: seed — nessun ID per '%s'", type_name)
                    continue
                for i, norm in enumerate(norms):
                    cur.execute(
                        """
                        INSERT INTO machine_type_normative (machine_type_id, norm_text, display_order)
                        VALUES (%s, %s, %s)
                        """,
                        (mt_id, norm, i),
                    )
                    inserted += 1
        conn.commit()
        conn.close()
        logger.info("machine_normative: seed completato (%d norme inserite)", inserted)
    except Exception as e:
        logger.warning("machine_normative: _seed_normative_if_empty fallito: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# Cache in-memory
# ─────────────────────────────────────────────────────────────────────────────

_cache_by_id: dict[Optional[int], List[str]] = {}  # None = norme globali
_cache_global: Optional[List[str]] = None
_cache_ts: float = 0.0
_cache_lock = threading.Lock()
_CACHE_TTL = 900  # 15 minuti


def _is_cache_valid() -> bool:
    return _time.monotonic() - _cache_ts < _CACHE_TTL


def _load_cache() -> None:
    """Ricarica cache da DB."""
    global _cache_by_id, _cache_global, _cache_ts
    try:
        from app.config import settings
        import psycopg2
        if not settings.database_url:
            return
        conn = psycopg2.connect(settings.database_url)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT machine_type_id, norm_text FROM machine_type_normative "
                "WHERE is_active = true ORDER BY machine_type_id NULLS FIRST, display_order"
            )
            rows = cur.fetchall()
        conn.close()
        new_cache: dict[Optional[int], List[str]] = {}
        for mt_id, norm_text in rows:
            key = mt_id  # None per globali
            if key not in new_cache:
                new_cache[key] = []
            new_cache[key].append(norm_text)
        with _cache_lock:
            _cache_by_id = new_cache
            _cache_global = new_cache.get(None, [])
            _cache_ts = _time.monotonic()
    except Exception as e:
        logger.debug("machine_normative: _load_cache fallito: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# API pubblica
# ─────────────────────────────────────────────────────────────────────────────

def get_normative_by_id(machine_type_id: int) -> List[str]:
    """
    Restituisce le normative per il tipo macchina identificato da ID.
    Include le norme globali (machine_type_id = NULL).
    Cache in-memory 15 min.
    """
    with _cache_lock:
        if not _is_cache_valid():
            pass
        elif None in _cache_by_id:  # cache valida e popolata
            global_norms = _cache_global or []
            specific = _cache_by_id.get(machine_type_id, [])
            seen = set()
            result = []
            for n in global_norms + specific:
                if n not in seen:
                    seen.add(n)
                    result.append(n)
            return result

    # Cache non valida o vuota: ricarica
    _load_cache()

    with _cache_lock:
        global_norms = _cache_global or _ALWAYS_APPLICABLE_SEED
        specific = _cache_by_id.get(machine_type_id, [])
        seen = set()
        result = []
        for n in global_norms + specific:
            if n not in seen:
                seen.add(n)
                result.append(n)
        return result


def get_normative(machine_type: str) -> List[str]:
    """
    Restituisce le normative applicabili per il tipo macchina (testo libero).
    Risolve il testo a ID tramite machine_type_service, poi delega a get_normative_by_id().
    Fallback: solo norme globali.
    """
    try:
        from app.services.machine_type_service import resolve_machine_type_id
        mt_id = resolve_machine_type_id(machine_type or "")
        if mt_id is not None:
            return get_normative_by_id(mt_id)
    except Exception:
        pass
    # Fallback: norme globali dal seed
    with _cache_lock:
        if _is_cache_valid() and _cache_global:
            return list(_cache_global)
    return list(_ALWAYS_APPLICABLE_SEED)
