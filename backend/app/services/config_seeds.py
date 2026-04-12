"""
Seed iniziale per config_lists/config_maps/domain_classifications/brand_machine_type_hints.
Eseguito all'avvio (main.py on_startup) DOPO le migrazioni DB. Idempotente:
ogni seed_*_if_empty inserisce solo se la chiave/tipo è ancora vuota.

I valori seed sono definiti QUI (ex-hardcode da search_service, vision_service,
source_manager, pdf_service, manufacturer_email_service, analysis_service,
routers/analyze, routers/feedback). Una volta seedato, il codice legge dal DB
via config_service e l'admin può modificare tutto dal pannello.
"""
import logging

from app.services import config_service

logger = logging.getLogger(__name__)


# ── LIST: safety keywords (pdf_service.SAFETY_KEYWORDS) ─────────────────────
_SAFETY_KEYWORDS = {
    "rischio", "pericolo", "sicurezza", "protezione", "dpi", "avvertenza",
    "avviso", "attenzione", "warning", "danger", "risk", "safety", "hazard",
    "proteggere", "indossare", "vietato", "proibito", "dispositivo",
    "guanti", "elmetto", "casco", "occhiali", "stivali", "imbracatura",
}

# ── LIST: office brands da escludere in titoli (analyze.OFFICE_BRANDS_IN_TITLE) ──
_OFFICE_BRANDS_IN_TITLE = {
    "ricoh", "canon", "epson", "brother", "xerox", "konica", "kyocera",
    "streampunch", "fellowes", "leitz", "rexel", "acco", "dymo",
    "samsung", "lg", "sony", "philips", "siemens home",
}

# ── LIST: pattern URL QR service (analyze._QR_SERVICE_PATTERNS) ─────────────
_QR_SERVICE_PATTERNS = {
    "service/scan", "/scan?", "/aftersales", "/support/scan",
    "cat.com/service", "komatsu.com/scan", "/qrcode/", "/qr?",
    "parts.cat.com", "sos.cat.com",
}

# ── LIST: PROBLEMI feedback (routers/feedback.PROBLEMI_OPTIONS) ─────────────
_PROBLEMI_OPTIONS = {
    "norme_errate", "checklist_incompleta", "dati_macchina_sbagliati",
    "prescrizioni_inutilizzabili", "fonte_non_affidabile",
}

# ── LIST: valori "null" stringa (analysis_service._NULL_STR_VALUES) ─────────
_NULL_STR_VALUES = {"null", "none", "n/a", "non previsto", "non applicabile"}

# ── LIST: email rejection prefixes (manufacturer_email_service) ─────────────
_EMAIL_REJECT_PREFIXES = {
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "privacy", "gdpr", "dpo", "legal", "compliance",
    "marketing", "press", "media", "pr", "comunicazione",
    "hr", "careers", "lavora", "jobs", "recruiting",
    "billing", "fatturazione", "amministrazione",
    "webmaster", "admin",
}
_EMAIL_IT_PREFIXES = {
    "italy", "italia", "it.service", "it.support", "it.assistenza", "assistenza.it",
}
_EMAIL_SERVICE_PREFIXES = {
    "service", "assistenza", "support", "supporto", "tecnico", "tecnica",
    "after-sales", "aftersales", "post-vendita", "postvend",
    "customer.service", "customerservice", "helpdesk", "help-desk",
    "workshop", "officina",
}

# ── LIST: generic/accessory signals (vision_service) ────────────────────────
_GENERIC_TYPES = {"macchinario", "macchina", "attrezzatura", "equipment", "machine",
                  "accessorio", "attrezzo", "attachment", "tool"}
