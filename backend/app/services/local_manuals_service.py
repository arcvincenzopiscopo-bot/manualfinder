"""
Servizio per la gestione dei manuali locali INAIL.
Mappa i tipi di macchina ai PDF locali nella cartella 'pdf manuali'.
"""
import os
from typing import Optional, Dict, List
from pathlib import Path

# Percorso della cartella PDF manuali.
# I PDF sono in backend/pdf manuali/ — sia localmente che nel container Docker
# (dockerContext: ./backend → WORKDIR /app → pdf manuali/ è dentro /app/)
_BACKEND_ROOT = Path(__file__).parent.parent.parent  # backend/
PDF_MANUALS_DIR = _BACKEND_ROOT / "pdf manuali"

# Normalizzazione termini inglesi → italiano
# Secondo strato di sicurezza: se l'OCR restituisce un termine inglese, lo traduce
EN_TO_IT: Dict[str, str] = {
    "dumper": "dumper",
    "articulated dump truck": "dumper",
    "dump truck": "dumper",
    "excavator": "escavatore",
    "mini excavator": "escavatore idraulico",
    "hydraulic excavator": "escavatore idraulico",
    "crane": "gru",
    "tower crane": "gru a torre",
    "truck crane": "gru su autocarro",
    "loader crane": "gru su autocarro",
    "mobile crane": "gru mobile",
    "platform": "piattaforma aerea",
    "aerial platform": "piattaforma aerea",
    "aerial work platform": "piattaforma aerea",
    "boom lift": "piattaforma aerea",
    "scissor lift": "piattaforma aerea",
    "mewp": "piattaforma aerea",
    "awp": "piattaforma aerea",
    "forklift": "carrello elevatore telescopico",
    "fork lift": "carrello elevatore telescopico",
    "telescopic handler": "sollevatore telescopico",
    "telehandler": "sollevatore telescopico",
    "loader": "pala caricatrice frontale",
    "wheel loader": "pala caricatrice frontale",
    "front loader": "pala caricatrice frontale",
    "backhoe loader": "escavatore idraulico",
    "backhoe": "escavatore idraulico",
    "roller": "rullo compattatore",
    "compactor": "rullo compattatore",
    "road roller": "rullo compattatore",
    "vibratory roller": "rullo compattatore",
    "compressor": "compressore",
    "air compressor": "compressore",
    "generator": "generatore",
    "genset": "generatore",
    "concrete pump": "pompa calcestruzzo",
    "pump": "betoniera",
    "drill": "perforatrice micropali",
    "drill rig": "perforatrice micropali",
    "paver": "finitrice",
    "finisher": "finitrice",
    "asphalt paver": "finitrice",
    "breaker": "martello demolitore",
    "jackhammer": "martello demolitore",
    "mixer": "betoniera",
    "concrete mixer": "betoniera",
    "welder": "saldatrice",
    "chainsaw": "motosega",
    "elevator": "ascensore di cantiere",
    "hoist": "ascensore di cantiere",
    "circular saw": "sega circolare",
    "saw": "sega circolare",
    "plate compactor": "piastra vibrante",
    "vibratory plate": "piastra vibrante",
    "scarifier": "tagliasfalto",
    "coring machine": "carotatrice",
    "brushcutter": "decespugliatore",
    "cut-off saw": "troncatrice",
}


def _normalize_machine_type(machine_type: str) -> str:
    """Traduce termini inglesi in italiano e normalizza la stringa."""
    mt = machine_type.lower().strip()
    # Cerca corrispondenza esatta nella mappa EN→IT
    if mt in EN_TO_IT:
        return EN_TO_IT[mt]
    # Cerca corrispondenza parziale (es. "dumper articolato" contiene "dumper")
    for en_term, it_term in EN_TO_IT.items():
        if en_term in mt:
            return it_term
    return mt


