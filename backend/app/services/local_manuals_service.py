"""
Servizio per la gestione dei manuali locali INAIL.

Design post-migrazione:
  - Le associazioni macchina → PDF sono in DB (tabella inail_manual_assignments).
  - Gli alias macchina sono in DB (tabella machine_aliases).
  - find_local_manual(machine_type, machine_type_id): lookup per ID → testo → disco.
  - I dict _LOCAL_MANUALS_MAP_SEED e _MACHINE_ALIASES_SEED sono usati SOLO dalle
    funzioni di seed al primo avvio; non vengono usati a runtime.
"""
from typing import Optional, Dict, List
from pathlib import Path
import re as _re
import logging

logger = logging.getLogger(__name__)

# Percorso della cartella PDF manuali.
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # manualfinder/
_BACKEND_ROOT  = Path(__file__).parent.parent.parent         # backend/
_root_dir    = _PROJECT_ROOT / "pdf manuali"
_backend_dir = _BACKEND_ROOT / "pdf manuali"
PDF_MANUALS_DIR = _root_dir if _root_dir.exists() else _backend_dir


# ─────────────────────────────────────────────────────────────────────────────
# Dati seed — usati SOLO da _seed_local_aliases_into_db() e
# _seed_inail_assignments_if_empty() al primo avvio.
# A runtime il sistema usa esclusivamente le tabelle DB.
# ─────────────────────────────────────────────────────────────────────────────

_LOCAL_MANUALS_MAP_SEED: Dict[str, str] = {
    "gru a torre":                          "Scheda 1 - GRU A TORRE.pdf",
    "gru su autocarro":                     "Scheda 2 - GRU SU AUTOCARRO.pdf",
    "piattaforma aerea":                    "Scheda 3 - PIATTAFORME MOBILI DI LAVORO ELEVABILI.pdf",
    "ascensore da cantiere":                "Scheda 4 - ASCENSORE DI CANTIERE.pdf",
    "carrello elevatore telescopico":       "Scheda 5 - CARRELLO ELEVATORE TELESCOPICO.pdf",
    "escavatore idraulico":                 "Scheda 6 - ESCAVATORE IDRAULICO.pdf",
    "pala caricatrice frontale":            "Scheda 7 - PALA CARICATRICE FRONTALE.pdf",
    "rullo compattatore":                   "Scheda 8 - RULLO COMPATTATORE.pdf",
    "finitrice":                            "Scheda 9 - FINITRICE.pdf",
    "perforatrice micropali":               "Scheda 10 - PERFORATRICE MICROPALI.pdf",
    "betoniera":                            "Scheda 11 - BETONIERA.pdf",
    "sega circolare":                       "Scheda 12 - SEGA CIRCOLARE.pdf",
    "taglialaterizi":                       "Scheda 13 - TAGLIALATERIZI.pdf",
    "elevatore a bandiera":                 "Scheda 14 - ELEVATORE A BANDIERA.pdf",
    "piastra vibrante":                     "Scheda 15 - PIASTRA VIBRANTE.pdf",
    "tagliasfalto":                         "Scheda 16 - TAGLIASFALTO A DISCO.pdf",
    "carotatrice":                          "Scheda 17 - CAROTATRICE.pdf",
    "decespugliatore":                      "Scheda 18 - DECESPUGLIATORE.pdf",
    "troncatrice":                          "Scheda 19 - TRONCATRICE PORTATILE A DISCO.pdf",
    "motosega":                             "Scheda 20 - MOTOSEGA.pdf",
    "trattore agricolo":                    "Scheda 21 - TRATTORI AGRICOLI.pdf",
    "macchina movimento terra":             "Scheda 22 - MOVIMENTO TERRA.pdf",
}