_ACCESSORY_SIGNALS = {
    "testa idraulica", "testa girevole", "rotatore idraulico", "rotatore",
    "benna a polipo", "benna frantoio", "benna carico", "benna",
    "polipo", "pinza demolizione", "pinza", "cesoia demolitrice",
    "martello demolitore idraulico da escavatore",
    "bilancino di sollevamento", "bilancino",
    "paranco manuale", "paranco",
    "gancio di sollevamento",
    "attrezzo intercambiabile", "testina di scavo", "scarificatore",
    "compattatore vibrante da escavatore",
    "forche da magazzino",
    "testa saldante",
}

# ── LIST: tipi machine set — edilizia/officina (search_service) ─────────────
_EDILIZIA_MACHINE_TYPES = {
    "escavatore", "escavatori", "gru", "gru mobile", "gru a torre", "camion gru",
    "carrello elevatore", "muletto", "sollevatore telescopico",
    "pala caricatrice", "pala meccanica", "dumper", "autocarro ribaltabile",
    "rullo compressore", "rullo compattatore", "compressore", "finitrice",
    "piattaforma di lavoro mobile elevabile ple", "pompa calcestruzzo",
    "terna", "terne", "retroescavatore", "bulldozer", "apripista",
    "betoniera", "martello demolitore",
}
_OFFICINA_MACHINE_TYPES = {
    "pressa piegatrice", "piegatrice", "press brake", "cesoie trancia",
    "punzonatrice pressa", "macchina taglio laser", "tornio macchina utensile",
    "fresatrice macchina utensile", "rettificatrice macchina utensile",
}

# ── LIST: no-patentino / no-verifiche types (analysis_service) ──────────────
_NO_PATENTINO_TYPES = {
    "compressore", "motocompressore", "compressore d'aria", "compressore aria",
    "gruppo elettrogeno", "generatore", "generatore elettrico",
    "piastra vibrante", "costipatore",
    "rullo compattatore", "rullo compressore", "rullo", "compattatore",
    "bulldozer", "apripista", "betoniera",
    "saldatrice", "saldatrice mig", "saldatrice tig", "saldatrice ad arco",
    "pressa", "pressa idraulica", "pressa piegatrice", "piegatrice",
    "punzonatrice", "cesoie", "tranciatrice",
    "tornio", "fresatrice", "rettificatrice",
    "laser", "macchina taglio laser", "taglio laser",
    "troncatrice", "troncatrice per alluminio",
    "benna a polipo", "benna carico-pietrisco", "benna", "polipo",
    "pinza demolitrice", "martello demolitore", "vibratore per calcestruzzo",
}
_NO_VERIFICHE_TYPES = _NO_PATENTINO_TYPES | {"dumper", "finitrice", "escavatore", "escavatore idraulico"}

# ── MAP: badge labels / colors / affidabilita / fonte_tipo / disclaimers (source_manager) ──
_BADGE_LABELS = {
    "A": "Manuale produttore",
    "B": "Manuale produttore + INAIL",
    "C": "Manuale categoria + INAIL",
    "D": "Manuale categoria",
    "E": "Quaderno INAIL",
    "F": "AI inference",
}
_BADGE_COLORS = {
    "A": "#16a34a", "B": "#16a34a", "C": "#d97706",
    "D": "#d97706", "E": "#0369a1", "F": "#dc2626",
}
_AFFIDABILITA = {"A": 95, "B": 90, "C": 65, "D": 55, "E": 70, "F": 30}
_FONTE_TIPO = {
    "A": "pdf", "B": "inail+produttore", "C": "inail+produttore",
    "D": "pdf", "E": "inail", "F": "fallback_ai",
}
_DISCLAIMERS = {
    "A": "",
    "B": "",
    "C": ("Manuale specifico del produttore non disponibile. "
          "Analisi basata su manuale di categoria e quaderno INAIL. "
          "Verificare i dati tecnici specifici direttamente sulla macchina."),
    "D": ("Manuale specifico e quaderno INAIL non disponibili. "
          "Analisi basata su manuale di categoria. "
          "Le prescrizioni normative devono essere verificate in campo."),
    "E": ("Manuale del produttore non disponibile. "
          "Dati tecnici operativi basati su quaderno INAIL. "
          "Verificare i componenti specifici direttamente in campo."),
    "F_no_rag": ("Nessuna fonte documentale disponibile per questa macchina. "
                 "La scheda è generata interamente da AI sulla base della categoria macchina. "
                 "Tutti i dati tecnici devono essere verificati direttamente in campo. "
                 "Non utilizzare le prescrizioni senza verifica."),
    "F_rag": ("Nessun PDF disponibile per questa macchina. "
              "La scheda è generata da AI supportata dal corpus normativo indicizzato "
              "(D.Lgs. 81/08 + quaderni INAIL). "
              "I dati tecnici specifici devono comunque essere verificati in campo."),
    "F": ("Nessuna fonte documentale disponibile per questa macchina. "
          "La scheda è generata da AI sulla base della categoria macchina e del corpus normativo. "
          "Tutti i dati tecnici devono essere verificati direttamente in campo. "
          "Non utilizzare le prescrizioni senza verifica."),
}

