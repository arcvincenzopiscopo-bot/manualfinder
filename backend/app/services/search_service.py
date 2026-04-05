"""
Ricerca manuale online per marca e modello del macchinario.
Strategia a due binari:
  1. Libretto INAIL per TIPO di macchina (priorità)
  2. Manuale produttore per MODELLO specifico
Provider: Perplexity (L1) → Brave Search (L2) → Google CSE (L2) → DuckDuckGo (L3)
"""
import asyncio
import httpx
import re
from typing import List, Set, Optional
from app.config import settings
from app.models.responses import ManualSearchResult


# Mappatura tipi macchina -> termini di ricerca INAIL
INAIL_MACHINE_TYPES = {
    "piattaforma aerea": "piattaforma di lavoro mobile elevabile PLE",
    "piattaforma": "piattaforma di lavoro mobile elevabile PLE",
    "escavatore": "escavatore",
    "gru": "gru",
    "gru mobile": "gru mobile",
    "gru a torre": "gru a torre",
    "carrello elevatore": "carrello elevatore",
    "muletto": "carrello elevatore",
    "sollevatore telescopico": "sollevatore telescopico",
    "compressore": "compressore",
    "generatore": "gruppo elettrogeno",
    "pompa": "pompa calcestruzzo",
    "rullo compressore": "rullo compressore",
    "pala meccanica": "pala caricatrice",
    "dumper": "dumper autocarro ribaltabile",
    "autocarro ribaltabile": "dumper autocarro ribaltabile",
    "betoniera": "betoniera",
    "martello demolitore": "martello demolitore",
    "saldatrice": "saldatrice",
    "fresa": "fresa",
    "sega": "sega",
    "trattore": "trattore",
    "camion gru": "camion gru",
    "autoscala": "autoscala",
    # Lavorazione lamiera / macchine utensili
    "piegatrice": "pressa piegatrice",
    "pressa piegatrice": "pressa piegatrice",
    "pressa idraulica": "pressa piegatrice",
    "press brake": "pressa piegatrice",
    "punzonatrice": "punzonatrice pressa",
    "punzonatura": "punzonatrice pressa",
    "cesoiatrice": "cesoie trancia",
    "tranciatrice": "cesoie trancia",
    "cesoie": "cesoie trancia",
    "laser": "macchina taglio laser",
    "taglio laser": "macchina taglio laser",
    "tornio": "tornio macchina utensile",
    "fresatrice": "fresatrice macchina utensile",
    "rettificatrice": "rettificatrice macchina utensile",
    "saldatrice mig": "saldatrice",
    "saldatrice tig": "saldatrice",
    # Tipi aggiuntivi frequenti in cantiere / industria
    "perforatrice": "perforatrice",
    "finitrice": "finitrice",
    "gru idraulica": "gru mobile",
    "verricello": "verricello",
    "argano": "argano",
    "elevatore a cremagliera": "montacarichi",
    "montacarichi": "montacarichi",
    "pala caricatrice": "pala caricatrice",
    "rullo compattatore": "rullo compressore",
    "vibrofinitrici": "finitrice",
    "motocompressore": "compressore",
    "gruppo elettrogeno": "gruppo elettrogeno",
    "gru su autocarro": "camion gru",
    "piattaforma elevabile": "piattaforma di lavoro mobile elevabile PLE",
    "ple": "piattaforma di lavoro mobile elevabile PLE",
    # Macchine da cantiere aggiuntive
    "terna": "terna retroescavatore",
    "terne": "terna retroescavatore",
    "retroescavatore": "terna retroescavatore",
    "bulldozer": "bulldozer apripista",
    "apripista": "bulldozer apripista",
    "piastra vibrante": "piastra vibrante costipatore",
    "costipatore": "piastra vibrante costipatore",
    "pompa calcestruzzo": "pompa calcestruzzo autobetonpompa",
    "autobetonpompa": "pompa calcestruzzo autobetonpompa",
    "pompa cls": "pompa calcestruzzo autobetonpompa",
    "frantoio": "frantoio impianto",
    "vibrofinitrice": "finitrice",
    "scarificatrice": "fresatrice stradale",
    "fresatrice stradale": "fresatrice stradale",
    "gru autocarro": "camion gru",
    "autocarro con gru": "camion gru",
    "sollevatore": "sollevatore telescopico",
    "telehandler": "sollevatore telescopico",
}


def _normalize_brand(brand: str) -> str:
    """
    Normalizza il nome del brand per la ricerca.
    Gestisce: abbreviazioni, tutto-maiuscolo (da OCR), varianti conglomerate.
    """
    if not brand:
        return brand
    brand = brand.lower().strip()
    brand_map = {
        # Caterpillar / CAT
        "cat":              "caterpillar",
        "caterpillar":      "caterpillar",
        # Atlas Copco
        "atlas copco":      "atlascopco",
        "atlascopco":       "atlascopco",
        "atlas":            "atlas",
        # John Deere
        "john deere":       "deere",
        "deere":            "deere",
        # CNH Industrial (Case / New Holland)
        "cnh":              "case",
        "cnhi":             "case",
        "cnh industrial":   "case",
        "case construction": "case",
        "new holland":      "case",
        "newholland":       "case",
        # Komatsu
        "komatsu":          "komatsu",
        # JCB
        "jcb":              "jcb",
        # Liebherr
        "liebherr":         "liebherr",
        # Manitou
        "manitou":          "manitou",
        # Haulotte
        "haulotte":         "haulotte",
        # Tadano / Grove
        "tadano":           "tadano",
        "grove":            "manitowoc",
        "manitowoc":        "manitowoc",
        # Volvo CE
        "volvo":            "volvo",
        "volvo ce":         "volvo",
        # Terex
        "terex":            "terex",
        # Merlo
        "merlo":            "merlo",
        # Wacker Neuson
        "wacker neuson":    "wacker neuson",
        "wacker":           "wacker",
        "wacker-neuson":    "wacker neuson",
        # Mercedes-Benz
        "mercedes":         "mercedes-benz",
        "mercedes-benz":    "mercedes-benz",
        # Hitachi
        "hitachi":          "hitachi",
        # Doosan / Bobcat
        "doosan":           "doosan",
        "bobcat":           "bobcat",
        # Hyundai CE
        "hyundai":          "hyundai",
        # Linde / Still / Jungheinrich (carrelli)
        "linde":            "linde",
        "still":            "still",
        "jungheinrich":     "jungheinrich",
        # Macchine utensili
        "trumpf":           "trumpf",
        "bystronic":        "bystronic",
        "amada":            "amada",
        "salvagnini":       "salvagnini",
        "ermaksan":         "ermaksan",
    }
    return brand_map.get(brand, brand)


def _get_inail_machine_type(machine_type: Optional[str]) -> Optional[str]:
    """Ottieni il termine di ricerca INAIL per il tipo di macchina.
    Normalizza prima i termini inglesi in italiano."""
    if not machine_type:
        return None
    from app.services.local_manuals_service import _normalize_machine_type
    mt = _normalize_machine_type(machine_type)
    # Cerca corrispondenza diretta
    if mt in INAIL_MACHINE_TYPES:
        return INAIL_MACHINE_TYPES[mt]
    # Cerca corrispondenza parziale
    for key, value in INAIL_MACHINE_TYPES.items():
        if key in mt or mt in key:
            return value
    # Usa il tipo normalizzato come termine di ricerca
    return mt


_EDILIZIA_MACHINE_TYPES = {
    "escavatore", "escavatori", "gru", "gru mobile", "gru a torre", "camion gru",
    "carrello elevatore", "muletto", "sollevatore telescopico",
    "pala caricatrice", "pala meccanica", "dumper", "autocarro ribaltabile",
    "rullo compressore", "rullo compattatore", "compressore", "finitrice",
    "piattaforma di lavoro mobile elevabile ple", "pompa calcestruzzo",
    "terna", "terne", "retroescavatore", "bulldozer", "apripista",
    "betoniera", "martello demolitore",
}

# Fonti per macchine utensili da officina (non edilizia)
_OFFICINA_MACHINE_TYPES = {
    "pressa piegatrice", "piegatrice", "press brake", "cesoie trancia",
    "punzonatrice pressa", "macchina taglio laser", "tornio macchina utensile",
    "fresatrice macchina utensile", "rettificatrice macchina utensile",
}


def _build_inail_queries(machine_type: Optional[str]) -> List[str]:
    """Genera query specifiche per ricerca INAIL per tipo di macchina."""
    inail_type = _get_inail_machine_type(machine_type)
    if not inail_type:
        return []

    inail_type_lower = inail_type.lower()
    is_edilizia = any(k in inail_type_lower for k in _EDILIZIA_MACHINE_TYPES)
    is_officina = any(k in inail_type_lower for k in _OFFICINA_MACHINE_TYPES)

    queries = [
        f'site:inail.it "{inail_type}" scheda tecnica',
        f'site:inail.it "{inail_type}" libretto',
        f'site:inail.it "{inail_type}" manuale sicurezza',
        # Quaderni Tecnici INAIL — serie più autorevole per cantieri e industria
        f'site:inail.it "quaderni tecnici" "{inail_type}" filetype:pdf',
        f'site:inail.it "quaderni tecnici per i cantieri" "{inail_type}" filetype:pdf',
    ]

    # CPT Torino / FormedilTorinoFSC — "Le macchine in edilizia":
    # SOLO per attrezzature da cantiere/edilizia — NON per carrelli, macchine utensili, ecc.
    if is_edilizia and not is_officina:
        queries.append(f'site:formediltorinofsc.it "{inail_type}" filetype:pdf')

    # UCIMU/Assofluid — fonti autorevoli per macchine utensili da officina
    if is_officina:
        queries += [
            f'site:ucimu.it "{inail_type}" sicurezza filetype:pdf',
            f'"{inail_type}" "D.Lgs. 81" sicurezza filetype:pdf site:ucimu.it OR site:inail.it',
        ]

    queries += [
        # PuntoSicuro — linee guida regionali e ministeriali per attrezzature
        f'site:puntosicuro.it "{inail_type}" filetype:pdf',
        # Regioni — Piani Mirati di Prevenzione con schede macchina allineate D.Lgs.81
        f'site:salute.regione.emilia-romagna.it "{inail_type}" filetype:pdf',
        f'site:ats-milano.it "{inail_type}" filetype:pdf',
        f'"piano mirato di prevenzione" "{inail_type}" filetype:pdf',
    ]

    return queries


