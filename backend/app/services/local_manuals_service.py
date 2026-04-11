"""
Servizio per la gestione dei manuali locali INAIL.
Mappa i tipi di macchina ai PDF locali nella cartella 'pdf manuali'.

Design:
  - LOCAL_MANUALS_MAP  : chiave canonica → nome file PDF (file noti, con alias espliciti)
  - MACHINE_ALIASES    : qualsiasi variante (it/en/brand-specific) → chiave canonica
  - find_local_manual(): normalizza → alias → mappa → discovery dinamica da disco
  - Discovery dinamica: qualsiasi PDF aggiunto alla cartella viene rilevato
    automaticamente estraendo il nome canonico dal filename
    (es. "Scheda 23 - POMPE IDRAULICHE.pdf" → canonical "pompe idrauliche").
"""
from typing import Optional, Dict, List
from pathlib import Path
import re as _re

# Percorso della cartella PDF manuali.
# Cerca prima nella root di progetto (dove l'utente aggiunge i file),
# poi fallback alla cartella backend/ per compatibilità.
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # manualfinder/
_BACKEND_ROOT  = Path(__file__).parent.parent.parent         # backend/
_root_dir    = _PROJECT_ROOT / "pdf manuali"
_backend_dir = _BACKEND_ROOT / "pdf manuali"
PDF_MANUALS_DIR = _root_dir if _root_dir.exists() else _backend_dir