# ── MAP: INAIL_MACHINE_TYPES (search_service) — map_key "inail_search_terms" ──
# Qui manteniamo anche nel DB su machine_types.inail_search_term, ma per chiavi
# che non sono tipi canonici (alias/abbreviazioni) teniamo anche la mappa.
_INAIL_MACHINE_TYPES = {
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
    "minipala": "minipala",
    "minipala gommata": "minipala",
    "minipala cingolata": "minipala",
    "skid steer": "minipala",
    "benna": "benna",
    "benna a polipo": "benna",
    "benna carico-pietrisco": "benna",
    "testa saldante": "saldatrice",
    "attrezzatura speciale": None,
}

# ── MAP: EN→IT machine type (vision_service) ────────────────────────────────
_EN_TO_IT_MACHINE_TYPE = {
    "reach stacker": "carrello portacontainer",
    "stacker": "carrello portacontainer",
    "scissor lift": "piattaforma a forbice",
    "boom lift": "piattaforma aerea a braccio",
    "aerial work platform": "piattaforma aerea",
    "awp": "piattaforma aerea",
    "forklift": "carrello elevatore",
    "telehandler": "sollevatore telescopico",
    "telescopic handler": "sollevatore telescopico",
    "excavator": "escavatore",
    "wheel loader": "pala caricatrice",
    "loader": "pala caricatrice",
    "bulldozer": "bulldozer",
    "dumper": "dumper",
    "compactor": "rullo compattatore",
    "crane": "gru mobile",
    "tower crane": "gru a torre",
    "concrete pump": "pompa calcestruzzo",
    "paver": "finitrice stradale",
    "grader": "livellatrice",
    "trencher": "scavatrice a catena",
    "skid steer": "minipala",
    "backhoe": "terna",
    "backhoe loader": "terna",
    "generator": "generatore",
    "compressor": "compressore",
    "concrete mixer": "betoniera",
    "mixer": "betoniera",
    "welder": "saldatrice",
}

# ── MAP: emergency types → keywords (analysis_service._EMERGENCY_TYPES) ─────
_EMERGENCY_TYPES = {
    "incendio":            ["incendio", "fuoco", "fire"],
    "ribaltamento":        ["ribaltamento", "capovolgimento", "rollover"],
    "cedimento_freni":     ["freni", "idraulico", "cedimento freni", "cedimento idraulico", "brake"],
    "investimento_persone":["investimento", "persona investita", "pedestrian", "persone"],
    "folgorazione":        ["folgorazione", "elettrico", "electrocution", "scarica"],
    "seppellimento":       ["seppellimento", "crollo", "burial", "collapse"],
}