# Siti ufficiali internazionali del produttore — massima autorità, PDF originali
# NOTA: definiti a livello di modulo per riuso in _scrape_wayback_machine
MANUFACTURER_SITES_PRIMARY = {
    "caterpillar": "cat.com",
    "komatsu":     "komatsu.com",
    "manitou":     "manitou.com",
    "atlascopco":  "atlascopco.com",
    "liebherr":    "liebherr.com",
    "volvo":       "volvoce.com",
    "jcb":         "jcb.com",
    "case":        "casece.com",
    "deere":       "deere.com",
    "bobcat":      "bobcat.com",
    "haulotte":    "haulotte.com",
    "fassi":       "fassi.com",
    "manitowoc":   "manitowoc.com",
    "tadano":      "tadano.com",
    "genie":       "genielift.com",
    "jlg":         "jlg.com",
    "terex":       "terex.com",
    "wacker neuson": "wackerneuson.com",
    "wacker":      "wackerneuson.com",
    "atlas":       "atlascopco.com",
    "putzmeister": "putzmeister.com",
    "schwing":     "schwing.de",
    # Macchine utensili / lavorazione lamiera
    "leadermec":   "leadermec.it",
    "ermaksan":    "ermaksan.com",
    "durma":       "durmapress.com",
    "bystronic":   "bystronic.com",
    "trumpf":      "trumpf.com",
    "amada":       "amada.com",
    "prima":       "prima-industrie.com",
    "salvagnini":  "salvagnini.com",
    "ficep":       "ficep.it",
    "gasparini":   "gasparini.com",
    "euromac":     "euromac.it",
    "rainer":      "rainer.it",
    "safan":       "safan-e-brake.com",
    "cidan":       "cidan.com",
    # Brand aggiuntivi comuni
    "hitachi":     "hitachicm.com",
    "merlo":       "merlo.com",
    "grove":       "manitowoc.com",
    "linde":       "linde-mh.com",
    "still":       "still.de",
    "jungheinrich": "jungheinrich.com",
    "doosan":      "doosanequipment.com",
    "hyundai":     "hd-hyundaice.com",
    "sandvik":     "sandvik.com",
    "atlas copco": "atlascopco.com",
    # Rulli compattatori / finitrici stradali
    "bomag":       "bomag.com",
    "wirtgen":     "wirtgen.com",
    "hamm":        "hamm.ag",
    "dynapac":     "dynapac.com",
    "ammann":      "ammann-group.com",
    "sakai":       "sakai-world.com",
    # Perforatrici / trivelle
    "soilmec":     "soilmec.com",
    "bauer":       "bauer.de",
    # Sollevatori telescopici aggiuntivi
    "skyjack":     "skyjack.com",
    "snorkel":     "snorkellifts.com",
    "dieci":       "diecisrl.com",
    # Compressori cantiere aggiuntivi
    "ceccato":     "ceccato.com",
    "kaeser":      "kaeser.com",
    "fini":        "fini-group.com",
    "abac":        "abac.com",
}

# Dealer italiani ufficiali — secondari, aggiunti DOPO le query sul sito primario
# Separati in dict distinto per evitare che sovrascrivano le chiavi primarie
MANUFACTURER_SITES_SECONDARY = {
    "jcb":          "jcbitalia.it",
    "komatsu":      "komatsu-italia.it",
    "liebherr":     "liebherr-italia.com",
    "manitou":      "manitou-italia.it",
    "haulotte":     "haulotte-italia.com",
    "tadano":       "tadano-italia.com",
    # Siti UK/internazionali con PDF manuali pubblici — ottima fonte
    "fassi":        "fassiuk.com",
    "merlo":        "merlogroup.com",
    "wacker neuson": "wackerneuson.com",
    "wacker":        "wackerneuson.com",
}


def _build_manual_queries(brand: str, model: str) -> List[str]:
    """
    Genera query per ricerca manuale specifico del produttore.
    Ordine: query filetype:pdf aperte → sito produttore → dealer → generiche.
    """
    normalized = _normalize_brand(brand)
    queries = []

    # 0) Query filetype:pdf SENZA restrizioni di sito — trovano PDF ovunque sul web
    # (archive.org, scribd, dealer minori, siti produttore con struttura URL diversa)
    # Messe PRIMA delle query site-specific per catturare più risultati con ddgs
    queries += [
        f'"{brand} {model}" operator manual filetype:pdf',
        f'"{brand} {model}" manuale operatore filetype:pdf',
        f'"{brand} {model}" "operator\'s manual" filetype:pdf',
        f'"{model}" operator manual filetype:pdf -"spare parts" -"parts catalog"',
        f'"{brand} {model}" manuale uso manutenzione filetype:pdf',
    ]

    # 1) Sito produttore ufficiale — alta priorità
    if normalized in MANUFACTURER_SITES_PRIMARY:
        site = MANUFACTURER_SITES_PRIMARY[normalized]
        queries.insert(0, f"{brand} {model} operator manual filetype:pdf site:{site}")
        queries.insert(1, f"{brand} {model} manuale site:{site}")

    # 2) Dealer italiano ufficiale
    if normalized in MANUFACTURER_SITES_SECONDARY:
        sec = MANUFACTURER_SITES_SECONDARY[normalized]
        queries.append(f"{brand} {model} manuale filetype:pdf site:{sec}")

    # 3) Aggregatori specializzati manuali
    queries += [
        f'"{brand} {model}" manual site:manualzz.com',
        f'"{brand} {model}" manual site:manualsbase.com',
        f'"{brand} {model}" operator manual site:scribd.com',
        f'"{brand} {model}" manuale operatore site:issuu.com',
    ]

    # 4) Query generiche in coda
    queries += [
        f"{brand} {model} filetype:pdf manuale",
        f"{brand} {model} filetype:pdf manual",
        f"{brand} {model} operator manual pdf",
    ]

    return queries


def _build_ante_ce_queries(machine_type: Optional[str], year: str, is_allegato_v: bool = False) -> List[str]:
    """
    Query specializzate per macchine pre-Direttiva Macchine.
    - ante-1996 (is_allegato_v=True): Allegato V D.Lgs.81, D.P.R. 547/55, nessuna CE
    - ante-2006: Direttiva 98/37/CE, D.Lgs. 626/94
    """
    inail_type = _get_inail_machine_type(machine_type) if machine_type else None
    base_type = inail_type or machine_type or "attrezzatura"

    queries = [
        # ISPESL — ente predecessore di INAIL, archivi storici
        f'site:inail.it ISPESL "{base_type}" filetype:pdf',
        f'ISPESL "{base_type}" sicurezza filetype:pdf',
    ]

    if is_allegato_v:
        # Ante-1996: cerca requisiti Allegato V e normativa pre-CE
        queries += [
            f'"Allegato V" "D.Lgs. 81" "{base_type}" filetype:pdf',
            f'"requisiti minimi" "{base_type}" sicurezza filetype:pdf',
            f'"D.P.R. 547" "{base_type}" sicurezza filetype:pdf',
            f'"adeguamento" "{base_type}" "vecchie attrezzature" filetype:pdf',
        ]
    else:
        # Ante-2006: cerca documentazione 626/94 e direttiva 98/37/CE
        queries += [
            f'"626/1994" "{base_type}" sicurezza filetype:pdf',
            f'"98/37/CE" "{base_type}" manuale filetype:pdf',
            f'ASL "{base_type}" "{year}" sicurezza filetype:pdf',
        ]

    return queries


def _build_auction_queries(brand: str, model: str) -> List[str]:
    """
    Query per portali aste/usato macchinari.
    Chi vende macchinari pesanti spesso allega il manuale e il certificato CE
    come prova di regolarità per rassicurare il compratore — PDF diretti.
    """
    return [
        # Mascus — principale portale europeo macchinari usati
        f'site:mascus.it "{brand}" "{model}" manuale filetype:pdf',
        f'site:mascus.com "{brand}" "{model}" manual filetype:pdf',
        # MachineryZone — forte in Italia e Francia
        f'site:machineryzone.it "{brand}" "{model}" manuale',
        # Surplex — aste industriali europee con documentazione tecnica
        f'site:surplex.com "{brand}" "{model}" manual filetype:pdf',
        # Forum riparatori italiani — manuali circolano nelle community meccanici
        f'site:forum-macchine.it "{brand}" "{model}" manuale OR pdf',
        # Heavy Equipment Forums — internazionale, forte su macchine movimento terra
        f'site:heavyequipmentforums.com "{brand}" "{model}" manual pdf',
    ]


def _build_rental_queries(brand: str, model: str) -> List[str]:
    """
    Query per portali di noleggio italiani.
    Art. 72 D.Lgs. 81/08: chi noleggia è obbligato a fornire il manuale d'uso.
    Molti portali caricano i PDF direttamente nelle schede prodotto.
    Query separate per dominio: più precise di una query multi-sito generica.
    """
    return [
        # Leader europeo — sezione italiana con schede tecniche e manuali operativi
        f'site:loxam.it "{brand}" "{model}" manuale',
        f'site:loxam.it "{brand}" "{model}" scheda tecnica',
        # Boels: tasto "Scarica manuale" per quasi ogni attrezzatura
        f'site:boels.it "{brand}" "{model}" manuale',
        # Mollo: PDF nelle schede prodotto per macchine movimento terra
        f'site:mollonoleggio.com "{brand}" "{model}" manuale',
        # Lorini: molto forte su attrezzature minori (betoniere, costipatori)
        f'site:lorini.it "{brand}" "{model}"',
        # Kiloutou Italia
        f'site:kiloutou.it "{brand}" "{model}" manuale',
        # CGT = dealer ufficiale Caterpillar Italia: brochure tecniche dettagliate
        f'site:cgt.it "{brand}" "{model}" filetype:pdf',
    ]


def _build_institutional_queries(machine_type: Optional[str]) -> List[str]:
    """
    Query per fonti istituzionali equivalenti o complementari a INAIL:
    SUVA (CH-IT), EU-OSHA, DGUV (DE), UCIMU (macchine utensili), ENAMA (agricole).
    """
    inail_type = _get_inail_machine_type(machine_type) if machine_type else None
    base = inail_type or machine_type or "macchinario"

    queries = [
        # SUVA Canton Ticino — schede sicurezza in italiano, stessa autorità INAIL
        f'site:suva.ch "{base}" sicurezza filetype:pdf',
        f'suva.ch "{base}" lista di controllo filetype:pdf',
        # EU-OSHA — agenzia europea, schede in italiano
        f'site:osha.europa.eu "{base}" sicurezza filetype:pdf',
        # DGUV — equivalente INAIL tedesco, utile per brand DE (Liebherr, Komatsu, ecc.)
        f'site:dguv.de "{base}" filetype:pdf',
    ]

    # Macchine utensili / lavorazione lamiera → UCIMU
    utensili_types = {
        "pressa piegatrice", "punzonatrice pressa", "cesoie trancia",
        "tornio macchina utensile", "fresatrice macchina utensile",
        "rettificatrice macchina utensile", "macchina taglio laser",
    }
    if base in utensili_types:
        queries += [
            f'site:ucimu.it "{base}" sicurezza filetype:pdf',
            f'UCIMU "{base}" linee guida sicurezza filetype:pdf',
            f'site:inail.it "macchine utensili" "{base}" filetype:pdf',
        ]

    # Macchine agricole → ENAMA
    if machine_type and any(w in machine_type.lower() for w in
                            ["trattore", "agri", "mietitrebbia", "seminatrice", "falciatrice"]):
        queries += [
            f'site:enama.it "{base}" sicurezza filetype:pdf',
            f'ENAMA "{base}" scheda sicurezza filetype:pdf',
        ]

    return queries