_MACHINE_ALIASES_SEED: Dict[str, str] = {
    # ── GRU A TORRE ──────────────────────────────────────────────────────────
    "gru a torre":                          "gru a torre",
    "gru":                                  "gru a torre",
    "tower crane":                          "gru a torre",
    "top-slewing crane":                    "gru a torre",
    "top slewing crane":                    "gru a torre",
    "self-erecting crane":                  "gru a torre",
    # ── GRU SU AUTOCARRO ─────────────────────────────────────────────────────
    "gru su autocarro":                     "gru su autocarro",
    "camion gru":                           "gru su autocarro",
    "gru mobile":                           "gru su autocarro",
    "gru cingolata":                        "gru su autocarro",
    "gru semovente":                        "gru su autocarro",
    "mobile crane":                         "gru su autocarro",
    "truck crane":                          "gru su autocarro",
    "crawler crane":                        "gru su autocarro",
    "loader crane":                         "gru su autocarro",
    "knuckle boom crane":                   "gru su autocarro",
    "gru a braccio":                        "gru su autocarro",
    "gru idraulica":                        "gru su autocarro",
    # ── PIATTAFORME AEREE ─────────────────────────────────────────────────────
    "piattaforma aerea":                    "piattaforma aerea",
    "piattaforma":                          "piattaforma aerea",
    "ple":                                  "piattaforma aerea",
    "piattaforma mobile elevabile":         "piattaforma aerea",
    "piattaforma mobile di lavoro elevabile": "piattaforma aerea",
    "piattaforma a forbice":                "piattaforma aerea",
    "piattaforma aerea a braccio":          "piattaforma aerea",
    "piattaforma aerea a forbice":          "piattaforma aerea",
    "piattaforma semovente":                "piattaforma aerea",
    "autoscala":                            "piattaforma aerea",
    "aerial work platform":                 "piattaforma aerea",
    "aerial platform":                      "piattaforma aerea",
    "boom lift":                            "piattaforma aerea",
    "scissor lift":                         "piattaforma aerea",
    "mewp":                                 "piattaforma aerea",
    "awp":                                  "piattaforma aerea",
    "platform":                             "piattaforma aerea",
    # ── ASCENSORE DA CANTIERE ─────────────────────────────────────────────────
    "ascensore da cantiere":                "ascensore da cantiere",
    "ascensore di cantiere":                "ascensore da cantiere",
    "ascensori da cantiere":                "ascensore da cantiere",
    "ascensori di cantiere":                "ascensore da cantiere",
    "ascensore cantiere":                   "ascensore da cantiere",
    "elevatore da cantiere":                "ascensore da cantiere",
    "elevatore di cantiere":                "ascensore da cantiere",
    "montacarichi da cantiere":             "ascensore da cantiere",
    "montacarichi":                         "ascensore da cantiere",
    "ponteggio elevatore":                  "ascensore da cantiere",
    "hoist":                                "ascensore da cantiere",
    "construction hoist":                   "ascensore da cantiere",
    "builder's hoist":                      "ascensore da cantiere",
    "personnel hoist":                      "ascensore da cantiere",
    # ── ELEVATORE A BANDIERA ─────────────────────────────────────────────────
    "elevatore a bandiera":                 "elevatore a bandiera",
    "elevatore":                            "elevatore a bandiera",
    "paranco":                              "elevatore a bandiera",
    "argano":                               "elevatore a bandiera",
    "hoisting winch":                       "elevatore a bandiera",
    # ── CARRELLO ELEVATORE TELESCOPICO ───────────────────────────────────────
    "carrello elevatore telescopico":       "carrello elevatore telescopico",
    "carrello elevatore":                   "carrello elevatore telescopico",
    "sollevatore telescopico":              "carrello elevatore telescopico",
    "muletto":                              "carrello elevatore telescopico",
    "carrello telescopico":                 "carrello elevatore telescopico",
    "carrello elevatore a contrappeso":     "carrello elevatore telescopico",
    "carrello elevatore retrattile":        "carrello elevatore telescopico",
    "carrello elevatore laterale":          "carrello elevatore telescopico",
    "carrello elevatore frontale":          "carrello elevatore telescopico",
    "carrello elevatore rotante":           "carrello elevatore telescopico",
    "reach stacker":                        "carrello elevatore telescopico",
    "stacker":                              "carrello elevatore telescopico",
    "carrello portacontenitori":            "carrello elevatore telescopico",
    "sollevatore portacontenitori":         "carrello elevatore telescopico",
    "carrello elevatore pesante":           "carrello elevatore telescopico",
    "heavy forklift":                       "carrello elevatore telescopico",
    "reach truck":                          "carrello elevatore telescopico",
    "forklift":                             "carrello elevatore telescopico",
    "fork lift":                            "carrello elevatore telescopico",
    "telehandler":                          "carrello elevatore telescopico",
    "telescopic handler":                   "carrello elevatore telescopico",
    # ── ESCAVATORE ────────────────────────────────────────────────────────────
    "escavatore idraulico":                 "escavatore idraulico",
    "escavatore":                           "escavatore idraulico",
    "miniescavatore":                       "escavatore idraulico",
    "mini escavatore":                      "escavatore idraulico",
    "escavatore cingolato":                 "escavatore idraulico",
    "escavatore gommato":                   "escavatore idraulico",
    "excavator":                            "escavatore idraulico",
    "mini excavator":                       "escavatore idraulico",
    "hydraulic excavator":                  "escavatore idraulico",
    "backhoe":                              "escavatore idraulico",
    "backhoe loader":                       "escavatore idraulico",
    "terna":                                "escavatore idraulico",
    # ── PALA CARICATRICE ─────────────────────────────────────────────────────
    "pala caricatrice frontale":            "pala caricatrice frontale",
    "pala caricatrice":                     "pala caricatrice frontale",
    "pala caricatrice gommata":             "pala caricatrice frontale",
    "pala meccanica":                       "pala caricatrice frontale",
    "pala":                                 "pala caricatrice frontale",
    "minipala":                             "pala caricatrice frontale",
    "skid steer loader":                    "pala caricatrice frontale",
    "wheel loader":                         "pala caricatrice frontale",
    "front loader":                         "pala caricatrice frontale",
    "loader":                               "pala caricatrice frontale",
    "bulldozer":                            "pala caricatrice frontale",
    "apripista":                            "pala caricatrice frontale",
    # ── RULLO COMPATTATORE ───────────────────────────────────────────────────
    "rullo compattatore":                   "rullo compattatore",
    "rullo compressore":                    "rullo compattatore",
    "rullo":                                "rullo compattatore",
    "compattatore":                         "rullo compattatore",
    "roller":                               "rullo compattatore",
    "road roller":                          "rullo compattatore",
    "compactor":                            "rullo compattatore",
    "vibratory roller":                     "rullo compattatore",
    "drum roller":                          "rullo compattatore",
    "tandem roller":                        "rullo compattatore",
    # ── FINITRICE ────────────────────────────────────────────────────────────
    "finitrice":                            "finitrice",
    "finitrice asfalto":                    "finitrice",
    "finitrice stradale":                   "finitrice",
    "paver":                                "finitrice",
    "asphalt paver":                        "finitrice",
    "asphalt finisher":                     "finitrice",
    "finisher":                             "finitrice",
    # ── PERFORATRICE ─────────────────────────────────────────────────────────
    "perforatrice micropali":               "perforatrice micropali",
    "perforatrice":                         "perforatrice micropali",
    "trivella":                             "perforatrice micropali",
    "trivella da fondazione":               "perforatrice micropali",
    "sonda di perforazione":                "perforatrice micropali",
    "drilling rig":                         "perforatrice micropali",
    "drill rig":                            "perforatrice micropali",
    "drill":                                "perforatrice micropali",
    # ── BETONIERA ────────────────────────────────────────────────────────────
    "betoniera":                            "betoniera",
    "betoniera a caricamento frontale":     "betoniera",
    "pompa calcestruzzo":                   "betoniera",
    "autobetoniera":                        "betoniera",
    "concrete mixer":                       "betoniera",
    "mixer":                                "betoniera",
    "concrete pump":                        "betoniera",
    # ── SEGA CIRCOLARE ───────────────────────────────────────────────────────
    "sega circolare":                       "sega circolare",
    "sega a disco":                         "sega circolare",
    "sega da banco":                        "sega circolare",
    "sega circolare da banco":              "sega circolare",
    "sega":                                 "sega circolare",
    "sega a nastro":                        "sega circolare",
    "circular saw":                         "sega circolare",
    "table saw":                            "sega circolare",
    "band saw":                             "sega circolare",
    "saw":                                  "sega circolare",
    # ── TAGLIALATERIZI ───────────────────────────────────────────────────────
    "taglialaterizi":                       "taglialaterizi",
    "taglia laterizi":                      "taglialaterizi",
    "tagliablocchi":                        "taglialaterizi",
    "block cutter":                         "taglialaterizi",
    "brick cutter":                         "taglialaterizi",
    # ── PIASTRA VIBRANTE ─────────────────────────────────────────────────────
    "piastra vibrante":                     "piastra vibrante",
    "piastra compattante":                  "piastra vibrante",
    "plate compactor":                      "piastra vibrante",
    "vibratory plate":                      "piastra vibrante",
    "rammer":                               "piastra vibrante",
    # ── TAGLIASFALTO ─────────────────────────────────────────────────────────
    "tagliasfalto":                         "tagliasfalto",
    "taglia asfalto":                       "tagliasfalto",
    "tagliasfalto a disco":                 "tagliasfalto",
    "scarifier":                            "tagliasfalto",
    "floor saw":                            "tagliasfalto",
    "road cutter":                          "tagliasfalto",
    # ── CAROTATRICE ──────────────────────────────────────────────────────────
    "carotatrice":                          "carotatrice",
    "carotatrice elettrica":                "carotatrice",
    "coring machine":                       "carotatrice",
    "core drill":                           "carotatrice",
    # ── DECESPUGLIATORE ──────────────────────────────────────────────────────
    "decespugliatore":                      "decespugliatore",
    "brushcutter":                          "decespugliatore",
    "brush cutter":                         "decespugliatore",
    "trimmer":                              "decespugliatore",
    # ── TRONCATRICE ──────────────────────────────────────────────────────────
    "troncatrice":                          "troncatrice",
    "troncatrice portatile":                "troncatrice",
    "troncatrice a disco":                  "troncatrice",
    "cut-off saw":                          "troncatrice",
    "angle grinder":                        "troncatrice",
    "martello demolitore":                  "troncatrice",
    "martello demolitore idraulico":        "troncatrice",
    "jackhammer":                           "troncatrice",
    "breaker":                              "troncatrice",
    # ── MOTOSEGA ─────────────────────────────────────────────────────────────
    "motosega":                             "motosega",
    "chainsaw":                             "motosega",
    "chain saw":                            "motosega",
    # ── TRATTORI AGRICOLI ─────────────────────────────────────────────────────
    "trattore agricolo":                    "trattore agricolo",
    "trattore":                             "trattore agricolo",
    "trattrice":                            "trattore agricolo",
    "trattore a ruote":                     "trattore agricolo",
    "trattore a cingoli":                   "trattore agricolo",
    "agricultural tractor":                 "trattore agricolo",
    "tractor":                              "trattore agricolo",
    # ── MACCHINE MOVIMENTO TERRA ──────────────────────────────────────────────
    "macchina movimento terra":             "macchina movimento terra",
    "movimento terra":                      "macchina movimento terra",
    "dumper":                               "macchina movimento terra",
    "scraper":                              "macchina movimento terra",
    "livellatrice":                         "macchina movimento terra",
    "grader":                               "macchina movimento terra",
    "escavatore a filo":                    "macchina movimento terra",
    "earth moving machine":                 "macchina movimento terra",
    "earthmover":                           "macchina movimento terra",
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers interni
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_machine_type(machine_type: str) -> str:
    return machine_type.lower().strip()


def _extract_canonical_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    name = _re.sub(r'^(?:scheda\s+)?\d+\s*[-–]\s*', '', stem, flags=_re.IGNORECASE)
    return name.lower().strip()


def _get_conn():
    from app.config import settings
    import psycopg2
    return psycopg2.connect(settings.database_url)


def _db_available() -> bool:
    from app.config import settings
    return bool(settings.database_url)


def _make_result(filename: str) -> Optional[Dict[str, str]]:
    """Costruisce il dict risultato per un filename, controlla esistenza su disco."""
    if not filename:
        return None
    filepath = PDF_MANUALS_DIR / filename
    if not filepath.exists():
        return None
    return {
        "filename": filename,
        "filepath": str(filepath),
        "title": filename.replace(".pdf", "").strip(),
        "source": "local_inail",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Seed functions — chiamate da main.py al primo avvio (idempotenti)
# ─────────────────────────────────────────────────────────────────────────────

def _seed_local_aliases_into_db() -> None:
    """
    Esporta _MACHINE_ALIASES_SEED nella tabella machine_aliases.
    Idempotente grazie a ON CONFLICT DO NOTHING.
    Chiamata dopo _ensure_tables() (che ha già inserito _SEED_ALIASES da machine_type_service).
    """
    if not _db_available():
        return
    try:
        from app.services.machine_type_service import resolve_machine_type_id
        conn = _get_conn()
        inserted = 0
        skipped = 0
        with conn.cursor() as cur:
            for alias_text, inail_canonical in _MACHINE_ALIASES_SEED.items():
                target_id = resolve_machine_type_id(inail_canonical)
                if target_id is None:
                    # Prova il testo dell'alias stesso come fallback
                    target_id = resolve_machine_type_id(alias_text)
                if target_id is None:
                    skipped += 1
                    continue
                normalized = alias_text.lower().strip()
                cur.execute(
                    """
                    INSERT INTO machine_aliases (machine_type_id, alias_text, normalized_alias, source)
                    VALUES (%s, %s, %s, 'inail_seed')
                    ON CONFLICT (normalized_alias) DO NOTHING
                    """,
                    (target_id, alias_text, normalized),
                )
                inserted += 1
        conn.commit()
        conn.close()
        logger.info(
            "local_manuals_service: seed alias → machine_aliases completato "
            "(%d inseriti, %d saltati senza match)", inserted, skipped
        )
    except Exception as e:
        logger.warning("local_manuals_service: _seed_local_aliases_into_db fallito: %s", e)


def _seed_inail_assignments_if_empty() -> None:
    """
    Popola inail_manual_assignments da _LOCAL_MANUALS_MAP_SEED.
    Eseguito solo se la tabella è vuota (primo avvio).
    """
    if not _db_available():
        return
    try:
        from app.services.machine_type_service import resolve_machine_type_id
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM inail_manual_assignments")
            count = cur.fetchone()[0]
        if count > 0:
            conn.close()
            logger.info("local_manuals_service: inail_manual_assignments già popolata (%d righe)", count)
            return
        with conn.cursor() as cur:
            seeded = 0
            for canonical_name, pdf_filename in _LOCAL_MANUALS_MAP_SEED.items():
                mt_id = resolve_machine_type_id(canonical_name)
                if mt_id is None:
                    logger.warning(
                        "local_manuals_service: seed INAIL — nessun ID per '%s'", canonical_name
                    )
                    continue
                display_title = Path(pdf_filename).stem.strip()
                cur.execute(
                    """
                    INSERT INTO inail_manual_assignments
                        (machine_type_id, pdf_filename, display_title)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (machine_type_id) DO NOTHING
                    """,
                    (mt_id, pdf_filename, display_title),
                )
                seeded += 1
        conn.commit()
        conn.close()
        logger.info(
            "local_manuals_service: inail_manual_assignments seeded (%d assegnazioni)", seeded
        )
    except Exception as e:
        logger.warning("local_manuals_service: _seed_inail_assignments_if_empty fallito: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# DB CRUD — funzioni per gestione assegnazioni INAIL (usate anche da admin)
# ─────────────────────────────────────────────────────────────────────────────

def get_inail_assignment_by_id(machine_type_id: int) -> Optional[Dict[str, str]]:
    """Cerca assegnazione INAIL per machine_type_id. Ritorna dict con filename o None."""
    if not _db_available():
        return None
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pdf_filename FROM inail_manual_assignments "
                "WHERE machine_type_id = %s AND is_active = true LIMIT 1",
                (machine_type_id,),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return _make_result(row[0])
    except Exception as e:
        logger.debug("get_inail_assignment_by_id(%s): %s", machine_type_id, e)
        return None


def list_inail_assignments() -> List[Dict]:
    """
    Lista tutte le assegnazioni attive con nome del tipo macchina.
    Usata dall'admin panel e da list_local_manuals().
    """
    if not _db_available():
        return []
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ia.id, ia.machine_type_id, mt.name AS machine_type_name,
                       ia.pdf_filename, ia.display_title, ia.is_active
                FROM inail_manual_assignments ia
                JOIN machine_types mt ON mt.id = ia.machine_type_id
                ORDER BY mt.name
                """
            )
            rows = cur.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "machine_type_id": r[1],
                "machine_type_name": r[2],
                "pdf_filename": r[3],
                "display_title": r[4] or r[3].replace(".pdf", "").strip(),
                "is_active": r[5],
                "exists_on_disk": (PDF_MANUALS_DIR / r[3]).exists(),
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning("list_inail_assignments: %s", e)
        return []


def upsert_inail_assignment(
    machine_type_id: int,
    pdf_filename: str,
    display_title: Optional[str] = None,
) -> None:
    """Crea o aggiorna l'assegnazione INAIL per un tipo macchina."""
    if not _db_available():
        return
    title = display_title or pdf_filename.replace(".pdf", "").strip()
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO inail_manual_assignments
                (machine_type_id, pdf_filename, display_title, is_active, updated_at)
            VALUES (%s, %s, %s, true, NOW())
            ON CONFLICT (machine_type_id) DO UPDATE
                SET pdf_filename  = EXCLUDED.pdf_filename,
                    display_title = EXCLUDED.display_title,
                    is_active     = true,
                    updated_at    = NOW()
            """,
            (machine_type_id, pdf_filename, title),
        )
    conn.commit()
    conn.close()


def delete_inail_assignment(machine_type_id: int) -> None:
    """Elimina l'assegnazione quaderno INAIL per un tipo macchina."""
    if not settings.database_url:
        return
    conn = _get_db_conn()
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM inail_manual_assignments WHERE machine_type_id = %s",
            (machine_type_id,),
        )
    conn.commit()
    conn.close()


def list_all_pdf_files() -> List[Dict[str, str]]:
    """
    Lista tutti i PDF fisicamente presenti nella cartella manuali.
    Usata dall'admin per il dropdown di selezione file.
    """
    if not PDF_MANUALS_DIR.exists():
        return []
    return sorted(
        [
            {
                "filename": f.name,
                "title": f.stem.strip(),
            }
            for f in PDF_MANUALS_DIR.glob("*.pdf")
        ],
        key=lambda x: x["filename"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Lookup principale
# ─────────────────────────────────────────────────────────────────────────────

def find_local_manual_by_filename(filename: str) -> Optional[Dict[str, str]]:
    """Cerca un manuale locale direttamente per nome file."""
    return _make_result(filename) if filename else None


def find_local_manual(
    machine_type: str = "",
    db_filename: Optional[str] = None,
    machine_type_id: Optional[int] = None,
) -> Optional[Dict[str, str]]:
    """
    Cerca il manuale INAIL locale per il tipo di macchina.

    Algoritmo:
    0. Se db_filename esplicito → usa direttamente (priorità assoluta)
    1. Se machine_type_id → lookup in inail_manual_assignments per ID
    2. Se machine_type text → resolve_machine_type_id() → step 1
    3. Fallback: discovery su disco (PDF fisici presenti ma non assegnati)
    """
    # Passo 0: file esplicito passato dall'admin
    if db_filename:
        result = find_local_manual_by_filename(db_filename)
        if result:
            return result

    # Passo 1: lookup per ID diretto
    if machine_type_id is not None:
        result = get_inail_assignment_by_id(machine_type_id)
        if result:
            return result

    # Passo 2: risolvi testo → ID → lookup
    if machine_type and machine_type.strip():
        try:
            from app.services.machine_type_service import resolve_machine_type_id
            resolved_id = resolve_machine_type_id(machine_type)
            if resolved_id is not None:
                result = get_inail_assignment_by_id(resolved_id)
                if result:
                    return result
        except Exception:
            pass

    # Passo 3: fallback a discovery da disco (non assegnato in DB)
    if machine_type and PDF_MANUALS_DIR.exists():
        mt_norm = _normalize_machine_type(machine_type)
        for f in sorted(PDF_MANUALS_DIR.glob("*.pdf")):
            canonical = _extract_canonical_from_filename(f.name)
            if canonical and (canonical in mt_norm or mt_norm in canonical):
                return {
                    "filename": f.name,
                    "filepath": str(f),
                    "title": f.stem.strip(),
                    "source": "local_inail",
                }

    return None


def list_local_manuals() -> List[Dict[str, str]]:
    """
    Restituisce tutti i manuali locali disponibili:
    - assegnazioni DB (inail_manual_assignments) con file esistente su disco
    - PDF su disco non ancora assegnati in DB
    """
    manuals = []
    assigned_filenames: set = set()

    # Sorgente primaria: assegnazioni DB
    for assignment in list_inail_assignments():
        fn = assignment["pdf_filename"]
        assigned_filenames.add(fn)
        filepath = PDF_MANUALS_DIR / fn
        if filepath.exists():
            manuals.append({
                "filename": fn,
                "filepath": str(filepath),
                "title": assignment["display_title"],
                "machine_type_id": assignment["machine_type_id"],
                "source": "local_inail",
            })

    # Fallback: PDF fisici su disco non ancora assegnati
    if PDF_MANUALS_DIR.exists():
        for f in sorted(PDF_MANUALS_DIR.glob("*.pdf")):
            if f.name not in assigned_filenames:
                manuals.append({
                    "filename": f.name,
                    "filepath": str(f),
                    "title": f.stem.strip(),
                    "machine_type_id": None,
                    "source": "local_inail",
                })

    return sorted(manuals, key=lambda x: x["title"])


def get_pdf_dir() -> str:
    """Restituisce il percorso della cartella PDF manuali."""
    return str(PDF_MANUALS_DIR)