# ─────────────────────────────────────────────────────────────────────────────
# Mappa canonica: chiave → nome file PDF
# Le chiavi sono i termini INAIL ufficiali (usati anche in quality_service)
# ─────────────────────────────────────────────────────────────────────────────
LOCAL_MANUALS_MAP: Dict[str, str] = {
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

# ─────────────────────────────────────────────────────────────────────────────
# Tabella alias: OGNI variante/sinonimo/termine-inglese → chiave canonica
# Tutto quello che NON è qui dentro NON viene abbinato a nessun manuale INAIL.
# Aggiungere qui varianti nuove, MAI affidarsi al partial-match fuzzy.
# ─────────────────────────────────────────────────────────────────────────────
MACHINE_ALIASES: Dict[str, str] = {

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
    # ATTENZIONE: "elevatore" da solo NON mappa qui — troppo generico.
    # Solo termini che identificano univocamente l'ascensore da cantiere.
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
    # Separato dall'ascensore di cantiere — strumento diverso
    "elevatore a bandiera":                 "elevatore a bandiera",
    "elevatore":                            "elevatore a bandiera",
    "paranco":                              "elevatore a bandiera",
    "argano":                               "elevatore a bandiera",
    "hoisting winch":                       "elevatore a bandiera",

    # ── CARRELLO ELEVATORE TELESCOPICO ───────────────────────────────────────
    # Include carrelli frontali, laterali, reach stacker, retrattili
    # (La Scheda 5 INAIL copre tutti i carrelli industriali)
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
    "terna":                                "escavatore idraulico",     # Scheda INAIL più vicina

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
    "bulldozer":                            "pala caricatrice frontale",   # approssimazione
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
    # NOTA: pompa calcestruzzo ≠ betoniera — ma in assenza di scheda INAIL dedicata
    # la Scheda 11 è la più vicina. Il quality_service gestisce la distinzione.
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
    "sega a nastro":                        "sega circolare",   # approssimazione
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
    "martello demolitore":                  "troncatrice",     # approssimazione
    "martello demolitore idraulico":        "troncatrice",     # accessorio, scheda INAIL più vicina
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
    "apripista":                            "macchina movimento terra",
    "bulldozer":                            "macchina movimento terra",
    "scraper":                              "macchina movimento terra",
    "livellatrice":                         "macchina movimento terra",
    "grader":                               "macchina movimento terra",
    "terna":                                "macchina movimento terra",
    "escavatore a filo":                    "macchina movimento terra",
    "earth moving machine":                 "macchina movimento terra",
    "earthmover":                           "macchina movimento terra",
}


def _normalize_machine_type(machine_type: str) -> str:
    """Normalizza la stringa (lower + strip). Usata anche da altri servizi."""
    return machine_type.lower().strip()


def _extract_canonical_from_filename(filename: str) -> str:
    """
    Estrae il nome canonico dal filename del quaderno INAIL.
    Es. "Scheda 21 - TRATTORI AGRICOLI.pdf"  → "trattori agricoli"
        "Scheda 22 - MOVIMENTO TERRA.pdf"    → "movimento terra"
        "Qualcosa - POMPE IDRAULICHE.pdf"    → "pompe idrauliche"
        "POMPE IDRAULICHE.pdf"               → "pompe idrauliche"
    """
    stem = Path(filename).stem
    # Rimuove prefisso tipo "Scheda N -" o "N -" o "Scheda N–"
    name = _re.sub(r'^(?:scheda\s+)?\d+\s*[-–]\s*', '', stem, flags=_re.IGNORECASE)
    return name.lower().strip()


def _get_dynamic_files() -> List[Dict[str, str]]:
    """
    Scansiona PDF_MANUALS_DIR e ritorna i file NON già presenti in LOCAL_MANUALS_MAP,
    con il canonical estratto automaticamente dal filename.
    Chiamato a runtime: rileva i nuovi file senza riavvio né modifica al codice.
    """
    if not PDF_MANUALS_DIR.exists():
        return []
    known_files = set(LOCAL_MANUALS_MAP.values())
    result = []
    for f in sorted(PDF_MANUALS_DIR.glob("*.pdf")):
        if f.name in known_files:
            continue
        canonical = _extract_canonical_from_filename(f.name)
        if canonical:
            result.append({
                "filename": f.name,
                "canonical": canonical,
                "filepath": str(f),
                "title": f.stem.strip(),
            })
    return result


def find_local_manual_by_filename(filename: str) -> Optional[Dict[str, str]]:
    """
    Cerca un manuale locale direttamente per nome file.
    Usato quando l'admin ha associato esplicitamente un file a un tipo macchina.
    """
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


def find_local_manual(machine_type: str, db_filename: Optional[str] = None) -> Optional[Dict[str, str]]:
    """
    Cerca il manuale INAIL locale per il tipo di macchina.

    Algoritmo:
    0. Se admin ha associato un file esplicito → lo usa direttamente
    1. Normalizza → lowercase strip
    2. Cerca in MACHINE_ALIASES → ottieni la chiave canonica
    3. Cerca se mt è già chiave in LOCAL_MANUALS_MAP
    4. Substring match su alias lunghi (>= 12 chars)
    5. Discovery dinamica: cerca nei PDF su disco non presenti in LOCAL_MANUALS_MAP,
       usando il canonical estratto dal filename
    """
    if not machine_type:
        return None

    # Passo 0: associazione esplicita dell'admin — priorità assoluta
    if db_filename:
        result = find_local_manual_by_filename(db_filename)
        if result:
            return result

    mt = _normalize_machine_type(machine_type)

    # Passo 1: alias esatto
    canonical = MACHINE_ALIASES.get(mt)

    # Passo 2: mt è già una chiave canonica
    if not canonical and mt in LOCAL_MANUALS_MAP:
        canonical = mt

    # Passo 3: mt contiene un alias lungo (>= 12 chars)
    if not canonical:
        best_match_len = 0
        for alias, canon in MACHINE_ALIASES.items():
            if len(alias) >= 12 and alias in mt:
                if len(alias) > best_match_len:
                    canonical = canon
                    best_match_len = len(alias)

    # Passo 4: lookup in LOCAL_MANUALS_MAP via canonical trovato
    if canonical:
        filename = LOCAL_MANUALS_MAP.get(canonical)
        if filename:
            filepath = PDF_MANUALS_DIR / filename
            if filepath.exists():
                return {
                    "filename": filename,
                    "filepath": str(filepath),
                    "title": filename.replace(".pdf", "").strip(),
                    "source": "local_inail",
                }

    # Passo 5: file extra su disco non in LOCAL_MANUALS_MAP — solo se già validati
    # (raggiungibili solo tramite db_filename al passo 0, dopo che l'admin ha approvato la proposta)
    return None


def list_local_manuals() -> List[Dict[str, str]]:
    """
    Restituisce la lista di tutti i manuali locali disponibili:
    quelli in LOCAL_MANUALS_MAP + quelli scoperti dinamicamente su disco.
    """
    manuals = []
    seen_files: set = set()

    # File noti dalla mappa statica
    for filename in LOCAL_MANUALS_MAP.values():
        if filename in seen_files:
            continue
        seen_files.add(filename)
        filepath = PDF_MANUALS_DIR / filename
        if filepath.exists():
            manuals.append({
                "filename": filename,
                "filepath": str(filepath),
                "title": filename.replace(".pdf", "").strip(),
                "source": "local_inail",
            })

    # File extra scoperti dinamicamente su disco
    for entry in _get_dynamic_files():
        manuals.append({
            "filename": entry["filename"],
            "filepath": entry["filepath"],
            "title": entry["title"],
            "source": "local_inail",
        })

    return sorted(manuals, key=lambda x: x["title"])


def get_pdf_dir() -> str:
    """Restituisce il percorso della cartella PDF manuali."""
    return str(PDF_MANUALS_DIR)