def _build_multilingual_queries(brand: str, model: str) -> List[str]:
    """
    Query in tedesco e francese per produttori europei.
    I manuali originali in DE/FR vengono poi tradotti dall'AI.
    """
    normalized = _normalize_brand(brand)
    brand_lower = brand.lower()
    queries = []

    german_brands = {
        "liebherr", "komatsu", "wackerneuson", "wacker", "atlascopco", "atlas",
        "putzmeister", "schwing", "trumpf", "kaeser", "bystronic", "ermaksan",
        "linde", "still", "jungheinrich", "zeppelin", "compact",
    }
    french_brands = {
        "manitou", "haulotte", "potain", "ppm", "merlo",
    }
    is_german = (normalized in german_brands
                 or any(sfx in brand_lower for sfx in ["gmbh", " ag", " kg", "werke"]))
    is_french = (normalized in french_brands
                 or any(sfx in brand_lower for sfx in ["france", " sa", " sas", " sàrl"]))

    if is_german:
        queries += [
            f"{brand} {model} Bedienungsanleitung filetype:pdf",
            f"{brand} {model} Betriebsanleitung filetype:pdf",
            f'site:dguv.de "{brand}" "{model}" filetype:pdf',
        ]
    if is_french:
        queries += [
            f"{brand} {model} notice utilisation filetype:pdf",
            f"{brand} {model} manuel opérateur filetype:pdf",
        ]
    if not is_german and not is_french:
        # Per brand non classificati: prova inglese generico come catch-all
        queries.append(f"{brand} {model} operating instructions filetype:pdf")

    return queries


def _build_serial_queries(brand: str, model: str, serial_number: str) -> List[str]:
    """
    Query con numero di serie per trovare la versione esatta del manuale.
    Alcuni portali produttore (CAT, JCB, Komatsu) permettono ricerca per seriale.
    """
    normalized = _normalize_brand(brand)
    queries = []

    serial_support = {
        "caterpillar": "parts.cat.com",
        "jcb": "jcbservice.com",
        "komatsu": "komatsu.com",
        "volvo": "volvoce.com",
        "liebherr": "liebherr.com",
    }

    if normalized in serial_support:
        site = serial_support[normalized]
        queries.append(f'site:{site} "{serial_number}" manual filetype:pdf')
        queries.append(f'site:{site} "{serial_number}" "{model}"')

    # Query generica con seriale — qualsiasi fonte
    queries += [
        f'"{brand}" "{model}" "{serial_number}" manual filetype:pdf',
        f'"{serial_number}" "{brand}" manuale filetype:pdf',
    ]
    return queries


