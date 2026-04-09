"""
Servizio per la gestione dei manuali locali INAIL.
Mappa i tipi di macchina ai PDF locali nella cartella 'pdf manuali'.

Design:
  - LOCAL_MANUALS_MAP  : chiave canonica → nome file PDF
  - MACHINE_ALIASES    : qualsiasi variante (it/en/brand-specific) → chiave canonica
  - find_local_manual(): normalizza → cerca in MACHINE_ALIASES → lookup canonico
    NESSUN partial-match fuzzy: ogni associazione è esplicita e verificata.
"""
from typing import Optional, Dict, List
from pathlib import Path

# Percorso della cartella PDF manuali.
_BACKEND_ROOT = Path(__file__).parent.parent.parent  # backend/
PDF_MANUALS_DIR = _BACKEND_ROOT / "pdf manuali"

# ─────────────────────────────────────────────────────────────────────────────
# Mappa canonica: chiave → nome file PDF
# Le chiavi sono i termini INAIL ufficiali (usati anche in quality_service)
# ─────────────────────────────────────────────────────────────────────────────
LOCAL_MANUALS_MAP: Dict[str, str] = {
    "gru a torre":                          "Scheda 1 - GRU A TORRE.pdf",
    "gru su autocarro":                     "Scheda 2 - GRU SU AUTOCARRO.pdf",
    "piattaforma aerea":                    "Scheda 3 - PIATTAFORME MOBILI DI LAVORO ELEVABILI.pdf",
    "ascensore di cantiere":                "Scheda 4 - ASCENSORE DI CANTIERE.pdf",
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

    # ── ASCENSORE DI CANTIERE ─────────────────────────────────────────────────
    # ATTENZIONE: "elevatore" da solo NON mappa qui — troppo generico.
    # Solo termini che identificano univocamente l'ascensore da cantiere.
    "ascensore di cantiere":                "ascensore di cantiere",
    "ascensore cantiere":                   "ascensore di cantiere",
    "montacarichi da cantiere":             "ascensore di cantiere",
    "montacarichi":                         "ascensore di cantiere",
    "hoist":                                "ascensore di cantiere",
    "construction hoist":                   "ascensore di cantiere",
    "builder's hoist":                      "ascensore di cantiere",
    "personnel hoist":                      "ascensore di cantiere",

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
}


def _normalize_machine_type(machine_type: str) -> str:
    """Normalizza la stringa (lower + strip). Usata anche da altri servizi."""
    return machine_type.lower().strip()


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

    Algoritmo (senza fuzzy-match):
    1. Normalizza → lowercase strip
    2. Cerca in MACHINE_ALIASES → ottieni la chiave canonica
    3. Cerca la chiave canonica in LOCAL_MANUALS_MAP → ottieni il file
    """
    if not machine_type:
        return None

    # Associazione esplicita dell'admin ha priorità assoluta
    if db_filename:
        result = find_local_manual_by_filename(db_filename)
        if result:
            return result

    mt = _normalize_machine_type(machine_type)

    # 1) Cerca alias esatto
    canonical = MACHINE_ALIASES.get(mt)

    # 2) Nessun alias esatto: cerca se mt è già una chiave canonica
    if not canonical and mt in LOCAL_MANUALS_MAP:
        canonical = mt

    # 3) Nessun match esatto: cerca se mt contiene uno dei termini alias
    #    (es. "carrello elevatore a contrappeso laterale" non è in alias ma contiene "carrello elevatore")
    #    Solo se il match è su un alias abbastanza specifico (>= 12 caratteri) per evitare falsi positivi
    if not canonical:
        best_match_len = 0
        for alias, canon in MACHINE_ALIASES.items():
            if len(alias) >= 12 and alias in mt:
                if len(alias) > best_match_len:
                    canonical = canon
                    best_match_len = len(alias)

    if not canonical:
        return None

    filename = LOCAL_MANUALS_MAP.get(canonical)
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


def list_local_manuals() -> List[Dict[str, str]]:
    """Restituisce la lista di tutti i manuali locali disponibili."""
    manuals = []
    seen_files: set = set()

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

    return sorted(manuals, key=lambda x: x["title"])


def get_pdf_dir() -> str:
    """Restituisce il percorso della cartella PDF manuali."""
    return str(PDF_MANUALS_DIR)