# ── MAP: title positive/negative weights (search_service) ───────────────────
_TITLE_POSITIVE = [
    ("manuale operatore", 25), ("manuale uso e manutenzione", 25),
    ("operator manual", 25), ("user manual", 20), ("manuale d'uso", 20),
    ("istruzioni per l'uso", 20), ("istruzioni d'uso", 20),
    ("safety manual", 20), ("manuale sicurezza", 20),
    ("manuale", 15), ("istruzioni", 15), ("manual", 15), ("operator", 12),
    ("sicurezza", 10), ("safety", 10), ("uso", 8), ("maintenance", 8),
    ("scheda tecnica", 5), ("datasheet", 5),
    ("EN 12622", 8), ("EN 13736", 8), ("EN 693", 8),
]
_TITLE_NEGATIVE = [
    ("spare parts", -25), ("parts catalog", -25), ("catalogo ricambi", -25),
    ("parts list", -20), ("listino", -20), ("price list", -20),
    ("workshop manual", -15), ("service manual", -15), ("repair manual", -15),
    ("manuale officina", -15), ("manuale riparazione", -15),
    ("brochure", -20), ("product sheet", -15), ("scheda prodotto", -15),
    ("scheda commerciale", -15), ("flyer", -15), ("volantino", -15),
    ("wiring diagram", -10), ("schema elettrico", -10),
]

# ── DOMAINS ─────────────────────────────────────────────────────────────────
_MANUFACTURER_DOMAINS = [
    "caterpillar.com", "cat.com", "komatsu.com", "manitou.com", "atlascopco.com",
    "liebherr.com", "volvoce.com", "jcb.com", "casece.com", "deere.com",
    "haulotte.com", "fassi.com", "manitowoc.com", "tadano.com",
    "bobcat.com", "wackerneuson.com", "putzmeister.com", "schwing.de",
    "genielift.com", "skyjack.com", "jlg.com", "terex.com",
    "leadermec.it", "ermaksan.com", "durmapress.com", "bystronic.com",
    "trumpf.com", "amada.com", "prima-industrie.com", "salvagnini.com",
    "ficep.it", "gasparini.com", "metallurgie.it", "safan-e-brake.com",
    "cidan.com", "euromac.it", "rainer.it", "promecam.it",
    "daito.it", "bendmak.com", "yangli.com", "accurl.com",
    "ceccato.com", "fini-group.com", "abac.com", "kaeser.com",
    "jcbitalia.it", "komatsu-italia.it", "liebherr-italia.com",
    "manitou-italia.it", "haulotte-italia.com", "atlascopco.it",
    "volvoce.it", "cnh-italia.com", "caterpillar-italia.com",
    "wackerneuson.it", "tadano-italia.com",
]
_RENTAL_DOMAINS = [
    "loxam.it", "boels.it", "mollonoleggio.com", "lorini.it",
    "kiloutou.it", "riwal.com", "cgt.it",
]
_INSTITUTIONAL_DOMAINS = [
    "inail.it", "formediltorinofsc.it", "puntosicuro.it",
    "salute.regione.emilia-romagna.it", "ats-milano.it",
    "suva.ch", "osha.europa.eu", "dguv.de", "ucimu.it", "enama.it",
]
_AGGREGATOR_DOMAINS = [
    "manualslib.com", "heavyequipments.org", "manualmachine.com", "manualeIstruzioni.it",
]
_INAIL_MIRROR_DOMAINS = [
    "necsi.it", "aliseo", "ispesl.it", "dors.it",
    "salute.gov.it", "lavoro.gov.it", "inail.it",
    "ausl.", "asl.", "spresal", "spisal",
    "portaleagenti.it", "sicurezzaentipubblici",
    "formediltorinofsc.it", "puntosicuro.it", "suva.ch",
]
# (brand, domain) tuples per manufacturer_primary/secondary — kind con brand valorizzato
_MANUFACTURER_SITES_PRIMARY = {
    "caterpillar": "cat.com", "komatsu": "komatsu.com", "manitou": "manitou.com",
    "atlascopco": "atlascopco.com", "liebherr": "liebherr.com", "volvo": "volvoce.com",
    "jcb": "jcb.com", "case": "casece.com", "deere": "deere.com", "bobcat": "bobcat.com",
    "haulotte": "haulotte.com", "fassi": "fassi.com", "manitowoc": "manitowoc.com",
    "tadano": "tadano.com", "genie": "genielift.com", "jlg": "jlg.com", "terex": "terex.com",
    "wacker neuson": "wackerneuson.com", "wacker": "wackerneuson.com",
    "atlas": "atlascopco.com", "putzmeister": "putzmeister.com", "schwing": "schwing.de",
    "leadermec": "leadermec.it", "ermaksan": "ermaksan.com", "durma": "durmapress.com",
    "bystronic": "bystronic.com", "trumpf": "trumpf.com", "amada": "amada.com",
    "prima": "prima-industrie.com", "salvagnini": "salvagnini.com", "ficep": "ficep.it",
    "gasparini": "gasparini.com", "euromac": "euromac.it", "rainer": "rainer.it",
    "safan": "safan-e-brake.com", "cidan": "cidan.com",
    "hitachi": "hitachicm.com", "merlo": "merlo.com", "grove": "manitowoc.com",
    "linde": "linde-mh.com", "still": "still.de", "jungheinrich": "jungheinrich.com",
    "doosan": "doosanequipment.com", "hyundai": "hd-hyundaice.com", "sandvik": "sandvik.com",
    "atlas copco": "atlascopco.com",
    "bomag": "bomag.com", "wirtgen": "wirtgen.com", "hamm": "hamm.ag",
    "dynapac": "dynapac.com", "ammann": "ammann-group.com", "sakai": "sakai-world.com",
    "soilmec": "soilmec.com", "bauer": "bauer.de",
    "skyjack": "skyjack.com", "snorkel": "snorkellifts.com", "dieci": "diecisrl.com",
    "ceccato": "ceccato.com", "kaeser": "kaeser.com", "fini": "fini-group.com", "abac": "abac.com",
}
_MANUFACTURER_SITES_SECONDARY = {
    "jcb": "jcbitalia.it", "komatsu": "komatsu-italia.it",
    "liebherr": "liebherr-italia.com", "manitou": "manitou-italia.it",
    "haulotte": "haulotte-italia.com", "tadano": "tadano-italia.com",
    "fassi": "fassiuk.com", "merlo": "merlogroup.com",
    "wacker neuson": "wackerneuson.com", "wacker": "wackerneuson.com",
}