async def _scrape_wayback_machine(brand: str, model: str) -> List[ManualSearchResult]:
    """
    Cerca PDF archiviati da Wayback Machine sul sito del produttore.
    Usa la CDX API pubblica (gratuita, no auth).
    Cruciale per: produttori che hanno rimosso i PDF, macchine ante-CE, brand cessati.
    """
    normalized = _normalize_brand(brand)

    # Usa MANUFACTURER_SITES_PRIMARY (unica fonte di verità per i domini)
    domain = MANUFACTURER_SITES_PRIMARY.get(normalized)
    if not domain:
        return []

    model_slug = re.sub(r'\s+', '', model.lower())
    brand_slug = normalized[:6]
    results: List[ManualSearchResult] = []

    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            resp = await client.get(
                "https://web.archive.org/cdx/search/cdx",
                params={
                    "url": f"{domain}/*.pdf",
                    "output": "json",
                    "limit": 30,
                    "fl": "original,timestamp",
                    "filter": "statuscode:200",
                    "collapse": "original",
                },
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            if not data or len(data) < 2:
                return []

            for row in data[1:]:  # Prima riga = header
                if len(row) < 2:
                    continue
                original_url, timestamp = row[0], row[1]
                url_lower = original_url.lower()

                # Scarta PDF di ricambi
                if any(t in url_lower for t in _PDF_EXCLUDE_TERMS):
                    continue

                # Preferisce URL che contengono model o brand slug
                combined = url_lower + " "
                relevant = (
                    model_slug in combined.replace("%20", "").replace("-", "").replace("_", "")
                    or brand_slug in combined
                    or any(t in combined for t in _PDF_INCLUDE_TERMS)
                )
                if not relevant:
                    continue

                wayback_url = f"https://web.archive.org/web/{timestamp}/{original_url}"
                year_found = timestamp[:4] if timestamp else "?"
                results.append(ManualSearchResult(
                    url=wayback_url,
                    title=f"{brand} {model} — Archivio web ({year_found})",
                    source_type="manufacturer",
                    language="unknown",
                    is_pdf=True,
                    relevance_score=42,  # Affidabile ma versione datata
                ))

            results.sort(key=lambda r: r.url, reverse=True)  # Più recente prima
            return results[:4]

    except Exception:
        return []


_MANUFACTURER_DOMAINS = {
    # Macchine movimento terra / sollevamento
    "caterpillar.com", "cat.com", "komatsu.com", "manitou.com", "atlascopco.com",
    "liebherr.com", "volvoce.com", "jcb.com", "casece.com", "deere.com",
    "haulotte.com", "fassi.com", "manitowoc.com", "tadano.com",
    "bobcat.com", "wackerneuson.com", "putzmeister.com", "schwing.de",
    "genielift.com", "skyjack.com", "jlg.com", "terex.com",
    # Macchine utensili / lavorazione lamiera — produttori italiani e internazionali
    "leadermec.it", "ermaksan.com", "durmapress.com", "bystronic.com",
    "trumpf.com", "amada.com", "prima-industrie.com", "salvagnini.com",
    "ficep.it", "gasparini.com", "metallurgie.it", "safan-e-brake.com",
    "cidan.com", "euromac.it", "rainer.it", "promecam.it",
    "daito.it", "bendmak.com", "yangli.com", "accurl.com",
    # Compressori / utensili pneumatici
    "ceccato.com", "fini-group.com", "abac.com", "kaeser.com",
    # Dealer ufficiali italiani — spesso hanno manuali IT non presenti sul sito internazionale
    "jcbitalia.it", "komatsu-italia.it", "liebherr-italia.com",
    "manitou-italia.it", "haulotte-italia.com", "atlascopco.it",
    "volvoce.it", "cnh-italia.com", "caterpillar-italia.com",
    "wackerneuson.it", "tadano-italia.com",
}

_RENTAL_DOMAINS = {
    "loxam.it", "boels.it", "mollonoleggio.com", "lorini.it",
    "kiloutou.it", "riwal.com", "cgt.it",
}

_INSTITUTIONAL_DOMAINS = {
    "inail.it", "formediltorinofsc.it", "puntosicuro.it",
    "salute.regione.emilia-romagna.it", "ats-milano.it",
    # Fonti istituzionali internazionali equivalenti INAIL
    "suva.ch",           # Istituto svizzero assicurazione infortuni — schede in italiano (CH-IT)
    "osha.europa.eu",    # EU-OSHA — agenzia europea sicurezza
    "dguv.de",           # Equivalente INAIL tedesco — qualità alta per brand DE
    "ucimu.it",          # Macchine utensili italiane
    "enama.it",          # Macchine agricole
}

_AGGREGATOR_DOMAINS = {
    "manualslib.com",
    "heavyequipments.org",
    "manualmachine.com",    # Sostituisce SafeManuals: PDF scaricabili senza login
    "manualeIstruzioni.it", # Aggregatore italiano: buona copertura macchine EU
}


def _classify_source(url: str) -> tuple[str, str]:
    """Classifica la sorgente e la lingua stimata dall'URL."""
    url_lower = url.lower()
    if any(d in url_lower for d in _INSTITUTIONAL_DOMAINS):
        return "inail", "it"
    if any(d in url_lower for d in _MANUFACTURER_DOMAINS):
        return "manufacturer", "en"
    if any(d in url_lower for d in _RENTAL_DOMAINS):
        return "web", "it"
    if any(ext in url_lower for ext in [".it/", ".it?", ".it#"]) or url_lower.endswith(".it"):
        return "web", "it"
    return "web", "unknown"


# Keyword nel titolo che indicano documento utile per sicurezza
_TITLE_POSITIVE = [
    ("manuale operatore", 25), ("manuale uso e manutenzione", 25),
    ("operator manual", 25), ("user manual", 20), ("manuale d'uso", 20),
    ("istruzioni per l'uso", 20), ("istruzioni d'uso", 20),
    ("safety manual", 20), ("manuale sicurezza", 20),
    ("manuale", 15), ("istruzioni", 15), ("manual", 15), ("operator", 12),
    ("sicurezza", 10), ("safety", 10), ("uso", 8), ("maintenance", 8),
    ("scheda tecnica", 5), ("datasheet", 5),
    # Norme armonizzate specifiche macchine utensili
    ("EN 12622", 8), ("EN 13736", 8), ("EN 693", 8),
]

# Keyword nel titolo che indicano documento NON utile (penalità)
_TITLE_NEGATIVE = [
    ("spare parts", -25), ("parts catalog", -25), ("catalogo ricambi", -25),
    ("parts list", -20), ("listino", -20), ("price list", -20),
    ("workshop manual", -15), ("service manual", -15), ("repair manual", -15),
    ("manuale officina", -15), ("manuale riparazione", -15),
    # Brochure commerciali — non contengono dati di sicurezza
    ("brochure", -20), ("product sheet", -15), ("scheda prodotto", -15),
    ("scheda commerciale", -15), ("flyer", -15), ("volantino", -15),
    ("wiring diagram", -10), ("schema elettrico", -10),
]


def _score_result(
    url: str, title: str, is_pdf: bool,
    is_inail: bool = False,
    brand: str = "", model: str = "",
) -> int:
    """
    Assegna uno score di rilevanza al risultato di ricerca (0–100).

    Criteri (in ordine di peso):
    1. Autorità fonte: INAIL/istituzionale > produttore ufficiale > portale noleggio > aggregatore > web
    2. Tipo documento: PDF > pagina HTML
    3. Corrispondenza brand/modello nel titolo — segnale diretto di pertinenza
    4. Contenuto titolo: penalizza cataloghi ricambi e manuali officina
    """
    score = 0
    url_lower = url.lower()
    title_lower = title.lower()

    # ── 1. Autorità della fonte ──────────────────────────────────────────
    if is_inail or any(d in url_lower for d in _INSTITUTIONAL_DOMAINS):
        score += 50  # INAIL e fonti istituzionali italiane: priorità assoluta
    elif any(d in url_lower for d in _MANUFACTURER_DOMAINS):
        score += 25  # Sito ufficiale produttore: fonte primaria per il modello
    elif any(d in url_lower for d in _RENTAL_DOMAINS):
        score += 18  # Portale noleggio: obbligo Art.72 D.Lgs.81, documenti affidabili
    elif any(d in url_lower for d in _AGGREGATOR_DOMAINS):
        score += 8   # Aggregatori: utili ma qualità variabile
    elif ".it" in url_lower:
        score += 5   # Generico italiano

    # ── 2. Tipo documento ────────────────────────────────────────────────
    if is_pdf or url_lower.endswith(".pdf"):
        score += 22  # PDF scaricabile: analizzabile direttamente dall'AI

    # ── 3. Corrispondenza brand/modello nel titolo ───────────────────────
    if brand or model:
        brand_l = brand.lower().strip()
        model_l = model.lower().strip()
        brand_in_title = bool(brand_l) and brand_l in title_lower
        model_in_title = bool(model_l) and len(model_l) >= 3 and model_l in title_lower
        combined = brand_in_title and model_in_title
        url_brand = bool(brand_l) and brand_l in url_lower
        url_model = bool(model_l) and len(model_l) >= 3 and model_l in url_lower

        if combined:
            score += 18  # Brand + modello entrambi nel titolo → massima pertinenza
        elif model_in_title:
            score += 10  # Solo modello nel titolo
        elif brand_in_title:
            score += 5   # Solo brand nel titolo

        if url_brand and url_model:
            score += 8   # Brand + modello nell'URL → PDF dedicato al modello
        elif url_model:
            score += 4

    # ── 4. Qualità titolo ────────────────────────────────────────────────
    for kw, pts in _TITLE_POSITIVE:
        if kw in title_lower:
            score += pts
            break  # Solo la corrispondenza migliore (sono ordinati per peso)

    for kw, pts in _TITLE_NEGATIVE:
        if kw in title_lower:
            score += pts  # pts è negativo
            break

    # ── 5. Penalità URL — percorsi che indicano documento non pertinente ────
    _URL_NEGATIVE_PATHS = (
        "brochure", "environmental", "/epd/", "declaration", "sustainability",
        "emissions", "carbon", "/flyer", "/promo", "/news/", "/press-release",
    )
    if any(p in url_lower for p in _URL_NEGATIVE_PATHS):
        score -= 40  # Penalità forte: molto probabilmente non è un manuale d'uso

    return max(0, min(100, score))


def _normalize_url(url: str) -> str:
    """
    Normalizza un URL per il confronto duplicati.
    Rimuove: trailing slash, parametri di tracking, varianti CDN, frammenti.
    """
    from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
    try:
        p = urlparse(url.lower().strip())
        # Rimuovi parametri di tracking comuni
        tracking = {"utm_source", "utm_medium", "utm_campaign", "utm_content",
                    "utm_term", "ref", "source", "fbclid", "gclid"}
        qs = {k: v for k, v in parse_qs(p.query).items() if k not in tracking}
        clean = urlunparse((p.scheme, p.netloc, p.path.rstrip("/"), "", urlencode(qs, doseq=True), ""))
        return clean
    except Exception:
        return url.lower().rstrip("/")


def _deduplicate_results(results: List[ManualSearchResult]) -> List[ManualSearchResult]:
    """
    Rimuove duplicati e ordina per score.
    Se stesso URL con score diverso, mantiene il più alto.
    """
    best: dict[str, ManualSearchResult] = {}
    for r in results:
        key = _normalize_url(r.url)
        if key not in best or r.relevance_score > best[key].relevance_score:
            best[key] = r
    return sorted(best.values(), key=lambda r: r.relevance_score, reverse=True)


async def search_manual(
    brand: str,
    model: str,
    machine_type: Optional[str] = None,
    lang: str = "it",
    machine_year: Optional[str] = None,
    serial_number: Optional[str] = None,
) -> List[ManualSearchResult]:
    """
    Cerca il manuale con strategia a più livelli.
    Risultati cachati 7 giorni per evitare query ripetute.
    """
    from app.services import local_manuals_service
    from app.services.cache_service import search_cache

    provider = settings.get_search_provider()

    # ── Cache lookup ─────────────────────────────────────────────────────
    cache_key = (brand, model, machine_type or "", machine_year or "", serial_number or "")
    cached = search_cache.get(*cache_key)
    if cached is not None:
        # Ricostruisci oggetti Pydantic dalla cache (serializzati come dict)
        return [ManualSearchResult(**r) for r in cached]

    all_results: List[ManualSearchResult] = []
    
    # LIVELLO 1: Cerca nel database locale PDF INAIL
    if machine_type:
        local_manual = local_manuals_service.find_local_manual(machine_type)
        if local_manual:
            # Crea un risultato per il PDF locale
            local_result = ManualSearchResult(
                url=f"/manuals/local/{local_manual['filename']}",
                title=f"{local_manual['title']} (INAIL - Locale)",
                source_type="inail",
                language="it",
                is_pdf=True,
                relevance_score=100,  # Priorità massima
            )
            all_results.append(local_result)
    
    # LIVELLO 2: Cerca libretto INAIL online per tipo di macchina
    if machine_type:
        inail_queries = _build_inail_queries(machine_type)
        for query in inail_queries[:2]:  # Prova max 2 query INAIL
            try:
                results = await _search_with_provider(query, provider)
                if results:
                    # Marca come INAIL e aumenta score
                    for r in results:
                        if "inail.it" in r.url.lower():
                            r.relevance_score = _score_result(r.url, r.title, r.is_pdf, is_inail=True)
                    all_results.extend(results)
                    # Se abbiamo trovato risultati INAIL online, siamo soddisfatti
                    inail_results = [r for r in all_results if "inail.it" in r.url.lower()]
                    if len(inail_results) >= 2:
                        break
            except Exception:
                continue
    
    # LIVELLO 2b: Fonti istituzionali equivalenti INAIL (SUVA, EU-OSHA, UCIMU, ENAMA)
    # In parallelo con le query INAIL — stesso livello di autorità
    if machine_type:
        institutional_queries = _build_institutional_queries(machine_type)
        for query in institutional_queries[:3]:
            try:
                results = await _search_with_provider(query, provider)
                all_results.extend(results)
            except Exception:
                continue

    # LIVELLO 3a: Fonti dirette indipendenti (in parallelo)
    direct_tasks = [
        _search_manualslib(brand, model),
        _search_manualsplus(brand, model),
        _search_heavyequipments(brand, model),
        _search_manualmachine(brand, model),
        _search_safemanuals(brand, model),
        _search_all_guides(brand, model),
    ]
    for direct_results in await asyncio.gather(*direct_tasks, return_exceptions=True):
        if isinstance(direct_results, list):
            all_results.extend(direct_results)

    # LIVELLO 3b: Cerca manuale produttore via provider generico
    manual_queries = _build_manual_queries(brand, model)
    rental_queries = _build_rental_queries(brand, model)
    auction_queries = _build_auction_queries(brand, model)

    for query in manual_queries[:3]:
        try:
            results = await _search_with_provider(query, provider)
            if results:
                all_results.extend(results)
                pdf_results = [r for r in all_results if r.is_pdf]
                if len(pdf_results) >= 3:
                    break
        except Exception:
            continue

    # Portali noleggio: solo se ancora pochi PDF (macchine da cantiere su portali noleggio,
    # inutile per macchine utensili da officina come piegatrici, torni, ecc.)
    pdf_so_far = [r for r in all_results if r.is_pdf]
    if len(pdf_so_far) < 2:
        for query in rental_queries:
            try:
                results = await _search_with_provider(query, provider)
                if results:
                    for r in results:
                        if any(d in r.url.lower() for d in _RENTAL_DOMAINS):
                            r.relevance_score = min(100, r.relevance_score + 15)
                    all_results.extend(results)
            except Exception:
                continue

    # Aste/usato e forum: solo se ancora pochi PDF
    pdf_so_far = [r for r in all_results if r.is_pdf]
    if len(pdf_so_far) < 2:
        for query in auction_queries[:3]:
            try:
                results = await _search_with_provider(query, provider)
                all_results.extend(results)
            except Exception:
                continue

    # ── Query multilingua (DE/FR) ────────────────────────────────────────
    # Solo se ancora pochi PDF — manuali non italiani vengono tradotti dall'AI
    pdf_so_far = [r for r in all_results if r.is_pdf]
    if len(pdf_so_far) < 2:
        multi_queries = _build_multilingual_queries(brand, model)
        for query in multi_queries:
            try:
                results = await _search_with_provider(query, provider)
                all_results.extend(results)
            except Exception:
                continue

    # ── Ricerca per numero di serie ──────────────────────────────────────
    # Trova la versione esatta del manuale per il range di seriali specifico
    pdf_so_far = [r for r in all_results if r.is_pdf]
    if serial_number and len(pdf_so_far) < 3:
        serial_queries = _build_serial_queries(brand, model, serial_number)
        for query in serial_queries[:2]:
            try:
                results = await _search_with_provider(query, provider)
                all_results.extend(results)
            except Exception:
                continue

    # ── Routing ante-CE ──────────────────────────────────────────────────
    pdf_so_far = [r for r in all_results if r.is_pdf]
    if machine_year and len(pdf_so_far) < 2:
        try:
            year_int = int(machine_year)
            if year_int < 2006:
                is_allegato_v = year_int < 1996
                ante_ce_queries = _build_ante_ce_queries(machine_type, machine_year, is_allegato_v)
                for query in ante_ce_queries:
                    try:
                        results = await _search_with_provider(query, provider)
                        all_results.extend(results)
                    except Exception:
                        continue
        except (ValueError, TypeError):
            pass

    # ── Scraping diretto produttore + Wayback Machine + pagine HTML ─────
    pdf_so_far = [r for r in all_results if r.is_pdf]
    if len(pdf_so_far) < 2:
        # 3c: URL dirette sul sito del produttore noto
        # 3e: Wayback Machine — archivio storico PDF produttore
        scraping_tasks = [
            _scrape_producer_site(brand, model),
            _scrape_wayback_machine(brand, model),
        ]
        scraping_results = await asyncio.gather(*scraping_tasks, return_exceptions=True)
        for batch in scraping_results:
            if isinstance(batch, list):
                all_results.extend(batch)

        # 3d: scraping delle pagine HTML trovate dalla ricerca
        html_pages = [r for r in all_results if not r.is_pdf]
        if html_pages:
            scraped = await scrape_html_results_for_pdfs(html_pages, brand, model)
            all_results.extend(scraped)

    # ── Corrispondenza temporale ─────────────────────────────────────────
    if machine_year:
        try:
            machine_year_int = int(machine_year)
            # Query aggiuntiva con anno solo se ancora pochi PDF
            pdf_so_far = [r for r in all_results if r.is_pdf]
            if len(pdf_so_far) < 3:
                year_query = f"{brand} {model} manual {machine_year_int} filetype:pdf"
                year_results = await _search_with_provider(year_query, provider)
                all_results.extend(year_results)
            all_results = _apply_temporal_score(all_results, machine_year_int)
        except (ValueError, TypeError):
            pass

    # ── Fallback finale DuckDuckGo ───────────────────────────────────────
    if not all_results:
        try:
            fallback_query = f"{brand} {model} manual pdf"
            all_results = await _search_duckduckgo(fallback_query)
        except Exception:
            pass

    # ── Re-scoring brand/model: applicato su tutti i risultati prima della dedup ──
    # I singoli provider non conoscono brand/model, quindi applichiamo qui il bonus
    # per corrispondenza nel titolo/URL. Aggiorna lo score in-place.
    all_results = _apply_brand_model_score(all_results, brand, model)

    # ── AI ranking: Gemini Flash classifica i candidati PDF per pertinenza ──
    # ~800 token, ~$0.00006, ~1s — chiamata non bloccante sul percorso critico
    # se fallisce, la lista resta quella del ranking rule-based precedente.
    all_results = await ai_rank_candidates(all_results, brand, model, machine_type)

    deduped = _deduplicate_results(all_results)

    # ── Scrittura in cache ───────────────────────────────────────────────
    if deduped:
        try:
            search_cache.set(*cache_key, [r.model_dump() for r in deduped])
        except Exception:
            pass

    return deduped


def _apply_brand_model_score(
    results: List[ManualSearchResult], brand: str, model: str
) -> List[ManualSearchResult]:
    """
    Aggiunge un bonus di score basato sulla presenza di brand/modello nel titolo e nell'URL.
    Applicato su tutti i risultati dopo la raccolta, prima della deduplicazione.
    Non penalizza mai — aggiunge solo bonus positivi.
    """
    if not brand and not model:
        return results

    brand_l = brand.lower().strip()
    model_l = model.lower().strip()

    for r in results:
        title_l = r.title.lower()
        url_l = r.url.lower()
        bonus = 0

        brand_in_title = bool(brand_l) and brand_l in title_l
        model_in_title = bool(model_l) and len(model_l) >= 3 and model_l in title_l
        brand_in_url   = bool(brand_l) and brand_l in url_l
        model_in_url   = bool(model_l) and len(model_l) >= 3 and model_l in url_l

        if brand_in_title and model_in_title:
            bonus += 18   # Corrispondenza esatta brand+modello nel titolo
        elif model_in_title:
            bonus += 10
        elif brand_in_title:
            bonus += 5

        if brand_in_url and model_in_url:
            bonus += 8    # Brand+modello nell'URL → PDF dedicato al modello
        elif model_in_url:
            bonus += 4

        if bonus:
            r.relevance_score = min(100, r.relevance_score + bonus)

    return results


async def ai_rank_candidates(
    results: List[ManualSearchResult],
    brand: str,
    model: str,
    machine_type: Optional[str],
) -> List[ManualSearchResult]:
    """
    Usa Gemini Flash per riordinare i candidati PDF prima del download.
    Input: titolo + URL + snippet di ogni risultato (~800 token totali).
    Output: stessa lista con relevance_score aggiornato dall'AI.

    Se l'AI non è disponibile o fallisce, restituisce la lista invariata.
    Costa ~$0.00006 per chiamata — trascurabile.
    """
    pdf_candidates = [r for r in results if r.is_pdf]
    if len(pdf_candidates) < 2:
        return results  # niente da riordinare

    # Prepara il contesto — solo i PDF candidati, massimo 12
    candidates_text = "\n".join(
        f"{i+1}. TITLE: {r.title[:100]}\n   URL: {r.url[:120]}\n   SNIPPET: {(r.snippet or '')[:120]}"
        for i, r in enumerate(pdf_candidates[:12])
    )

    prompt = f"""Sei un esperto di macchinari industriali. Devi selezionare i manuali d'uso e sicurezza per: {brand} {model} (tipo: {machine_type or 'non specificato'}).

Candidati trovati online:
{candidates_text}

Per ogni candidato assegna un punteggio da 0 a 100:
- 90-100: manuale d'uso/operatore/sicurezza specifico per {brand} {model} o modello molto simile
- 70-89: manuale d'uso per la stessa categoria di macchina ({machine_type or 'stessa categoria'}) ma brand diverso
- 40-69: scheda tecnica, datasheet o documento normativo pertinente alla categoria
- 10-39: documento parzialmente pertinente (noleggio, vendita con documentazione allegata)
- 0-9: catalogo ricambi, catalogo attrezzature/utensili, brochure commerciale, spec sheet, documento non pertinente

Rispondi SOLO con un JSON array di oggetti con i campi "i" (numero 1-based) e "score":
[{{"i": 1, "score": 85}}, {{"i": 2, "score": 20}}, ...]

Includi TUTTI i {min(len(pdf_candidates), 12)} candidati. Nessun testo aggiuntivo."""

    try:
        from app.config import settings
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=300,
                temperature=0.0,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        import json, re
        text = response.text
        # Estrai JSON array dalla risposta
        m = re.search(r'\[.*\]', text, re.DOTALL)
        if not m:
            return results
        scores_list = json.loads(m.group(0))
        score_map = {item["i"]: item["score"] for item in scores_list if "i" in item and "score" in item}

        # Applica i punteggi AI ai candidati PDF.
        # L'AI agisce come BOOST selettivo, non come penalità globale:
        # - score AI >= 70 (manuale reale): bonus +20 capped a 100
        # - score AI 40-69 (documento pertinente): score invariato
        # - score AI < 40 (catalogo/brochure): penalità -15
        # In questo modo non abbassa i candidati legittimi che l'AI non riconosce
        # (es. PDF scansionati senza testo nel titolo/snippet).
        for idx, r in enumerate(pdf_candidates[:12]):
            ai_score = score_map.get(idx + 1)
            if ai_score is None:
                continue
            if ai_score >= 70:
                r.relevance_score = min(100, r.relevance_score + 20)
            elif ai_score < 40:
                r.relevance_score = max(0, r.relevance_score - 15)

    except Exception:
        pass  # Fallback silenzioso — la lista torna invariata

    return results


def _apply_temporal_score(
    results: List[ManualSearchResult], machine_year: int
) -> List[ManualSearchResult]:
    """
    Modifica lo score in base alla coerenza temporale tra la macchina e il manuale.

    Logica:
    - Manuale con anno nel titolo/URL vicino all'anno della macchina: bonus
    - Manuale con anno molto lontano (>15 anni): penalità lieve
      (es. macchina 1995 + manuale 2024 = sistemi sicurezza diversi,
       normativa diversa — pre/post Direttiva Macchine 2006/42/CE)
    - Manuale senza anno rilevabile: nessuna modifica (non penalizzare per mancanza info)
    - INAIL e fonti istituzionali: nessuna penalità (le schede si aggiornano)
    """
    year_pattern = re.compile(r'\b(19[6-9]\d|20[0-2]\d)\b')

    for r in results:
        # Le fonti istituzionali non vengono mai penalizzate per l'anno
        if any(d in r.url.lower() for d in _INSTITUTIONAL_DOMAINS):
            continue

        # Cerca anno nel titolo e nell'URL
        text_to_search = f"{r.title} {r.url}"
        found_years = [int(y) for y in year_pattern.findall(text_to_search)]

        if not found_years:
            continue  # Nessun anno rilevabile: nessuna modifica

        # Usa l'anno più vicino alla macchina tra quelli trovati
        closest_year = min(found_years, key=lambda y: abs(y - machine_year))
        gap = abs(closest_year - machine_year)

        if gap <= 3:
            # Manuale coevo (entro 3 anni): bonus significativo
            r.relevance_score = min(100, r.relevance_score + 12)
        elif gap <= 8:
            # Manuale vicino (entro 8 anni): bonus lieve
            r.relevance_score = min(100, r.relevance_score + 5)
        elif gap > 15:
            # Manuale molto distante: penalità lieve
            # Non troppo aggressiva: il modello potrebbe essere rimasto invariato
            r.relevance_score = max(0, r.relevance_score - 8)

    return results


async def _search_with_provider(query: str, provider: str) -> List[ManualSearchResult]:
    """
    Esegue la ricerca con il provider specificato.
    Se il provider primario restituisce 0 risultati, fallback automatico a DuckDuckGo.
    """
    if provider == "perplexity":
        results = await _search_perplexity(query)
    elif provider == "brave":
        results = await _search_brave(query)
    elif provider == "google_cse":
        results = await _search_google_cse(query)
    elif provider == "gemini_search":
        results = await _search_gemini_grounding(query)
    else:
        results = await _search_duckduckgo(query)

    # Fallback a DuckDuckGo se il provider primario non ha trovato niente
    if not results and provider not in ("duckduckgo", None):
        import logging as _log
        _log.getLogger(__name__).info(
            "_search_with_provider: %s returned 0 results for %r, falling back to DuckDuckGo",
            provider, query[:60]
        )
        try:
            results = await _search_duckduckgo(query)
        except Exception:
            pass

    return results


async def _search_perplexity(query: str) -> List[ManualSearchResult]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.perplexity_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "sonar",
                "messages": [{"role": "user", "content": query}],
                "return_citations": True,
            },
        )
        response.raise_for_status()
        data = response.json()

    results: List[ManualSearchResult] = []
    citations = data.get("citations", [])

    for citation in citations[:8]:
        url = citation if isinstance(citation, str) else citation.get("url", "")
        if not url:
            continue

        title = citation.get("title", url) if isinstance(citation, dict) else url
        is_pdf = url.lower().endswith(".pdf") or "pdf" in url.lower()
        source_type, language = _classify_source(url)
        is_inail = "inail.it" in url.lower()

        results.append(ManualSearchResult(
            url=url,
            title=title,
            source_type=source_type,
            language=language,
            is_pdf=is_pdf,
            relevance_score=_score_result(url, title, is_pdf, is_inail),
        ))

    return results