# Mappatura tipo macchina -> file PDF locale
# Chiavi: varianti del tipo di macchina (in italiano)
# Valori: nome del file PDF nella cartella locale
LOCAL_MANUALS_MAP: Dict[str, str] = {
    # Gru
    "gru a torre": "Scheda 1 - GRU A TORRE.pdf",
    "gru": "Scheda 1 - GRU A TORRE.pdf",
    "gru su autocarro": "Scheda 2 - GRU SU AUTOCARRO.pdf",
    "camion gru": "Scheda 2 - GRU SU AUTOCARRO.pdf",
    "gru mobile": "Scheda 2 - GRU SU AUTOCARRO.pdf",
    
    # Piattaforme aeree
    "piattaforma aerea": "Scheda 3 - PIATTAFORME MOBILI DI LAVORO ELEVABILI.pdf",
    "piattaforma": "Scheda 3 - PIATTAFORME MOBILI DI LAVORO ELEVABILI.pdf",
    "ple": "Scheda 3 - PIATTAFORME MOBILI DI LAVORO ELEVABILI.pdf",
    "piattaforma mobile elevabile": "Scheda 3 - PIATTAFORME MOBILI DI LAVORO ELEVABILI.pdf",
    "autoscala": "Scheda 3 - PIATTAFORME MOBILI DI LAVORO ELEVABILI.pdf",
    
    # Ascensore di cantiere
    "ascensore di cantiere": "Scheda 4 - ASCENSORE DI CANTIERE.pdf",
    "ascensore": "Scheda 4 - ASCENSORE DI CANTIERE.pdf",
    "elevatore a bandiera": "Scheda 14 - ELEVATORE A BANDIERA.pdf",
    
    # Carrelli elevatori
    "carrello elevatore telescopico": "Scheda 5 - CARRELLO ELEVATORE TELESCOPICO.pdf",
    "sollevatore telescopico": "Scheda 5 - CARRELLO ELEVATORE TELESCOPICO.pdf",
    "carrello elevatore": "Scheda 5 - CARRELLO ELEVATORE TELESCOPICO.pdf",
    "muletto": "Scheda 5 - CARRELLO ELEVATORE TELESCOPICO.pdf",
    
    # Escavatori
    "escavatore idraulico": "Scheda 6 - ESCAVATORE IDRAULICO.pdf",
    "escavatore": "Scheda 6 - ESCAVATORE IDRAULICO.pdf",
    
    # Pale caricatrici
    "pala caricatrice frontale": "Scheda 7 - PALA CARICATRICE FRONTALE.pdf",
    "pala caricatrice": "Scheda 7 - PALA CARICATRICE FRONTALE.pdf",
    "pala meccanica": "Scheda 7 - PALA CARICATRICE FRONTALE.pdf",
    "pala": "Scheda 7 - PALA CARICATRICE FRONTALE.pdf",
    
    # Rulli compattatori
    "rullo compattatore": "Scheda 8 - RULLO COMPATTATORE.pdf",
    "rullo compressore": "Scheda 8 - RULLO COMPATTATORE.pdf",
    "rullo": "Scheda 8 - RULLO COMPATTATORE.pdf",
    
    # Finitrice
    "finitrice": "Scheda 9 - FINITRICE.pdf",
    "finitrice asfalto": "Scheda 9 - FINITRICE.pdf",
    
    # Perforatrice
    "perforatrice micropali": "Scheda 10 - PERFORATRICE MICROPALI.pdf",
    "perforatrice": "Scheda 10 - PERFORATRICE MICROPALI.pdf",
    
    # Betoniera
    "betoniera": "Scheda 11 - BETONIERA.pdf",
    "pompa calcestruzzo": "Scheda 11 - BETONIERA.pdf",
    
    # Seghe
    "sega circolare": "Scheda 12 - SEGA CIRCOLARE.pdf",
    "sega": "Scheda 12 - SEGA CIRCOLARE.pdf",
    "taglia laterizi": "Scheda 13 - TAGLIALATERIZI.pdf",
    "taglialaterizi": "Scheda 13 - TAGLIALATERIZI.pdf",
    
    # Attrezzi portatili
    "piastra vibrante": "Scheda 15 - PIASTRA VIBRANTE.pdf",
    "taglia asfalto": "Scheda 16 - TAGLIASFALTO A DISCO.pdf",
    "tagliasfalto": "Scheda 16 - TAGLIASFALTO A DISCO.pdf",
    "carotatrice": "Scheda 17 - CAROTATRICE.pdf",
    "decespugliatore": "Scheda 18 - DECESPUGLIATORE.pdf",
    "troncatrice": "Scheda 19 - TRONCATRICE PORTATILE A DISCO.pdf",
    "martello demolitore": "Scheda 19 - TRONCATRICE PORTATILE A DISCO.pdf",
    "motosega": "Scheda 20 - MOTOSEGA.pdf",
}


def find_local_manual(machine_type: str) -> Optional[Dict[str, str]]:
    """
    Cerca un manuale locale per il tipo di macchina specificato.
    Traduce automaticamente termini inglesi in italiano prima della ricerca.
    """
    if not machine_type:
        return None

    mt = _normalize_machine_type(machine_type)
    
    # Cerca corrispondenza esatta
    if mt in LOCAL_MANUALS_MAP:
        filename = LOCAL_MANUALS_MAP[mt]
        filepath = PDF_MANUALS_DIR / filename
        if filepath.exists():
            return {
                "filename": filename,
                "filepath": str(filepath),
                "title": filename.replace(".pdf", "").strip(),
                "source": "local_inail",
            }
    
    # Cerca corrispondenza parziale
    for key, filename in LOCAL_MANUALS_MAP.items():
        if key in mt or mt in key:
            filepath = PDF_MANUALS_DIR / filename
            if filepath.exists():
                return {
                    "filename": filename,
                    "filepath": str(filepath),
                    "title": filename.replace(".pdf", "").strip(),
                    "source": "local_inail",
                }
    
    return None


def list_local_manuals() -> List[Dict[str, str]]:
    """
    Restituisce la lista di tutti i manuali locali disponibili.
    """
    manuals = []
    seen_files = set()
    
    for key, filename in LOCAL_MANUALS_MAP.items():
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