# ── BRAND type map e model prefix overrides (vision_service) ────────────────
_BRAND_TYPE_MAP = {
    "polieri": "sega circolare", "casadei": "sega circolare", "scm": "sega circolare",
    "griggio": "sega circolare", "felder": "sega circolare", "altendorf": "sega circolare",
    "robland": "sega circolare", "maka": "centro di lavoro CNC per legno",
    "biesse": "centro di lavoro CNC per legno", "homag": "centro di lavoro CNC per legno",
    "weinig": "pialla quattro facce", "martin": "sega circolare",
    "oertli": "fresatrice per legno", "steton": "sega circolare",
    "trumpf": "macchina taglio laser", "bystronic": "macchina taglio laser",
    "amada": "pressa piegatrice", "salvagnini": "pannellatrice",
    "prima industrie": "macchina taglio laser", "ermaksan": "pressa piegatrice",
    "durmapress": "pressa piegatrice", "safan": "pressa piegatrice",
    "gasparini": "pressa piegatrice", "ficep": "punzonatrice", "euromac": "punzonatrice",
    "rainer": "pressa piegatrice", "promecam": "pressa piegatrice",
    "haco": "pressa piegatrice", "durma": "pressa piegatrice",
    "accurpress": "pressa piegatrice",
    "rozzi": "attrezzatura idraulica per escavatore",
    "indeco": "martello demolitore idraulico",
    "mb crusher": "frantoio da escavatore", "mb": "attrezzatura per escavatore",
    "epiroc": "martello demolitore idraulico", "furukawa": "martello demolitore idraulico",
    "atlas copco rock drills": "martello demolitore idraulico",
    "montabert": "martello demolitore idraulico", "rammer": "martello demolitore idraulico",
    "brokk": "robot demolitore", "demoq": "attrezzatura demolitiva",
    "haulotte": "piattaforma aerea", "genie": "piattaforma aerea", "jlg": "piattaforma aerea",
    "skyjack": "piattaforma a forbice", "snorkel": "piattaforma aerea",
    "niftylift": "piattaforma aerea a braccio", "manitou": "sollevatore telescopico",
    "merlo": "sollevatore telescopico", "dieci": "sollevatore telescopico",
    "jcb": "sollevatore telescopico", "faresin": "sollevatore telescopico",
    "magni": "sollevatore telescopico rotante", "tadano": "gru mobile",
    "liebherr ltm": "gru mobile", "fassi": "gru su autocarro", "hiab": "gru su autocarro",
    "palfinger": "gru su autocarro", "effer": "gru su autocarro", "pesci": "gru su autocarro",
    "atlas": "gru su autocarro",
    "caterpillar": "escavatore", "komatsu": "escavatore", "volvo ce": "escavatore",
    "volvo": "escavatore", "doosan": "escavatore", "hitachi": "escavatore",
    "hyundai": "escavatore", "case": "escavatore", "new holland": "escavatore",
    "bobcat": "minipala", "gehl": "minipala gommata", "mustang": "minipala",
    "takeuchi": "minipala", "yanmar": "minipala", "kubota": "minipala",
    "terex": "minipala", "thomas": "minipala", "new holland construction": "minipala",
    "wacker neuson": "rullo compattatore", "bomag": "rullo compattatore",
    "hamm": "rullo compattatore", "dynapac": "rullo compattatore",
    "ammann": "rullo compattatore", "sakai": "rullo compattatore",
    "wirtgen": "fresatrice stradale", "vögele": "finitrice", "vogele": "finitrice",
    "bauer": "trivella da fondazione", "soilmec": "trivella da fondazione",
    "linde": "carrello elevatore", "still": "carrello elevatore",
    "jungheinrich": "carrello elevatore", "toyota": "carrello elevatore",
    "hyster": "carrello elevatore", "yale": "carrello elevatore",
    "crown": "carrello elevatore", "nissan": "carrello elevatore",
    "mitsubishi": "carrello elevatore", "clark": "carrello elevatore",
    "om": "carrello elevatore", "konecranes": "carrello elevatore",
    "kalmar": "carrello elevatore", "cvs ferrari": "carrello elevatore",
    "cvs": "carrello elevatore", "svetruck": "carrello elevatore",
    "terberg": "carrello elevatore", "combilift": "carrello elevatore",
    "bendi": "carrello elevatore", "aisle-master": "carrello elevatore",
    "hangcha": "carrello elevatore", "heli": "carrello elevatore",
    "ep equipment": "carrello elevatore", "unicarriers": "carrello elevatore",
    "nichiyu": "carrello elevatore", "rocla": "carrello elevatore",
    "schwing": "pompa calcestruzzo", "putzmeister": "pompa calcestruzzo",
    "cifa": "pompa calcestruzzo", "sermac": "pompa calcestruzzo",
    "atlas copco": "compressore", "kaeser": "compressore", "ceccato": "compressore",
    "fini": "compressore", "abac": "compressore", "ingersoll rand": "compressore",
    "boge": "compressore", "almig": "compressore",
    "kohler": "generatore", "sdmo": "generatore", "pramac": "generatore",
    "cummins": "generatore", "perkins": "generatore",
    "vaia car": "attrezzatura speciale", "vaia": "attrezzatura speciale",
    "idrobenne": "benna idraulica", "mantovanibenne": "benna idraulica",
    "casagrande": "trivella da fondazione",
}
_MODEL_PREFIX_OVERRIDES = [
    ("caterpillar", "320", "escavatore"), ("caterpillar", "323", "escavatore"),
    ("caterpillar", "330", "escavatore"), ("caterpillar", "336", "escavatore"),
    ("caterpillar", "345", "escavatore"), ("caterpillar", "950", "pala caricatrice"),
    ("caterpillar", "966", "pala caricatrice"), ("caterpillar", "972", "pala caricatrice"),
    ("caterpillar", "420", "terna"), ("caterpillar", "432", "terna"),
    ("caterpillar", "444", "terna"), ("caterpillar", "770", "dumper"),
    ("caterpillar", "773", "dumper"),
    ("komatsu", "pc", "escavatore"), ("komatsu", "wa", "pala caricatrice"),
    ("komatsu", "hd", "dumper"), ("komatsu", "d", "bulldozer"),
    ("jcb", "3cx", "terna"), ("jcb", "4cx", "terna"), ("jcb", "js", "escavatore"),
    ("jcb", "535", "sollevatore telescopico"), ("jcb", "541", "sollevatore telescopico"),
    ("jcb", "550", "sollevatore telescopico"),
    ("haulotte", "h", "piattaforma a forbice"),
    ("haulotte", "ha", "piattaforma aerea a braccio"),
    ("haulotte", "ht", "piattaforma aerea a braccio"),
    ("genie", "gs", "piattaforma a forbice"),
    ("genie", "z-", "piattaforma aerea a braccio"),
    ("genie", "s-", "piattaforma aerea a braccio"),
    ("jlg", "2646", "piattaforma a forbice"), ("jlg", "3246", "piattaforma a forbice"),
    ("jlg", "4069", "piattaforma a forbice"),
    ("jlg", "600aj", "piattaforma aerea a braccio"),
    ("jlg", "800aj", "piattaforma aerea a braccio"),
    ("volvo", "ew", "escavatore"), ("volvo", "ec", "escavatore"),
    ("volvo", "l", "pala caricatrice"), ("volvo", "a", "dumper articolato"),
    ("liebherr", "ltm", "gru mobile"), ("liebherr", "ltc", "gru mobile"),
    ("liebherr", "ltr", "gru cingolata"), ("liebherr", "ec", "gru a torre"),
    ("liebherr", "l", "pala caricatrice"), ("liebherr", "r", "escavatore"),
    ("rozzi", "rr", "benna a polipo"), ("rozzi", "rb", "benna a mordacchia"),
    ("rozzi", "rc", "cesoia demolitrice"), ("rozzi", "rm", "martello demolitore"),
    ("vaia car", "bco", "benna carico-pietrisco"),
    ("vaia car", "kube", "testa saldante"),
    ("vaia car", "si", "saldatrice inverter"),
    ("vaia", "bco", "benna carico-pietrisco"),
    ("vaia", "kube", "testa saldante"),
    ("vaia", "si", "saldatrice inverter"),
    ("konecranes", "smv", "carrello portacontainer"),
    ("konecranes", "eco", "carrello elevatore"),
    ("konecranes", "smc", "carrello elevatore"),
    ("kalmar", "drf", "carrello portacontainer"),
    ("kalmar", "dck", "carrello portacontainer"),
    ("kalmar", "dcf", "carrello elevatore"),
    ("doosan", "b", "carrello elevatore"), ("doosan", "g", "carrello elevatore"),
    ("doosan", "d", "carrello elevatore"),
    ("doosan", "dx", "escavatore"), ("doosan", "dl", "pala caricatrice"),
    ("case", "cx", "escavatore"), ("case", "wx", "escavatore"),
    ("case", "580", "terna"), ("case", "590", "terna"),
    ("case", "621", "pala caricatrice"), ("case", "721", "pala caricatrice"),
]