async def _search_brave(query: str) -> List[ManualSearchResult]:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"X-Subscription-Token": settings.brave_search_api_key},
            params={"q": query, "count": 10, "search_lang": "it", "result_filter": "web"},
        )
        response.raise_for_status()
        data = response.json()

    results: List[ManualSearchResult] = []
    for item in data.get("web", {}).get("results", []):
        url = item.get("url", "")
        title = item.get("title", "")
        is_pdf = url.lower().endswith(".pdf")
        source_type, language = _classify_source(url)
        is_inail = "inail.it" in url.lower()

        results.append(ManualSearchResult(
            url=url,
            title=title,
            source_type=source_type,
            language=language,
            is_pdf=is_pdf,
            relevance_score=_score_result(url, title, is_pdf, is_inail),
        ))

    return results


async def _search_google_cse(query: str) -> List[ManualSearchResult]:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": settings.google_cse_api_key,
                "cx": settings.google_cse_cx,
                "q": query,
                "num": 10,
                "lr": "lang_it",
            },
        )
        response.raise_for_status()
        data = response.json()

    results: List[ManualSearchResult] = []
    for item in data.get("items", []):
        url = item.get("link", "")
        title = item.get("title", "")
        is_pdf = url.lower().endswith(".pdf") or item.get("fileFormat") == "pdf"
        source_type, language = _classify_source(url)
        is_inail = "inail.it" in url.lower()

        results.append(ManualSearchResult(
            url=url,
            title=title,
            source_type=source_type,
            language=language,
            is_pdf=is_pdf,
            relevance_score=_score_result(url, title, is_pdf, is_inail),
        ))

    return results


async def _search_duckduckgo(query: str) -> List[ManualSearchResult]:
    """Ricerca DuckDuckGo tramite libreria ddgs (più affidabile dello scraping HTML)."""
    results: List[ManualSearchResult] = []

    try:
        from ddgs import DDGS
        import asyncio

        loop = asyncio.get_event_loop()
        # DDGS è sincrono — lo eseguiamo in un thread separato per non bloccare l'event loop
        def _ddgs_search():
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=12, safesearch="off"))

        hits = await loop.run_in_executor(None, _ddgs_search)

        for hit in hits:
            url = hit.get("href") or hit.get("url") or ""
            if not url:
                continue
            title = hit.get("title") or url
            snippet = hit.get("body") or ""
            is_pdf = url.lower().endswith(".pdf") or "filetype=pdf" in url.lower() or ".pdf" in url.lower()
            source_type, language = _classify_source(url)
            is_inail = "inail.it" in url.lower()
            results.append(ManualSearchResult(
                url=url,
                title=title,
                source_type=source_type,
                language=language,
                is_pdf=is_pdf,
                relevance_score=_score_result(url, title, is_pdf, is_inail),
                snippet=snippet,
            ))

    except ImportError:
        # Fallback: scraping HTML se ddgs non installato
        logger.warning("duckduckgo-search non installato, uso scraping HTML")
        results = await _search_duckduckgo_html(query)
    except Exception as e:
        logger.warning("_search_duckduckgo (ddgs) failed: %s: %s", type(e).__name__, e)
        # Tenta fallback HTML
        try:
            results = await _search_duckduckgo_html(query)
        except Exception:
            pass

    return results


async def _search_duckduckgo_html(query: str) -> List[ManualSearchResult]:
    """Fallback: scraping HTML di DuckDuckGo (meno affidabile, usato se ddgs fallisce)."""
    from bs4 import BeautifulSoup
    from urllib.parse import unquote, parse_qs, urlparse

    results: List[ManualSearchResult] = []
    try:
        async with httpx.AsyncClient(
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            follow_redirects=True,
        ) as client:
            response = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
            )
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        for result_div in soup.find_all("div", class_="result"):
            link_tag = result_div.find("a", class_="result__url")
            if not link_tag:
                continue
            href = link_tag.get("href", "")
            if not href:
                continue
            if "/l/?uddg=" in href:
                parsed = urlparse(href)
                params = parse_qs(parsed.query)
                url = unquote(params.get("uddg", [""])[0])
            else:
                url = href
            if not url or "duckduckgo.com" in url:
                continue
            title = link_tag.get_text(strip=True) or url
            snippet_tag = result_div.find("a", class_="result__snippet")
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
            is_pdf = url.lower().endswith(".pdf") or "pdf" in url.lower() or "pdf" in snippet.lower()
            source_type, language = _classify_source(url)
            is_inail = "inail.it" in url.lower()
            results.append(ManualSearchResult(
                url=url, title=title,
                source_type=source_type, language=language,
                is_pdf=is_pdf,
                relevance_score=_score_result(url, title, is_pdf, is_inail),
            ))
        if not results:
            pdf_urls = re.findall(r'(https?://[^\s"<>]+\.pdf[^\s"<>]*)', response.text)
            for url in pdf_urls[:6]:
                if "duckduckgo.com" in url:
                    continue
                source_type, language = _classify_source(url)
                is_inail = "inail.it" in url.lower()
                results.append(ManualSearchResult(
                    url=url, title=f"PDF: {url.split('/')[-1]}",
                    source_type=source_type, language=language,
                    is_pdf=True,
                    relevance_score=_score_result(url, url, True, is_inail),
                ))
    except Exception:
        pass
    return results


async def _search_gemini_grounding(query: str) -> List[ManualSearchResult]:
    """
    Ricerca tramite Google Search grounding di Gemini.
    Usa la chiave Gemini già disponibile — nessuna API aggiuntiva.
    Restituisce URL reali di Google con qualità superiore a DuckDuckGo.
    """
    from google import genai
    from google.genai import types
    from app.config import settings

    results: List[ManualSearchResult] = []
    try:
        client = genai.Client(api_key=settings.gemini_api_key)

        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=(
                f"{query}\n\n"
                "Elenca i link diretti ai PDF trovati (manuali, libretti, schede tecniche). "
                "Priorità a PDF scaricabili direttamente."
            ),
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                max_output_tokens=512,
            ),
        )

        # Estrai URL dai grounding chunks (fonte primaria)
        candidate = response.candidates[0] if response.candidates else None
        if candidate and candidate.grounding_metadata:
            chunks = candidate.grounding_metadata.grounding_chunks or []
            redirect_urls: List[tuple[str, str]] = []  # (redirect_url, title)
            for chunk in chunks:
                web = getattr(chunk, "web", None)
                if not web:
                    continue
                url = getattr(web, "uri", "") or ""
                title = getattr(web, "title", "") or url
                if not url:
                    continue
                redirect_urls.append((url, title))

            # Segui i redirect per ottenere gli URL reali
            if redirect_urls:
                async with httpx.AsyncClient(
                    timeout=10, follow_redirects=True,
                    headers={"User-Agent": "Mozilla/5.0"},
                ) as client:
                    for redirect_url, title in redirect_urls:
                        try:
                            if "vertexaisearch.cloud.google.com" in redirect_url:
                                resp = await client.head(redirect_url)
                                real_url = str(resp.url)
                            else:
                                real_url = redirect_url
                            is_pdf = real_url.lower().endswith(".pdf") or "pdf" in real_url.lower()
                            source_type, language = _classify_source(real_url)
                            is_inail = "inail.it" in real_url.lower()
                            results.append(ManualSearchResult(
                                url=real_url,
                                title=title,
                                source_type=source_type,
                                language=language,
                                is_pdf=is_pdf,
                                relevance_score=_score_result(real_url, title, is_pdf, is_inail),
                            ))
                        except Exception:
                            # Mantieni il redirect URL se non riusciamo a seguirlo
                            is_pdf = redirect_url.lower().endswith(".pdf")
                            source_type, language = _classify_source(redirect_url)
                            results.append(ManualSearchResult(
                                url=redirect_url, title=title,
                                source_type=source_type, language=language,
                                is_pdf=is_pdf,
                                relevance_score=0,
                            ))

        # Fallback: cerca URL nel testo della risposta se grounding vuoto
        if not results and response.text:
            import re
            found_urls = re.findall(r'https?://[^\s\)\]"<>]+', response.text)
            for url in found_urls[:8]:
                url = url.rstrip(".,;)")
                is_pdf = url.lower().endswith(".pdf") or "pdf" in url.lower()
                source_type, language = _classify_source(url)
                is_inail = "inail.it" in url.lower()
                results.append(ManualSearchResult(
                    url=url,
                    title=url.split("/")[-1] or url,
                    source_type=source_type,
                    language=language,
                    is_pdf=is_pdf,
                    relevance_score=_score_result(url, url, is_pdf, is_inail),
                ))

    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).warning("_search_gemini_grounding failed: %s: %s", type(e).__name__, e)

    return results


async def _search_manualslib(brand: str, model: str) -> List[ManualSearchResult]:
    """
    Cerca su ManualsLib per brand + model.
    ManualsLib blocca lo scraping diretto da IP cloud, quindi usiamo DuckDuckGo
    con site:manualslib.com per trovare le pagine, poi seguiamo il link /download/.
    """
    from bs4 import BeautifulSoup

    results: List[ManualSearchResult] = []

    # Step 1: usa DuckDuckGo per trovare le pagine ManualsLib (aggira il blocco diretto)
    ddg_results: list = []
    try:
        from ddgs import DDGS
        import asyncio as _asyncio
        loop = _asyncio.get_event_loop()
        # site: operator non funziona bene su DDG — cerchiamo "manualslib" nel testo
        query = f'manualslib "{brand} {model}" operator manual'
        ddg_results = await loop.run_in_executor(
            None,
            lambda: list(DDGS().text(query, max_results=8, safesearch="off"))
        )
    except Exception:
        pass

    # Filtra solo URL /manual/
    found_pages: dict[str, str] = {}
    for hit in ddg_results:
        url = hit.get("href") or ""
        title = hit.get("title") or ""
        if "manualslib.com/manual/" in url.lower():
            found_pages[url] = title
        if len(found_pages) >= 4:
            break

    if not found_pages:
        return results

    # Step 2: segui ogni pagina per trovare il link /download/
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    }
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            for page_url, page_title in list(found_pages.items())[:4]:
                try:
                    resp = await client.get(page_url)
                    if resp.status_code != 200:
                        results.append(ManualSearchResult(
                            url=page_url, title=f"{page_title} — ManualsLib",
                            source_type="manufacturer", language="unknown",
                            is_pdf=False, relevance_score=25,
                        ))
                        continue

                    soup = BeautifulSoup(resp.text, "html.parser")

                    dl_url = None
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        if "/download/" in href and href.startswith("/"):
                            dl_url = f"https://www.manualslib.com{href.split('?')[0].rstrip('/')}"
                            break
                        if a.get_text(strip=True).lower() in ("download", "download pdf") and href.startswith("http"):
                            dl_url = href
                            break

                    if dl_url:
                        pdf_url = f"{dl_url}?agree=yes&page=1"
                        results.append(ManualSearchResult(
                            url=pdf_url, title=f"{page_title} — ManualsLib",
                            source_type="manufacturer", language="unknown",
                            is_pdf=True,
                            relevance_score=_score_result(pdf_url, page_title, True),
                        ))
                    else:
                        results.append(ManualSearchResult(
                            url=page_url, title=f"{page_title} — ManualsLib",
                            source_type="manufacturer", language="unknown",
                            is_pdf=False, relevance_score=25,
                        ))
                except Exception:
                    continue
    except Exception:
        pass

    return results


async def _search_heavyequipments(brand: str, model: str) -> List[ManualSearchResult]:
    """
    Cerca su heavyequipments.org — repository gratuito con PDF diretti scaricabili
    (operatore, sicurezza, manutenzione) per macchinari pesanti da cantiere.
    Copre i principali brand: CAT, Komatsu, Volvo, Terex, JCB, Liebherr, ecc.
    """
    from bs4 import BeautifulSoup
    from urllib.parse import quote_plus

    results: List[ManualSearchResult] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    search_term = f"{brand} {model}"
    search_urls = [
        f"https://www.heavyequipments.org/?s={quote_plus(search_term)}",
        f"https://www.heavyequipments.org/?s={quote_plus(brand)}+{quote_plus(model)}+manual",
    ]

    found: dict[str, str] = {}  # url → title

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=headers) as client:
            for search_url in search_urls:
                try:
                    resp = await client.get(search_url)
                    if resp.status_code != 200:
                        continue

                    soup = BeautifulSoup(resp.text, "html.parser")

                    # Cerca link PDF diretti nella pagina risultati
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        if not href:
                            continue

                        # PDF diretti
                        if href.lower().endswith(".pdf") and "heavyequipments.org" in href:
                            title = a.get_text(strip=True) or href.split("/")[-1]
                            if href not in found:
                                found[href] = title

                        # Pagine di articolo/manuale (non PDF ma scaricabili dal dettaglio)
                        elif "heavyequipments.org" in href and any(
                            kw in href.lower() for kw in [
                                "manual", "operator", "service", "maintenance",
                                "instruction", brand.lower().replace(" ", "-"),
                            ]
                        ):
                            title = a.get_text(strip=True) or ""
                            parent = a.find_parent(["article", "div", "li", "h2", "h3"])
                            if parent:
                                heading = parent.find(["h2", "h3", "h4"])
                                if heading:
                                    title = heading.get_text(strip=True)
                            if not title or len(title) < 5:
                                title = href.rstrip("/").split("/")[-1].replace("-", " ").title()
                            if href not in found and len(found) < 6:
                                found[href] = title

                    # Se già trovato abbastanza, fermati
                    if len(found) >= 4:
                        break

                except Exception:
                    continue

            # Per i link alle pagine (non PDF) tenta di entrare e trovare il PDF diretto
            page_links = {url: title for url, title in found.items() if not url.lower().endswith(".pdf")}
            pdf_links = {url: title for url, title in found.items() if url.lower().endswith(".pdf")}

            for page_url, page_title in list(page_links.items())[:3]:
                try:
                    resp = await client.get(page_url)
                    if resp.status_code != 200:
                        continue
                    page_soup = BeautifulSoup(resp.text, "html.parser")
                    for a in page_soup.find_all("a", href=True):
                        href = a["href"]
                        if href.lower().endswith(".pdf") and href not in pdf_links:
                            pdf_links[href] = a.get_text(strip=True) or page_title
                except Exception:
                    continue

    except Exception:
        pass

    # PDF diretti (score alto) + pagine di riferimento se nessun PDF trovato
    for url, title in list(pdf_links.items())[:4]:
        source_type, language = _classify_source(url)
        results.append(ManualSearchResult(
            url=url,
            title=f"{title} — HeavyEquipments",
            source_type=source_type or "manufacturer",
            language=language,
            is_pdf=True,
            relevance_score=_score_result(url, title, True),
        ))

    if not pdf_links:
        for url, title in list(page_links.items())[:3]:
            results.append(ManualSearchResult(
                url=url,
                title=f"{title} — HeavyEquipments",
                source_type="manufacturer",
                language="unknown",
                is_pdf=False,
                relevance_score=15,
            ))

    return results