def bootstrap_all_seeds() -> None:
    """Seed idempotente: popola tutte le config-list/map/domain/brand-hint vuote."""
    # Lists
    config_service.seed_list_if_empty("safety_keywords", _SAFETY_KEYWORDS)
    config_service.seed_list_if_empty("office_brands_in_title", _OFFICE_BRANDS_IN_TITLE)
    config_service.seed_list_if_empty("qr_service_patterns", _QR_SERVICE_PATTERNS)
    config_service.seed_list_if_empty("problemi_options", _PROBLEMI_OPTIONS)
    config_service.seed_list_if_empty("null_str_values", _NULL_STR_VALUES)
    config_service.seed_list_if_empty("email_reject_prefixes", _EMAIL_REJECT_PREFIXES)
    config_service.seed_list_if_empty("email_it_prefixes", _EMAIL_IT_PREFIXES)
    config_service.seed_list_if_empty("email_service_prefixes", _EMAIL_SERVICE_PREFIXES)
    config_service.seed_list_if_empty("generic_machine_types", _GENERIC_TYPES)
    config_service.seed_list_if_empty("accessory_signals", _ACCESSORY_SIGNALS)
    config_service.seed_list_if_empty("edilizia_machine_types", _EDILIZIA_MACHINE_TYPES)
    config_service.seed_list_if_empty("officina_machine_types", _OFFICINA_MACHINE_TYPES)
    config_service.seed_list_if_empty("no_patentino_types", _NO_PATENTINO_TYPES)
    config_service.seed_list_if_empty("no_verifiche_types", _NO_VERIFICHE_TYPES)

    # Maps
    config_service.seed_map_if_empty("badge_labels", _BADGE_LABELS)
    config_service.seed_map_if_empty("badge_colors", _BADGE_COLORS)
    config_service.seed_map_if_empty("affidabilita", _AFFIDABILITA)
    config_service.seed_map_if_empty("fonte_tipo", _FONTE_TIPO)
    config_service.seed_map_if_empty("disclaimers", _DISCLAIMERS)
    config_service.seed_map_if_empty("inail_machine_types", _INAIL_MACHINE_TYPES)
    config_service.seed_map_if_empty("en_to_it_machine_type", _EN_TO_IT_MACHINE_TYPE)
    config_service.seed_map_if_empty("emergency_types", _EMERGENCY_TYPES)
    # title keywords con pesi → dict con chiave = termine, valore = peso
    config_service.seed_map_if_empty(
        "title_positive", {k: w for k, w in _TITLE_POSITIVE}
    )
    config_service.seed_map_if_empty(
        "title_negative", {k: w for k, w in _TITLE_NEGATIVE}
    )

    # Domains
    config_service.seed_domains_if_empty(
        "manufacturer", [(d, None) for d in _MANUFACTURER_DOMAINS]
    )
    config_service.seed_domains_if_empty(
        "rental", [(d, None) for d in _RENTAL_DOMAINS]
    )
    config_service.seed_domains_if_empty(
        "institutional", [(d, None) for d in _INSTITUTIONAL_DOMAINS]
    )
    config_service.seed_domains_if_empty(
        "aggregator", [(d, None) for d in _AGGREGATOR_DOMAINS]
    )
    config_service.seed_domains_if_empty(
        "inail_mirror", [(d, None) for d in _INAIL_MIRROR_DOMAINS]
    )
    config_service.seed_domains_if_empty(
        "manufacturer_primary",
        [(d, b) for b, d in _MANUFACTURER_SITES_PRIMARY.items()],
    )
    config_service.seed_domains_if_empty(
        "manufacturer_secondary",
        [(d, b) for b, d in _MANUFACTURER_SITES_SECONDARY.items()],
    )

    # Brand hints
    config_service.seed_brand_hints_if_empty(_BRAND_TYPE_MAP, _MODEL_PREFIX_OVERRIDES)

    logger.info("config_seeds: bootstrap completato")