async def _search_manualmachine(brand: str, model: str) -> List[ManualSearchResult]:
    """
    Cerca su ManualMachine.com — database con PDF scaricabili senza login.
    Buona copertura macchinari industriali e agricoli europei.
    Struttura: /brand/{slug}/{model-slug}/ → link diretto PDF.
    """
    from bs4 import BeautifulSoup
    from urllib.parse import quote_plus, urljoin

    results: List[ManualSearchResult] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    brand_slug = re.sub(r'[^a-z0-9]', '-', brand.lower()).strip('-')
    model_slug = re.sub(r'[^a-z0-9]', '-', model.lower()).strip('-')

    urls_to_try = [
        f"https://manualmachine.com/{brand_slug}/{model_slug}/",
        f"https://manualmachine.com/search/?q={quote_plus(brand)}+{quote_plus(model)}",
        f"https://manualmachine.com/{brand_slug}/",
    ]

    model_lower = model.lower()
    found_urls: set[str] = set()

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            for url in urls_to_try:
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")

                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        abs_url = urljoin(url, href)
                        abs_lower = abs_url.lower()

                        if ".pdf" in abs_lower and abs_url not in found_urls:
                            # Filtra per rilevanza
                            link_text = a.get_text(strip=True).lower()
                            if any(t in abs_lower + link_text for t in _PDF_EXCLUDE_TERMS):
                                continue
                            found_urls.add(abs_url)
                            title = a.get_text(strip=True) or f"{brand} {model} Manual"
                            results.append(ManualSearchResult(
                                url=abs_url,
                                title=title[:200],
                                source_type="web",
                                language="unknown",
                                is_pdf=True,
                                relevance_score=_score_result(abs_url, title, True),
                            ))
                        elif ("manualmachine.com" in abs_lower
                              and model_lower.replace(" ", "-") in abs_lower
                              and abs_url not in found_urls):
                            found_urls.add(abs_url)
                            # Segui la pagina per trovare il PDF
                            try:
                                page_resp = await client.get(abs_url)
                                if page_resp.status_code == 200:
                                    page_soup = BeautifulSoup(page_resp.text, "html.parser")
                                    for pa in page_soup.find_all("a", href=True):
                                        pdf_href = pa["href"]
                                        if ".pdf" in pdf_href.lower():
                                            pdf_abs = urljoin(abs_url, pdf_href)
                                            if pdf_abs not in found_urls:
                                                found_urls.add(pdf_abs)
                                                results.append(ManualSearchResult(
                                                    url=pdf_abs,
                                                    title=pa.get_text(strip=True) or f"{brand} {model}",
                                                    source_type="web",
                                                    language="unknown",
                                                    is_pdf=True,
                                                    relevance_score=_score_result(pdf_abs, f"{brand} {model}", True),
                                                ))
                            except Exception:
                                pass

                    if len(results) >= 3:
                        break
                except Exception:
                    continue
    except Exception:
        pass

    return results[:3]


async def _search_safemanuals(brand: str, model: str) -> List[ManualSearchResult]:
    """
    Cerca su SafeManuals.com tramite DuckDuckGo (il sito blocca scraping diretto da IP cloud).
    Poi segue i link trovati per estrarre PDF diretti.
    """
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin

    results: List[ManualSearchResult] = []

    # Step 1: DuckDuckGo site: search per trovare le pagine SafeManuals
    ddg_results: list = []
    try:
        from ddgs import DDGS
        import asyncio as _asyncio
        loop = _asyncio.get_event_loop()
        query = f'safemanuals "{brand} {model}" manual'
        ddg_results = await loop.run_in_executor(
            None,
            lambda: list(DDGS().text(query, max_results=8, safesearch="off"))
        )
    except Exception:
        pass

    found_pages: dict[str, str] = {}
    found_pdfs: dict[str, str] = {}

    # Aggregatori PDF affidabili accettati anche se non sono safemanuals.com
    _SAFE_AGGREGATORS = ("safemanuals.com", "all-guidesbox.com", "manualmachine.com",
                         "all-guides.com", "manualzz.com")

    for hit in ddg_results:
        url = hit.get("href") or ""
        title = hit.get("title") or ""
        url_l = url.lower()
        if url_l.endswith(".pdf"):
            found_pdfs[url] = title
        elif any(a in url_l for a in _SAFE_AGGREGATORS):
            found_pages[url] = title
        if len(found_pages) + len(found_pdfs) >= 5:
            break

    if not found_pages and not found_pdfs:
        return results

    # Step 2: segui le pagine per trovare PDF diretti
    if found_pages:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
        }
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
                for page_url, page_title in list(found_pages.items())[:3]:
                    try:
                        resp = await client.get(page_url)
                        if resp.status_code != 200:
                            continue
                        soup = BeautifulSoup(resp.text, "html.parser")
                        for a in soup.find_all("a", href=True):
                            href = a["href"]
                            abs_url = urljoin(page_url, href)
                            if abs_url.lower().endswith(".pdf") and abs_url not in found_pdfs:
                                found_pdfs[abs_url] = a.get_text(strip=True) or page_title
                            text = a.get_text(strip=True).lower()
                            if any(kw in text for kw in ["download", "view pdf", "open pdf"]):
                                if abs_url not in found_pdfs and not href.startswith("#"):
                                    found_pdfs[abs_url] = page_title
                    except Exception:
                        continue
        except Exception:
            pass

    for url, title in list(found_pdfs.items())[:4]:
        is_pdf = url.lower().endswith(".pdf")
        source_type, language = _classify_source(url)
        results.append(ManualSearchResult(
            url=url, title=f"{title} — SafeManuals",
            source_type=source_type or "web", language=language,
            is_pdf=is_pdf,
            relevance_score=_score_result(url, title, is_pdf),
        ))

    if not found_pdfs:
        for url, title in list(found_pages.items())[:2]:
            results.append(ManualSearchResult(
                url=url, title=f"{title} — SafeManuals",
                source_type="web", language="unknown",
                is_pdf=False, relevance_score=18,
            ))

    return results


async def _search_all_guides(brand: str, model: str) -> List[ManualSearchResult]:
    """
    Cerca su all-guides.com — aggregatore con buona copertura macchine industriali
    europee. Ha PDF diretti scaricabili senza login. Struttura:
    /brand/{slug}/ → lista modelli → /manual/{id}/ → PDF diretto.
    """
    from bs4 import BeautifulSoup
    from urllib.parse import quote_plus, urljoin

    results: List[ManualSearchResult] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    brand_slug = re.sub(r'[^a-z0-9]', '-', brand.lower()).strip('-')
    model_lower = model.lower()

    search_urls = [
        f"https://all-guides.com/search/?q={quote_plus(brand)}+{quote_plus(model)}",
        f"https://all-guides.com/brand/{brand_slug}/",
    ]

    found_pages: dict[str, str] = {}
    found_pdfs: dict[str, str] = {}

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            for url in search_urls:
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")

                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        abs_url = urljoin(url, href)
                        abs_lower = abs_url.lower()

                        if abs_lower.endswith(".pdf") and abs_url not in found_pdfs:
                            title = a.get_text(strip=True) or f"{brand} {model}"
                            found_pdfs[abs_url] = title
                        elif "all-guides.com" in abs_lower and (
                            model_lower.replace(" ", "-") in abs_lower
                            or model_lower.replace(" ", "") in abs_lower
                        ) and "/manual/" in abs_lower and abs_url not in found_pages:
                            title = a.get_text(strip=True) or f"{brand} {model}"
                            if len(found_pages) < 4:
                                found_pages[abs_url] = title

                    if len(found_pdfs) >= 3:
                        break
                except Exception:
                    continue

            # Segui pagine manuale per trovare PDF diretti
            for page_url, page_title in list(found_pages.items())[:3]:
                try:
                    resp = await client.get(page_url)
                    if resp.status_code != 200:
                        continue
                    page_soup = BeautifulSoup(resp.text, "html.parser")
                    for a in page_soup.find_all("a", href=True):
                        href = a["href"]
                        abs_url = urljoin(page_url, href)
                        if abs_url.lower().endswith(".pdf") and abs_url not in found_pdfs:
                            found_pdfs[abs_url] = a.get_text(strip=True) or page_title
                        # Cerca link "Download PDF" o "Download"
                        text = a.get_text(strip=True).lower()
                        if any(kw in text for kw in ["download", "pdf"]) and "/download/" in abs_url.lower():
                            if abs_url not in found_pdfs:
                                found_pdfs[abs_url] = page_title
                except Exception:
                    continue

    except Exception:
        pass

    for url, title in list(found_pdfs.items())[:4]:
        source_type, language = _classify_source(url)
        results.append(ManualSearchResult(
            url=url,
            title=f"{title} — All-Guides",
            source_type=source_type or "web",
            language=language,
            is_pdf=True,
            relevance_score=_score_result(url, title, True),
        ))

    if not found_pdfs:
        for url, title in list(found_pages.items())[:2]:
            results.append(ManualSearchResult(
                url=url,
                title=f"{title} — All-Guides",
                source_type="web",
                language="unknown",
                is_pdf=False,
                relevance_score=18,
            ))

    return results


async def _search_manualsplus(brand: str, model: str) -> List[ManualSearchResult]:
    """
    Cerca su Manuals+ (manuals.plus) — database emergente con testo del manuale
    direttamente nella pagina HTML (oltre al PDF), ideale per l'estrazione AI.
    Database diverso da ManualsLib: buona copertura macchinari industriali.
    """
    from bs4 import BeautifulSoup
    from urllib.parse import quote_plus

    results: List[ManualSearchResult] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    search_url = f"https://manuals.plus/?s={quote_plus(brand + ' ' + model)}"

    found_pages: dict[str, str] = {}
    found_pdfs: dict[str, str] = {}

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=headers) as client:
            try:
                resp = await client.get(search_url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")

                    # Cerca link PDF diretti
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        if not href:
                            continue
                        if href.lower().endswith(".pdf"):
                            title = a.get_text(strip=True) or href.split("/")[-1]
                            found_pdfs[href] = title
                        elif "manuals.plus" in href and len(href) > 25:
                            # Pagine manuale: URL tipo /brand-model-user-manual/
                            if any(kw in href.lower() for kw in [
                                brand.lower().replace(" ", "-"),
                                model.lower().replace(" ", "-"),
                                "manual", "instruction",
                            ]):
                                title = a.get_text(strip=True) or ""
                                parent = a.find_parent(["article", "div", "li"])
                                if parent:
                                    h = parent.find(["h2", "h3", "h4"])
                                    if h:
                                        title = h.get_text(strip=True)
                                if not title or len(title) < 4:
                                    title = href.rstrip("/").split("/")[-1].replace("-", " ").title()
                                if href not in found_pages and len(found_pages) < 4:
                                    found_pages[href] = title
            except Exception:
                pass

            # Segui le pagine manuale per estrarre PDF diretti
            for page_url, page_title in list(found_pages.items())[:3]:
                try:
                    resp = await client.get(page_url)
                    if resp.status_code != 200:
                        continue
                    page_soup = BeautifulSoup(resp.text, "html.parser")
                    for a in page_soup.find_all("a", href=True):
                        href = a["href"]
                        if href.lower().endswith(".pdf") and href not in found_pdfs:
                            found_pdfs[href] = a.get_text(strip=True) or page_title
                except Exception:
                    continue

    except Exception:
        pass

    for url, title in list(found_pdfs.items())[:4]:
        is_pdf = url.lower().endswith(".pdf")
        source_type, language = _classify_source(url)
        results.append(ManualSearchResult(
            url=url,
            title=f"{title} — Manuals+",
            source_type=source_type or "web",
            language=language,
            is_pdf=is_pdf,
            relevance_score=_score_result(url, title, is_pdf),
        ))

    # Pagine HTML con testo manuale — utili per analisi anche senza PDF
    if not found_pdfs:
        for url, title in list(found_pages.items())[:2]:
            results.append(ManualSearchResult(
                url=url,
                title=f"{title} — Manuals+",
                source_type="web",
                language="unknown",
                is_pdf=False,
                relevance_score=18,  # Leggermente più alto di SafeManuals: testo leggibile da AI
            ))

    return results


# ── Scraping PDF da pagine HTML ───────────────────────────────────────────────

# Parole che indicano un PDF NON pertinente — ricambi, cataloghi prezzo, schemi elettrici, brochure
_PDF_EXCLUDE_TERMS = frozenset([
    "spare", "parts", "ricambi", "catalog", "listino", "price", "pricelist",
    "schema", "wiring", "electrical", "circuit", "exploded",
    # Documenti ambientali / commerciali — non sono manuali d'uso
    "brochure", "environmental", "epd", "declaration", "sustainability",
    "product-declaration", "enviro", "emissions", "carbon",
])

# Parole che indicano un PDF pertinente — manuale d'uso
_PDF_INCLUDE_TERMS = frozenset([
    "manual", "manuale", "handbook", "guide", "guida", "istruz", "operator",
    "uso", "utente", "user", "operating", "operation", "safety", "sicurezza",
    "maintenance", "manutenzione",
])


async def _scrape_page_for_pdf_links(
    url: str, brand: str, model: str, source_type: str
) -> list[ManualSearchResult]:
    """
    Scarica una pagina HTML e cerca link diretti a file PDF.
    Filtra i PDF non pertinenti (ricambi, cataloghi) e valuta la rilevanza
    in base a brand, model e parole chiave nei link.
    """
    from urllib.parse import urlparse, urljoin

    try:
        async with httpx.AsyncClient(
            timeout=10, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ManualFinder/1.0)"},
        ) as client:
            resp = await client.get(url)
            if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", ""):
                return []
            html = resp.text
    except Exception:
        return []

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        # Fallback regex se BeautifulSoup non disponibile
        import re as _re
        pdf_urls = _re.findall(r'href=["\']([^"\']*\.pdf)["\']', html, _re.IGNORECASE)
        soup = None

    base = urlparse(url)
    brand_lower = brand.lower()
    model_lower = model.lower()
    seen: set[str] = set()
    results: list[ManualSearchResult] = []

    if soup:
        candidates = [(tag.get("href", ""), tag.get_text(strip=True)) for tag in soup.find_all("a", href=True)]
    else:
        candidates = [(u, "") for u in pdf_urls]  # type: ignore[name-defined]

    for href, link_text in candidates:
        if not href:
            continue

        # Normalizza URL relativo → assoluto
        abs_url = urljoin(url, href)
        if not abs_url.startswith("http"):
            continue

        # Deve terminare con .pdf (o contenere .pdf? nel query string)
        lower_url = abs_url.lower()
        if ".pdf" not in lower_url:
            continue

        if abs_url in seen:
            continue
        seen.add(abs_url)

        combined = (lower_url + " " + link_text.lower())

        # Scarta PDF non pertinenti
        if any(t in combined for t in _PDF_EXCLUDE_TERMS):
            continue

        # Calcola score
        score = 15  # base per PDF trovato su pagina HTML
        if brand_lower in combined:
            score += 15
        if model_lower in combined:
            score += 20
        if any(t in combined for t in _PDF_INCLUDE_TERMS):
            score += 20
        # Bonus dominio istituzionale o produttore
        domain = urlparse(abs_url).netloc.lower()
        if domain in _INSTITUTIONAL_DOMAINS:
            score += 25
        elif domain in _MANUFACTURER_DOMAINS:
            score += 15

        title = link_text or abs_url.split("/")[-1].replace("-", " ").replace("_", " ").removesuffix(".pdf")
        results.append(ManualSearchResult(
            url=abs_url,
            title=title[:200],
            source_type=source_type,
            language="unknown",
            is_pdf=True,
            relevance_score=min(score, 80),  # cap: inferiore ai risultati di ricerca diretti
        ))

    results.sort(key=lambda r: r.relevance_score, reverse=True)
    return results[:3]  # Max 3 PDF per pagina


async def scrape_html_results_for_pdfs(
    html_results: list[ManualSearchResult],
    brand: str,
    model: str,
    max_pages: int = 4,
) -> list[ManualSearchResult]:
    """
    Quando la ricerca non trova PDF diretti, scarica le prime N pagine HTML
    e cerca link a PDF nascosti dentro di esse.
    Esegue i download in parallelo per minimizzare la latenza.
    """
    targets = [r for r in html_results if not r.is_pdf][:max_pages]
    if not targets:
        return []

    tasks = [
        _scrape_page_for_pdf_links(r.url, brand, model, r.source_type)
        for r in targets
    ]
    results_per_page = await asyncio.gather(*tasks, return_exceptions=True)

    found: list[ManualSearchResult] = []
    seen_urls: set[str] = set()
    for batch in results_per_page:
        if not isinstance(batch, list):
            continue
        for r in batch:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                found.append(r)

    found.sort(key=lambda r: r.relevance_score, reverse=True)
    return found


async def _scrape_producer_site(brand: str, model: str) -> list[ManualSearchResult]:
    """
    Scraping diretto del sito del produttore quando il dominio è noto.
    Strategia: prova le URL candidate più probabili per i manuali
    (es. /Pdf/, /manuals/, /downloads/, /support/) senza dipendere dalla ricerca.
    Utile per produttori italiani che non compaiono nei motori di ricerca ma
    hanno PDF pubblici sul proprio sito (es. leadermec.it/Pdf/).
    """
    from urllib.parse import urljoin

    normalized = _normalize_brand(brand)
    # Cerca il dominio del produttore nel dict manufacturer_sites
    _manufacturer_sites_local = {
        "leadermec": "leadermec.it",
        "ermaksan": "ermaksan.com",
        "durma": "durmapress.com",
        "bystronic": "bystronic.com",
        "trumpf": "trumpf.com",
        "amada": "amada.com",
        "salvagnini": "salvagnini.com",
        "ficep": "ficep.it",
        "gasparini": "gasparini.com",
        "euromac": "euromac.it",
        "rainer": "rainer.it",
        "caterpillar": "cat.com",
        "manitou": "manitou.com",
        "haulotte": "haulotte.com",
        "jlg": "jlg.com",
        "genie": "genielift.com",
        "tadano": "tadano.com",
        "fassi": "fassi.com",
        "wacker": "wackerneuson.com",
        "ceccato": "ceccato.com",
        "kaeser": "kaeser.com",
    }

    domain = _manufacturer_sites_local.get(normalized)
    if not domain:
        # Prova a costruire un dominio ragionevole (brand.it o brand.com)
        brand_slug = re.sub(r'[^a-z0-9]', '', normalized)
        candidates_domain = [f"{brand_slug}.it", f"{brand_slug}.com"]
    else:
        candidates_domain = [domain]

    # Percorsi comuni dove i produttori mettono i PDF
    # Ordinati per probabilità decrescente
    pdf_paths = [
        "/Pdf/",
        "/pdf/",
        "/manuals/",
        "/manuali/",
        "/downloads/",
        "/download/",
        "/support/manuals/",
        "/files/manuals/",
        "/documenti/",
        "/documents/",
        "/resources/manuals/",
        "/media/manuals/",
    ]

    model_slug = re.sub(r'\s+', '%20', model.strip())
    model_slug_dash = re.sub(r'\s+', '-', model.strip())
    model_slug_under = re.sub(r'\s+', '_', model.strip())

    found: list[ManualSearchResult] = []
    seen_urls: set[str] = set()

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ManualFinder/1.0)",
        "Accept": "text/html,application/pdf,*/*",
    }

    async with httpx.AsyncClient(timeout=10, follow_redirects=True, headers=headers) as client:
        for domain in candidates_domain:
            base_url = f"https://{domain}"

            # 1. Prova URL dirette costruite con nome modello (senza passare da pagine HTML)
            direct_candidates = []
            for path in pdf_paths[:6]:  # Solo i percorsi più probabili
                for slug in [model_slug, model_slug_dash, model_slug_under]:
                    direct_candidates.append(f"{base_url}{path}{slug}.pdf")
                    direct_candidates.append(f"{base_url}{path}{brand}%20{slug}.pdf")
                    direct_candidates.append(f"{base_url}{path}{brand}-{slug}.pdf")

            for url in direct_candidates:
                if url in seen_urls:
                    continue
                try:
                    resp = await client.head(url, timeout=5)
                    if resp.status_code == 200 and (
                        "pdf" in resp.headers.get("content-type", "").lower()
                        or url.lower().endswith(".pdf")
                    ):
                        seen_urls.add(url)
                        found.append(ManualSearchResult(
                            url=url,
                            title=f"{brand} {model} — Manuale (sito produttore)",
                            source_type="manufacturer",
                            language="unknown",
                            is_pdf=True,
                            relevance_score=72,  # Alta priorità: PDF diretto dal produttore
                        ))
                except Exception:
                    continue

            if found:
                break  # Trovato qualcosa sul primo dominio, non tentare gli altri

            # 2. Se nessun URL diretto funziona, scraping della homepage + pagine PDF
            for path in pdf_paths[:4]:
                listing_url = f"{base_url}{path}"
                if listing_url in seen_urls:
                    continue
                seen_urls.add(listing_url)
                try:
                    resp = await client.get(listing_url, timeout=8)
                    if resp.status_code != 200:
                        continue
                    ct = resp.headers.get("content-type", "")
                    if "text/html" not in ct:
                        continue

                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "html.parser")
                    model_lower = model.lower()
                    brand_lower = brand.lower()

                    for tag in soup.find_all("a", href=True):
                        href = tag["href"]
                        abs_url = urljoin(listing_url, href)
                        if ".pdf" not in abs_url.lower():
                            continue
                        if abs_url in seen_urls:
                            continue

                        link_text = tag.get_text(strip=True).lower()
                        combined = (abs_url.lower() + " " + link_text)

                        # Filtra: scarta ricambi e brochure
                        if any(t in combined for t in _PDF_EXCLUDE_TERMS):
                            continue

                        # Calcola score: priorità ai link che contengono il modello
                        score = 60
                        if model_lower in combined:
                            score += 15
                        if brand_lower in combined:
                            score += 5
                        if any(t in combined for t in _PDF_INCLUDE_TERMS):
                            score += 10

                        seen_urls.add(abs_url)
                        title = tag.get_text(strip=True) or abs_url.split("/")[-1].replace("%20", " ").removesuffix(".pdf")
                        found.append(ManualSearchResult(
                            url=abs_url,
                            title=title[:200],
                            source_type="manufacturer",
                            language="unknown",
                            is_pdf=True,
                            relevance_score=min(score, 80),
                        ))
                except Exception:
                    continue

            if found:
                break

    found.sort(key=lambda r: r.relevance_score, reverse=True)
    return found[:5]  # Max 5 PDF dal sito produttore