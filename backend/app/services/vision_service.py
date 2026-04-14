"""
OCR targa identificativa tramite Groq Vision (llama-3.2-11b-vision-preview).
Fallback locale a Tesseract se quota Groq esaurita.
Estrae: brand, modello, numero di serie, anno di fabbricazione.
"""
import asyncio
import json
import logging
import re
from typing import Optional
from app.config import settings
from app.models.responses import PlateOCRResult

logger = logging.getLogger(__name__)

PLATE_OCR_PROMPT = """Sei un sistema OCR specializzato nel leggere targhe di identificazione di macchinari industriali e da cantiere.

Analizza l'immagine della targa identificativa del macchinario e estrai le seguenti informazioni in formato JSON:

{
  "brand": "nome del produttore/costruttore (es: Caterpillar, Manitou, Atlas Copco, Komatsu)",
  "model": "modello del macchinario (es: 320D, MT1440, XAS 137)",
  "machine_type": "tipo di macchinario in italiano (es: 'piattaforma aerea', 'escavatore', 'gru', 'carrello elevatore', 'sollevatore telescopico', 'compressore', 'generatore', 'pompa calcestruzzo', 'rullo compattatore', 'pala caricatrice', 'betoniera', 'martello demolitore', 'saldatrice', 'pressa piegatrice', 'fresa', 'sega')",
  "machine_category": "cantiere | industriale | agricola | sollevamento | altro",
  "serial_number": "numero di serie o matricola (se visibile)",
  "year": "anno di fabbricazione (se visibile, es: 2018)",
  "ce_marking": "presente | assente | non_visibile",
  "norme": ["EN 280", "UNI EN 474-1"],
  "qr_urls": ["URL1 decodificato da QR Code se presente nella foto", "URL2 se ci sono più QR Code"],
  "confidence": "high|medium|low",
  "raw_text": "tutto il testo visibile sulla targa, riga per riga",
  "notes": "eventuali osservazioni (es: targa parzialmente leggibile, ossidazione severa, QR Code presente ma illeggibile)"
}

REGOLE IMPORTANTI:
- Se un campo non è visibile o leggibile usa null, NON inventare dati
- Per "brand" usa il nome completo del produttore (Caterpillar, non CAT; Komatsu, non KOM; Atlas Copco, non ATLAS)
- Per "model" includi il codice alfanumerico ESATTO come appare sulla targa
- Per "machine_type": identifica il TIPO di macchina e scrivi SEMPRE in italiano.
  IMPORTANTE: il tipo di macchina raramente è scritto sulla targa. Deducilo dal CODICE MODELLO usando la tua conoscenza dei produttori industriali. Esempi per codice modello:
  - Haulotte H12SX / H15SX / H18SX / H21TX → "piattaforma a forbice"
  - Haulotte HA12 / HA16 / HA20 / HTL / Star → "piattaforma aerea a braccio"
  - Genie GS-1932 / GS-2646 / GS-3246 → "piattaforma a forbice"
  - Genie Z-45 / Z-60 / S-40 / S-60 → "piattaforma aerea a braccio"
  - JLG 2646ES / 3246ES / 4069LE → "piattaforma a forbice"
  - JLG 340AJ / 600AJ / 800AJ → "piattaforma aerea a braccio"
  - Caterpillar 320 / 323 / 330 / 336 → "escavatore"
  - Caterpillar 950 / 966 / 972 → "pala caricatrice"
  - Caterpillar 420 / 432 / 444 → "terna"
  - Manitou MT / MRT → "sollevatore telescopico"
  - Manitou M / MC → "carrello elevatore"
  - Merlo P / ROTO → "sollevatore telescopico"
  - Komatsu PC / HB → "escavatore"
  - Komatsu WA → "pala caricatrice"
  - Liebherr LTM / LTC / LTR → "gru mobile"
  - Liebherr EC-B / EC-H / 81K / 110 EC → "gru a torre"
  - Fassi F / FR → "gru su autocarro"
  - Tadano GR / ATF / AC → "gru mobile"
  - Atlas Copco XAS / XRS / XAMS → "compressore"
  - Atlas Copco QAS / QIS → "generatore"
  - Wacker Neuson DPU / RD / RD → "rullo compattatore"
  - Ammann APH / ARX / AV → "rullo compattatore"
  - Schwing / Putzmeister BP / BSA → "pompa calcestruzzo"
  - Bystronic ByStar / BySprint → "macchina taglio laser"
  - Trumpf TruLaser / TruBend → "macchina taglio laser" / "pressa piegatrice"
  - Amada HFB / HDS / EML → "pressa piegatrice"
  - Salvagnini P4 / L3 → "pannellatrice" / "macchina taglio laser"
  Se sulla targa appare un termine in inglese, traducilo:
  - "DUMPER" → "dumper", "EXCAVATOR" → "escavatore", "CRANE" → "gru"
  - "PLATFORM" / "AWP" / "AERIAL WORK PLATFORM" → "piattaforma aerea"
  - "SCISSOR LIFT" → "piattaforma a forbice"
  - "FORKLIFT" → "carrello elevatore", "TELEHANDLER" → "sollevatore telescopico"
  - "LOADER" / "WHEEL LOADER" → "pala caricatrice"
  - "ROLLER" / "COMPACTOR" → "rullo compattatore"
  - "GENERATOR" / "GENSET" → "generatore", "COMPRESSOR" → "compressore"
  - "CONCRETE PUMP" → "pompa calcestruzzo", "PAVER" → "finitrice"
  - "PRESS BRAKE" / "BENDING MACHINE" → "pressa piegatrice"
  - "CRANE TRUCK" → "camion gru"
  NON lasciare MAI termini in inglese nel campo machine_type.
  Se non riesci a identificare il tipo nemmeno dal modello, scrivi null — NON scrivere "macchinario generico" o simili.
- Per "machine_category":
  - "cantiere" = escavatori, pale caricatrici, dumper, compattatori, trivelle, pompe calcestruzzo, finitrici
  - "sollevamento" = gru (tutte le tipologie), piattaforme aeree, carrelli elevatori, sollevatori telescopici, montacarichi
  - "industriale" = presse, torni, frese, macchine taglio laser, saldatrici, compressori, generatori, betoniere
  - "agricola" = trattori, mietitrebbiatrici, seminatrici, irroratrici, falciatrici
  - "altro" = tutte le altre categorie
- Per "ce_marking": cerca il simbolo CE (Conformité Européenne) sulla targa.
  - "presente" = simbolo CE chiaramente visibile, anche se piccolo (esempio: CE 0123 o solo CE)
  - "assente" = targa visibile e completa, ma senza il simbolo CE (IMPORTANTE per macchine ante-1996)
  - "non_visibile" = targa parzialmente illeggibile, impossibile determinare con certezza
  - NOTA: la presenza/assenza della marcatura CE determina il regime normativo applicabile (Dir. 2006/42/CE vs Allegato V D.Lgs. 81/08)
- Per "norme": lista delle norme armonizzate riportate sulla targa (stringhe che iniziano per EN, UNI, ISO, IEC, prEN). Esempi: "EN 280", "UNI EN 474-1", "ISO 4309". Lista vuota [] se non presenti.
- Per "qr_urls": lista di TUTTI gli URL decodificati dai QR Code presenti nell'immagine. Ogni QR Code visibile va tentato (almeno 3 angoli leggibili). Lista vuota [] se nessun QR presente o leggibile. Se un QR è presente ma illeggibile, aggiungi "QR Code presente ma illeggibile" nelle notes. I QR Code sulle targhe spesso rimandano al manuale digitale del produttore.
- confidence "high": testo chiaramente leggibile senza dubbi
- confidence "medium": leggibile ma con qualche incertezza su alcuni caratteri o valori
- confidence "low": molto difficile da leggere, probabili errori di interpretazione
- Se la targa è plurilingue (es. "ANNO / YEAR / BAUJAHR: 2015"), estrai il valore UNA SOLA VOLTA senza ripetere per ogni lingua
- La targa può essere ossidata, sporca o con illuminazione scarsa: fai del tuo meglio

Rispondi SOLO con il JSON valido, senza markdown, senza testo aggiuntivo."""



_FB_GENERIC_TYPES = {
    None, "", "macchinario", "macchina", "attrezzatura", "equipment", "machine",
    "accessorio", "attrezzo", "attachment", "tool",
}
_FB_ACCESSORY_SIGNALS = {
    "testa idraulica", "testa girevole", "rotatore idraulico", "rotatore",
    "benna a polipo", "benna frantoio", "benna carico", "benna",
    "polipo", "pinza demolizione", "pinza", "cesoia demolitrice",
    "martello demolitore idraulico da escavatore",
    "bilancino di sollevamento", "bilancino",
    "paranco manuale", "paranco", "gancio di sollevamento",
    "attrezzo intercambiabile", "testina di scavo", "scarificatore",
    "compattatore vibrante da escavatore", "forche da magazzino", "testa saldante",
}
_FB_EN_TO_IT: dict[str, str] = {
    "reach stacker": "carrello portacontainer", "stacker": "carrello portacontainer",
    "scissor lift": "piattaforma a forbice", "boom lift": "piattaforma aerea a braccio",
    "aerial work platform": "piattaforma aerea", "awp": "piattaforma aerea",
    "forklift": "carrello elevatore", "telehandler": "sollevatore telescopico",
    "telescopic handler": "sollevatore telescopico", "excavator": "escavatore",
    "wheel loader": "pala caricatrice", "loader": "pala caricatrice",
    "bulldozer": "bulldozer", "dumper": "dumper", "compactor": "rullo compattatore",
    "crane": "gru mobile", "tower crane": "gru a torre",
    "concrete pump": "pompa calcestruzzo", "paver": "finitrice stradale",
    "grader": "livellatrice", "trencher": "scavatrice a catena",
    "skid steer": "minipala", "backhoe": "terna", "backhoe loader": "terna",
    "generator": "generatore", "compressor": "compressore",
    "concrete mixer": "betoniera", "mixer": "betoniera", "welder": "saldatrice",
}


def _generic_types() -> frozenset:
    from app.services.config_service import get_list
    return frozenset(get_list("generic_machine_types", _FB_GENERIC_TYPES - {None, ""})) | {None, ""}


def _accessory_signals() -> frozenset:
    from app.services.config_service import get_list
    return frozenset(get_list("accessory_signals", _FB_ACCESSORY_SIGNALS))


def _en_to_it_map() -> dict:
    from app.services.config_service import get_map
    return get_map("en_to_it_machine_type", _FB_EN_TO_IT)


def _normalize_machine_type(machine_type: str) -> str:
    """Normalizza tipi macchina inglesi → italiano INAIL."""
    if not machine_type:
        return machine_type
    mt = machine_type.lower().strip()
    return _en_to_it_map().get(mt, machine_type)


_VALIDATE_PROMPT = (
    "Guarda questa immagine. È una targa identificativa o etichetta di un macchinario/attrezzatura industriale "
    "(es: targa costruttore, targhetta dati, placca matricola di macchina da cantiere, industriale o agricola)?\n"
    "Rispondi SOLO con: SI oppure NO.\n"
    "Esempi SI: targa macchina con brand/modello/matricola, etichetta CE con dati tecnici, placca seriale.\n"
    "Esempi NO: selfie, paesaggio, documento cartaceo, schermo computer, ricevuta, cibo, auto privata, "
    "edificio, QR isolato senza contesto macchina, immagine vuota o irriconoscibile."
)


async def validate_plate_image(image_base64: str) -> bool:
    """
    Verifica rapidamente che l'immagine sia una targa/etichetta di macchinario.
    Richiesta leggera (max_tokens=5) — usata come guard prima dell'OCR completo.
    Ritorna True se valida, False se non è una targa macchina.
    """
    from app.services.llm_router import llm_router, LLMQuotaExceededError
    try:
        answer = await llm_router.generate_vision(image_base64, _VALIDATE_PROMPT, max_tokens=5)
        return answer.strip().upper().startswith("S")
    except LLMQuotaExceededError:
        logger.info("validate_plate_image: Groq esaurito — immagine accettata per default")
    except Exception as e:
        logger.warning("validate_plate_image: validazione AI fallita (%s) — immagine accettata per default", e)
    # Se la validazione fallisce o Groq è esaurito, lascia passare
    return True


async def extract_plate_info(image_base64: str) -> PlateOCRResult:
    from app.services.llm_router import llm_router, LLMQuotaExceededError
    try:
        raw = await llm_router.generate_vision(image_base64, PLATE_OCR_PROMPT, max_tokens=1024)
        result = _parse_ocr_json(raw.strip())
    except LLMQuotaExceededError:
        logger.info("extract_plate_info: Groq esaurito — fallback a Tesseract")
        result = await _extract_with_tesseract(image_base64)

    # Determina sempre il tipo di macchina da brand+modello tramite AI.
    # L'OCR raramente legge il tipo dalla targa (quasi mai è scritto), quindi
    # l'AI ha sempre più contesto dal codice modello che dalla targa stessa.
    # Il risultato OCR viene usato come hint ma l'AI ha l'ultima parola.
    if result.brand and result.model:
        ocr_hint = (result.machine_type or "").strip()
        # Passa il tipo OCR come hint — l'AI può confermarlo o correggerlo
        enriched, mt_id = await _infer_machine_type(result.brand, result.model, ocr_hint=ocr_hint or None)
        if enriched:
            result.machine_type = enriched
        # Registra l'ID canonico (None se tipo non nel catalogo — backward compat)
        result.machine_type_id = mt_id

    # Post-inferenza: rileva accessori/attrezzature per evitare analisi come macchina completa
    if result.machine_type:
        mt_lower = result.machine_type.lower()
        for sig in _accessory_signals():
            if sig in mt_lower:
                if not result.notes:
                    result.notes = (
                        f"Attrezzatura/accessorio rilevato ({result.machine_type}): "
                        "l'analisi potrebbe non trovare scheda INAIL specifica."
                    )
                break

    # Decodifica nativa QR/DataMatrix: integra con quanto già trovato dall'AI vision.
    # Viene eseguita sull'immagine originale (non preprocessata) per massimizzare la resa.
    # I decoder nativi leggono codici rovinati/angolati che il modello vision ignora.
    try:
        from app.services.image_service import decode_barcodes
        native_urls = decode_barcodes(image_base64)
        if native_urls:
            # Aggiungi solo URL non già presenti (confronto case-insensitive)
            existing_lower = {u.lower() for u in result.qr_urls}
            for url in native_urls:
                if url.lower() not in existing_lower:
                    result.qr_urls.append(url)
                    existing_lower.add(url.lower())
            # Aggiorna qr_url (primo elemento) per retrocompatibilità
            if result.qr_urls and not result.qr_url:
                result.qr_url = result.qr_urls[0]
    except Exception:
        pass  # Librerie non installate o errore — non blocca l'OCR

    return result


async def extract_plate_info_multishot(image_base64: str) -> PlateOCRResult:
    """
    Esegue 3 OCR in parallelo con preprocessing diversi e fa majority voting su brand+model.
    Usato quando il primo tentativo restituisce confidence='low'.
    """
    from app.services.image_service import preprocess_plate_image, preprocess_plate_image_variant
    variants = [
        preprocess_plate_image(image_base64),              # 0: standard
        preprocess_plate_image_variant(image_base64, 1),   # 1: alto contrasto B&W
        preprocess_plate_image_variant(image_base64, 2),   # 2: denoised morbido
        preprocess_plate_image_variant(image_base64, 3),   # 3: contrasto locale adattivo (CLAHE-like)
    ]
    results: list[PlateOCRResult] = await asyncio.gather(
        *[extract_plate_info(v) for v in variants],
        return_exceptions=True,
    )
    valid = [r for r in results if isinstance(r, PlateOCRResult)]
    if not valid:
        return await extract_plate_info(image_base64)

    # Majority voting su brand (case-insensitive)
    brand_counts: dict[str, int] = {}
    for r in valid:
        if r.brand:
            k = r.brand.lower().strip()
            brand_counts[k] = brand_counts.get(k, 0) + 1
    best_brand = max(brand_counts, key=brand_counts.get) if brand_counts else None

    # Tra i risultati con il brand vincente, scegli il più completo
    winners = (
        [r for r in valid if r.brand and r.brand.lower().strip() == best_brand]
        if best_brand else valid
    )
    best = max(winners, key=lambda r: sum([
        bool(r.brand), bool(r.model), bool(r.serial_number), bool(r.year),
        r.confidence == "high", r.confidence == "medium",
        len(r.raw_text or ""),
    ]))
    # Promuovi la confidence se almeno 2/4 concordano sul brand
    if best_brand and brand_counts.get(best_brand, 0) >= 2 and best.confidence == "low":
        best = best.model_copy(update={"confidence": "medium"})

    # Majority voting su model, year, serial_number:
    # se 2+ varianti concordano su un valore, sovrascrive quello del best_result
    def _majority_field(field: str):
        counts: dict[str, int] = {}
        for r in valid:
            v = (getattr(r, field, None) or "").strip()
            if v:
                counts[v.lower()] = counts.get(v.lower(), 0) + 1
        if not counts:
            return None
        top_key, top_count = max(counts.items(), key=lambda x: x[1])
        if top_count >= 2:
            for r in valid:
                v = (getattr(r, field, None) or "").strip()
                if v and v.lower() == top_key:
                    return v
        return None

    for field in ("model", "year", "serial_number"):
        majority_val = _majority_field(field)
        if majority_val:
            best = best.model_copy(update={field: majority_val})

    # Flag di incertezza: marca i campi su cui meno di 2/4 varianti concordano
    best = _add_uncertain_flags(best, valid)

    return best


def _add_uncertain_flags(result: PlateOCRResult, variants: list) -> PlateOCRResult:
    """
    Marca uncertain=True i campi con accordo < 2 varianti su 4.
    Campi controllati: serial_number, year, model.
    """
    updates: dict = {}
    for field in ("serial_number", "year", "model"):
        values = [(getattr(r, field) or "").strip().lower() for r in variants if getattr(r, field)]
        if not values:
            # Campo mai letto da nessuna variante — potenzialmente incerto
            continue
        from collections import Counter
        top_count = Counter(values).most_common(1)[0][1]
        if top_count < 2:
            updates[f"{field}_uncertain"] = True
    if updates:
        return result.model_copy(update=updates)
    return result


# _BRAND_TYPE_MAP e _MODEL_PREFIX_OVERRIDES sono ora in DB (brand_machine_type_hints).
# Seed iniziale in config_seeds.py. Usare config_service.get_brand_hints() via _lookup_brand_type().
_BRAND_TYPE_MAP: dict[str, str] = {  # mantenuto solo come documentazione / riferimento seed
    # ── Macchine per lavorazione legno ────────────────────────────────────────
    "polieri":      "sega circolare",
    "casadei":      "sega circolare",
    "scm":          "sega circolare",       # SCM Group — varie, ma prevalenza seghe
    "griggio":      "sega circolare",
    "felder":       "sega circolare",
    "altendorf":    "sega circolare",
    "robland":      "sega circolare",
    "maka":         "centro di lavoro CNC per legno",
    "biesse":       "centro di lavoro CNC per legno",
    "homag":        "centro di lavoro CNC per legno",
    "weinig":       "pialla quattro facce",
    "martin":       "sega circolare",       # Martin GmbH
    "oertli":       "fresatrice per legno",
    "steton":       "sega circolare",
    # ── Macchine per lavorazione lamiera / metallo ────────────────────────────
    "trumpf":       "macchina taglio laser",
    "bystronic":    "macchina taglio laser",
    "amada":        "pressa piegatrice",
    "salvagnini":   "pannellatrice",
    "prima industrie": "macchina taglio laser",
    "ermaksan":     "pressa piegatrice",
    "durmapress":   "pressa piegatrice",
    "safan":        "pressa piegatrice",
    "gasparini":    "pressa piegatrice",
    "ficep":        "punzonatrice",
    "euromac":      "punzonatrice",
    "rainer":       "pressa piegatrice",
    "promecam":     "pressa piegatrice",
    "haco":         "pressa piegatrice",
    "durma":        "pressa piegatrice",
    "accurpress":   "pressa piegatrice",
    # ── Accessori idraulici / attrezzature per escavatori ────────────────────
    "rozzi":        "attrezzatura idraulica per escavatore",
    "indeco":       "martello demolitore idraulico",
    "mb crusher":   "frantoio da escavatore",
    "mb":           "attrezzatura per escavatore",
    "epiroc":       "martello demolitore idraulico",
    "furukawa":     "martello demolitore idraulico",
    "atlas copco rock drills": "martello demolitore idraulico",
    "montabert":    "martello demolitore idraulico",
    "rammer":       "martello demolitore idraulico",
    "brokk":        "robot demolitore",
    "demoq":        "attrezzatura demolitiva",
    # ── Piattaforme aeree / sollevamento ──────────────────────────────────────
    "haulotte":     "piattaforma aerea",
    "genie":        "piattaforma aerea",
    "jlg":          "piattaforma aerea",
    "skyjack":      "piattaforma a forbice",
    "snorkel":      "piattaforma aerea",
    "niftylift":    "piattaforma aerea a braccio",
    "manitou":      "sollevatore telescopico",
    "merlo":        "sollevatore telescopico",
    "dieci":        "sollevatore telescopico",
    "jcb":          "sollevatore telescopico",  # JCB prevalenza — overridden by model prefix later
    "faresin":      "sollevatore telescopico",
    "magni":        "sollevatore telescopico rotante",
    "tadano":       "gru mobile",
    "liebherr ltm": "gru mobile",
    "fassi":        "gru su autocarro",
    "hiab":         "gru su autocarro",
    "palfinger":    "gru su autocarro",
    "effer":        "gru su autocarro",
    "pesci":        "gru su autocarro",
    "atlas":        "gru su autocarro",         # Atlas Maschinen (gru), non Atlas Copco
    # ── Movimento terra ───────────────────────────────────────────────────────
    "caterpillar":  "escavatore",               # default — raffinato da prefisso modello
    "komatsu":      "escavatore",
    "volvo ce":     "escavatore",
    "volvo":        "escavatore",
    "doosan":       "escavatore",
    "hitachi":      "escavatore",
    "hyundai":      "escavatore",
    "case":         "escavatore",
    "new holland":  "escavatore",
    "bobcat":       "minipala",
    "gehl":         "minipala gommata",
    "mustang":      "minipala",
    "takeuchi":     "minipala",
    "yanmar":       "minipala",
    "kubota":       "minipala",
    "terex":        "minipala",
    "thomas":       "minipala",
    "new holland construction": "minipala",
    "wacker neuson":"rullo compattatore",
    "bomag":        "rullo compattatore",
    "hamm":         "rullo compattatore",
    "dynapac":      "rullo compattatore",
    "ammann":       "rullo compattatore",
    "sakai":        "rullo compattatore",
    "wirtgen":      "fresatrice stradale",
    "vögele":       "finitrice",
    "vogele":       "finitrice",
    "bauer":        "trivella da fondazione",
    "soilmec":      "trivella da fondazione",
    # ── Carrelli elevatori ────────────────────────────────────────────────────
    "linde":        "carrello elevatore",
    "still":        "carrello elevatore",
    "jungheinrich": "carrello elevatore",
    "toyota":       "carrello elevatore",
    "hyster":       "carrello elevatore",
    "yale":         "carrello elevatore",
    "crown":        "carrello elevatore",
    "nissan":       "carrello elevatore",
    "mitsubishi":   "carrello elevatore",
    "clark":        "carrello elevatore",
    "om":           "carrello elevatore",       # OM Carrelli (brand italiano)
    "konecranes":   "carrello elevatore",       # SMV = reach stacker / heavy forklift
    "kalmar":       "carrello elevatore",       # reach stacker portuali
    "cvs ferrari":  "carrello elevatore",       # reach stacker italiani
    "cvs":          "carrello elevatore",
    "svetruck":     "carrello elevatore",       # carrelli pesanti svedesi
    "terberg":      "carrello elevatore",       # terminal tractors / heavy movers
    "combilift":    "carrello elevatore",       # carrelli multidirezionali
    "bendi":        "carrello elevatore",
    "aisle-master": "carrello elevatore",
    "doosan":       "carrello elevatore",       # override: Doosan produce anche carrelli (SMV)
    "hangcha":      "carrello elevatore",
    "heli":         "carrello elevatore",
    "ep equipment": "carrello elevatore",
    "unicarriers":  "carrello elevatore",
    "nichiyu":      "carrello elevatore",
    "rocla":        "carrello elevatore",
    # ── Pompe / calcestruzzo ──────────────────────────────────────────────────
    "schwing":      "pompa calcestruzzo",
    "putzmeister":  "pompa calcestruzzo",
    "cifa":         "pompa calcestruzzo",
    "sermac":       "pompa calcestruzzo",
    # ── Compressori / generatori ──────────────────────────────────────────────
    "atlas copco":  "compressore",
    "kaeser":       "compressore",
    "ceccato":      "compressore",
    "fini":         "compressore",
    "abac":         "compressore",
    "ingersoll rand": "compressore",
    "boge":         "compressore",
    "almig":        "compressore",
    "kohler":       "generatore",
    "sdmo":         "generatore",
    "pramac":       "generatore",
    "cummins":      "generatore",
    "perkins":      "generatore",
    # VAIA CAR: brand italiano di attrezzature/macchine speciali
    "vaia car":     "attrezzatura speciale",   # default — raffinato da prefisso modello
    "vaia":         "attrezzatura speciale",
    # Accessori idraulici per escavatori
    "idrobenne":    "benna idraulica",
    "mantovanibenne": "benna idraulica",
    "casagrande":   "trivella da fondazione",
}

# Ora in DB. Mantenuto solo come seed reference.
_MODEL_PREFIX_OVERRIDES: list[tuple[str, str, str]] = [
    # (brand_lower, model_prefix_lower, tipo)
    ("caterpillar", "320", "escavatore"),
    ("caterpillar", "323", "escavatore"),
    ("caterpillar", "330", "escavatore"),
    ("caterpillar", "336", "escavatore"),
    ("caterpillar", "345", "escavatore"),
    ("caterpillar", "950", "pala caricatrice"),
    ("caterpillar", "966", "pala caricatrice"),
    ("caterpillar", "972", "pala caricatrice"),
    ("caterpillar", "420", "terna"),
    ("caterpillar", "432", "terna"),
    ("caterpillar", "444", "terna"),
    ("caterpillar", "770", "dumper"),
    ("caterpillar", "773", "dumper"),
    ("komatsu", "pc",  "escavatore"),
    ("komatsu", "wa",  "pala caricatrice"),
    ("komatsu", "hd",  "dumper"),
    ("komatsu", "d",   "bulldozer"),
    ("jcb", "3cx",     "terna"),
    ("jcb", "4cx",     "terna"),
    ("jcb", "js",      "escavatore"),
    ("jcb", "535",     "sollevatore telescopico"),
    ("jcb", "541",     "sollevatore telescopico"),
    ("jcb", "550",     "sollevatore telescopico"),
    ("haulotte", "h",  "piattaforma a forbice"),
    ("haulotte", "ha", "piattaforma aerea a braccio"),
    ("haulotte", "ht", "piattaforma aerea a braccio"),
    ("genie", "gs",    "piattaforma a forbice"),
    ("genie", "z-",    "piattaforma aerea a braccio"),
    ("genie", "s-",    "piattaforma aerea a braccio"),
    ("jlg", "2646",    "piattaforma a forbice"),
    ("jlg", "3246",    "piattaforma a forbice"),
    ("jlg", "4069",    "piattaforma a forbice"),
    ("jlg", "600aj",   "piattaforma aerea a braccio"),
    ("jlg", "800aj",   "piattaforma aerea a braccio"),
    ("volvo", "ew",    "escavatore"),
    ("volvo", "ec",    "escavatore"),
    ("volvo", "l",     "pala caricatrice"),
    ("volvo", "a",     "dumper articolato"),
    ("liebherr", "ltm","gru mobile"),
    ("liebherr", "ltc","gru mobile"),
    ("liebherr", "ltr","gru cingolata"),
    ("liebherr", "ec", "gru a torre"),
    ("liebherr", "l",  "pala caricatrice"),
    ("liebherr", "r",  "escavatore"),
    ("rozzi", "rr",       "benna a polipo"),
    ("rozzi", "rb",       "benna a mordacchia"),
    ("rozzi", "rc",       "cesoia demolitrice"),
    ("rozzi", "rm",       "martello demolitore"),
    # VAIA CAR: bco = benna carico-scarico, kube = testa saldante, si = saldatrice inverter
    ("vaia car", "bco",   "benna carico-pietrisco"),
    ("vaia car", "kube",  "testa saldante"),
    ("vaia car", "si",    "saldatrice inverter"),
    ("vaia", "bco",       "benna carico-pietrisco"),
    ("vaia", "kube",      "testa saldante"),
    ("vaia", "si",        "saldatrice inverter"),
    # Konecranes: SMV = carrello portacontainer (reach stacker)
    ("konecranes", "smv", "carrello portacontainer"),
    ("konecranes", "eco", "carrello elevatore"),
    ("konecranes", "smc", "carrello elevatore"),
    # Kalmar: carrello portacontainer (reach stacker) / straddle carrier
    ("kalmar", "drf",     "carrello portacontainer"),
    ("kalmar", "dck",     "carrello portacontainer"),
    ("kalmar", "dcf",     "carrello elevatore"),
    # Doosan (carrelli): serie B/G/D = carrelli elevatori, non escavatori
    ("doosan", "b",       "carrello elevatore"),
    ("doosan", "g",       "carrello elevatore"),
    ("doosan", "d",       "carrello elevatore"),
    # Doosan (escavatori): serie DX / DL
    ("doosan", "dx",      "escavatore"),
    ("doosan", "dl",      "pala caricatrice"),
    # Case: serie CX = escavatori, WX = escavatori gomm., 580/590 = terna
    ("case", "cx",        "escavatore"),
    ("case", "wx",        "escavatore"),
    ("case", "580",       "terna"),
    ("case", "590",       "terna"),
    ("case", "621",       "pala caricatrice"),
    ("case", "721",       "pala caricatrice"),
]


def _lookup_brand_type(brand: str, model: str) -> Optional[str]:
    """
    Lookup deterministico da DB brand_machine_type_hints.
    Prima controlla prefissi modello specifici, poi fallback sul brand.
    Restituisce None se brand sconosciuto.
    """
    from app.services.config_service import get_brand_hints
    brand_l = brand.strip().lower()
    model_l = model.strip().lower()

    hints = get_brand_hints()

    # 1) Sovrascritture per prefisso modello (model_prefix valorizzato)
    for h in hints:
        mp = h.get("model_prefix")
        if mp and h["brand"] == brand_l and model_l.startswith(mp):
            return h["machine_type_text"]

    # 2) Fallback brand esatto (model_prefix NULL)
    for h in hints:
        if h.get("model_prefix") is None and h["brand"] == brand_l:
            return h["machine_type_text"]

    # 3) Fallback brand parziale (gestisce "Volvo CE" vs "Volvo")
    for h in hints:
        if h.get("model_prefix") is None:
            key = h["brand"]
            if len(key) >= 4 and (key in brand_l or brand_l in key):
                return h["machine_type_text"]

    return None


async def _infer_machine_type(
    brand: str, model: str, ocr_hint: Optional[str] = None
) -> tuple[Optional[str], Optional[int]]:
    """
    Determina il tipo di macchina da brand+modello.
    Ritorna (machine_type_str, machine_type_id) — id può essere None (backward compat).

    Pipeline:
    1. Lookup deterministico su _BRAND_TYPE_MAP (istantaneo, 100% affidabile per brand noti)
    2. DB matching su ocr_hint via machine_type_service (rapidfuzz + LLM candidati)
    3. AI inference con prompt mirato, poi match DB sul testo restituito
    """
    from app.services.machine_type_service import match_ocr_text, get_name_by_id

    # Step 1: lookup deterministico — nessuna chiamata AI
    lookup = _lookup_brand_type(brand, model)
    if lookup:
        # Prova a trovare l'ID nel catalogo
        mt_id, score, _ = match_ocr_text(lookup)
        return (lookup, mt_id if score >= 0.82 else None)

    # Step 2: DB matching diretto su ocr_hint (se disponibile e affidabile)
    if ocr_hint and ocr_hint not in _generic_types():
        mt_id, score, method = match_ocr_text(ocr_hint)
        if mt_id and score >= 0.82:
            name = get_name_by_id(mt_id)
            return (name or ocr_hint, mt_id)

    # Step 3: brand sconosciuto — chiedi all'AI con istruzioni precise
    hint_line = f"Nota: l'OCR ha letto dalla targa '{ocr_hint}' come tipo — verifica se è corretto.\n" if ocr_hint else ""
    prompt = (
        f"Rispondi con UNA SOLA RIGA di testo, senza spiegazioni.\n"
        f"Qual è il tipo esatto di macchinario industriale '{brand} {model}'?\n"
        f"{hint_line}"
        f"REGOLE CRITICHE:\n"
        f"- Usa SOLO la tua conoscenza certa del brand e del modello specifico\n"
        f"- NON indovinare: se non conosci questo brand/modello con certezza, scrivi null\n"
        f"- Se il brand è sconosciuto o poco noto nel settore macchine da cantiere/industriali, scrivi null\n"
        f"- NON confondere accessori/attrezzature con macchine autonome. Esempi di ACCESSORI (NON macchine):\n"
        f"  benne, martelli idraulici, pinze, polpi, forche, teste girevoli, rotatori idraulici,\n"
        f"  attrezzi intercambiabili, testine di scavo, scarificatori, compattatori vibranti da escavatore,\n"
        f"  forche da magazzino, bilancini di sollevamento, ganci, benne a polipo, pale benna,\n"
        f"  teste idrauliche, girapali, gru a bandiera fisse, paranco manuale\n"
        f"  Se il modello o il nome suggerisce un attrezzo/accessorio: scrivi il tipo di accessorio\n"
        f"  (es. 'testa idraulica girevole' → 'testa idraulica girevole'; 'rotatore' → 'rotatore idraulico')\n"
        f"  NON classificarlo come la macchina su cui viene montato (es. NON 'piattaforma aerea').\n"
        f"- Se il modello suggerisce un accessorio (BCO=benna, KUBE=testa, RR=polipo) scrivi il tipo di accessorio\n"
        f"- NON classificare macchine tessili, alimentari, farmaceutiche come macchine da cantiere\n"
        f"  Se il brand fa macchine per altri settori industriali, scrivi il settore corretto o null\n"
        f"- Scrivi in italiano, termine INAIL se esiste\n"
        f"Esempi validi: 'escavatore idraulico', 'pala caricatrice', 'carrello elevatore', "
        f"'sollevatore telescopico', 'piattaforma a forbice', 'piattaforma aerea a braccio', "
        f"'gru mobile', 'gru a torre', 'rullo compattatore', 'compressore', 'generatore', "
        f"'pompa calcestruzzo', 'finitrice', 'dumper', 'betoniera', 'terna', 'bulldozer', "
        f"'sega circolare', 'sega a nastro', 'pialla', 'fresatrice CNC', 'tornio', "
        f"'pressa piegatrice', 'punzonatrice', 'laser taglio', 'martello demolitore idraulico', "
        f"'benna a polipo', 'benna carico-pietrisco', 'testa saldante', 'attrezzatura idraulica per escavatore'.\n"
        f"Se non sei sicuro o il brand è sconosciuto: null"
    )
    answer = None
    try:
        from app.services.llm_router import llm_router
        answer = (await llm_router.generate_text("machine_type", prompt, max_tokens=50, fast=True)).strip().lower()
    except Exception:
        return (None, None)

    if not answer or answer in ("null", "non so", "sconosciuto", "unknown", ""):
        return (None, None)

    # Normalizza EN→IT, poi cerca nel catalogo DB
    normalized = _normalize_machine_type(answer.strip('"\'.,').strip())
    mt_id, score, _ = match_ocr_text(normalized)
    if mt_id and score >= 0.65:
        name = get_name_by_id(mt_id) or normalized
        return (name, mt_id)
    # Tipo non nel catalogo — backward compat: testo libero senza ID
    return (normalized, None)



async def _extract_with_tesseract(image_base64: str) -> PlateOCRResult:
    import base64, io
    import pytesseract
    from PIL import Image

    image_bytes = base64.b64decode(image_base64)
    img = Image.open(io.BytesIO(image_bytes))

    # Tentativo 1: PSM 6 (blocco testo uniforme) con whitelist caratteri targa
    config_psm6 = "--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-./: "
    raw_text = pytesseract.image_to_string(img, lang="ita+eng", config=config_psm6)

    # Tentativo 2: PSM 3 (fully automatic) se PSM 6 produce troppo poco
    if len(raw_text.strip()) < 20:
        raw_text = pytesseract.image_to_string(img, lang="ita+eng", config="--psm 3")

    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    full_text = " ".join(lines)

    # Pattern comuni per targhe industriali
    # Anno: 4 cifre, tipicamente 1990-2029
    year_match = re.search(r'\b(19[89]\d|20[0-2]\d)\b', full_text)
    year = year_match.group(1) if year_match else None

    # Serial number: pattern alfanumerico lungo (es: MATR, S/N, SER, N°)
    serial_match = re.search(r'(?:MATR|S[/\\]?N|SER|N[°\.]|SERIAL|MATRICOLA)[:\s]*([A-Z0-9\-]{4,20})', full_text, re.IGNORECASE)
    serial_number = serial_match.group(1) if serial_match else None

    # Modello: pattern comune dopo "MODEL", "TYPE", "MOD"
    model_match = re.search(r'(?:MODEL|TYPE|MOD|MODELLO)[:\s]*([A-Z0-9][A-Z0-9\s\-]{2,30})', full_text, re.IGNORECASE)
    model = model_match.group(1).strip() if model_match else None

    # Brand: pattern comune dopo "MAKE", "MANUFACTURER", "PRODUTTORE"
    brand_match = re.search(r'(?:MAKE|MANUFACTURER|PRODUTTORE|COSTRUTTORE|MARCA)[:\s]*([A-Z][A-Z\s]{2,30})', full_text, re.IGNORECASE)
    brand = brand_match.group(1).strip() if brand_match else None

    # Fallback: se non troviamo brand/model con pattern, usa prime righe
    if not brand and len(lines) > 0:
        brand = lines[0][:30]
    if not model and len(lines) > 1:
        model = lines[1][:30]

    notes_parts = []
    if not brand:
        notes_parts.append("Brand non identificato automaticamente")
    if not model:
        notes_parts.append("Modello non identificato automaticamente")
    notes_parts.append("Estratto con Tesseract OCR — qualità ridotta. Verificare manualmente.")

    return PlateOCRResult(
        brand=brand,
        model=model,
        serial_number=serial_number,
        year=year,
        raw_text=raw_text,
        confidence="low",
        notes=". ".join(notes_parts),
    )


def _qr_fields(data: dict) -> dict:
    """Ritorna {'qr_urls': [...], 'qr_url': first_or_None} per PlateOCRResult."""
    urls = _parse_qr_urls(data)
    return {"qr_urls": urls, "qr_url": urls[0] if urls else None}


def _parse_qr_urls(data: dict) -> list[str]:
    """
    Estrae la lista di URL QR Code da un dict OCR.
    Supporta sia il nuovo campo 'qr_urls' (list) che il vecchio 'qr_url' (str) per retrocompatibilità.
    Filtra URL null/vuoti.
    """
    urls: list[str] = []
    raw = data.get("qr_urls")
    if isinstance(raw, list):
        urls = [u for u in raw if isinstance(u, str) and u.strip()]
    if not urls:
        legacy = data.get("qr_url")
        if isinstance(legacy, str) and legacy.strip():
            urls = [legacy.strip()]
    return urls


def _try_extract_json_field(text: str, field: str) -> Optional[str]:
    """
    Estrae un singolo campo stringa da JSON malformato via regex.
    Usato come fallback quando json.loads fallisce.
    Ritorna None se il campo non è trovato o non è una stringa semplice.
    """
    m = re.search(
        rf'"{re.escape(field)}"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"',
        text,
        re.DOTALL,
    )
    if m:
        try:
            # Usa json.loads sul frammento per gestire correttamente le escape sequences
            return json.loads(f'"{m.group(1)}"')
        except json.JSONDecodeError:
            return m.group(1)
    return None


def _parse_ocr_json(text: str) -> PlateOCRResult:
    cleaned = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
    try:
        data = json.loads(cleaned.strip())
        # Estrai norme armonizzate dal campo dedicato o con regex dal raw_text come fallback
        norme = data.get("norme") or []
        if not norme:
            raw = data.get("raw_text", "")
            norme = re.findall(r'\b(?:prEN\s+|EN\s+|UNI\s+EN\s+|UNI\s+|ISO\s+|IEC\s+)\d[\d\-\.:]*', raw, re.IGNORECASE)
            norme = [n.strip() for n in norme]

        return PlateOCRResult(
            brand=data.get("brand"),
            model=data.get("model"),
            machine_type=data.get("machine_type"),
            serial_number=data.get("serial_number"),
            year=data.get("year"),
            norme=norme,
            **_qr_fields(data),
            confidence=data.get("confidence", "low"),
            raw_text=data.get("raw_text", ""),
            notes=data.get("notes"),
            ce_marking=data.get("ce_marking"),
            machine_category=data.get("machine_category"),
        )
    except json.JSONDecodeError:
        # Recupero field-level: il modello restituisce spesso JSON quasi-valido
        # (virgole finali, caratteri speciali) — recuperiamo i campi più importanti.
        recovered_raw = _try_extract_json_field(text, "raw_text") or text

        brand        = _try_extract_json_field(text, "brand")
        model        = _try_extract_json_field(text, "model")
        year         = _try_extract_json_field(text, "year")
        machine_type = _try_extract_json_field(text, "machine_type")
        confidence   = _try_extract_json_field(text, "confidence") or "low"
        ce_marking   = _try_extract_json_field(text, "ce_marking")

        # Fallback regex se il campo non era nel JSON nemmeno parzialmente
        if not year:
            m = re.search(r'\b(19[89]\d|20[0-2]\d)\b', recovered_raw)
            year = m.group(1) if m else None
        if not brand:
            m = re.search(
                r'(?:MAKE|MANUFACTURER|PRODUTTORE|COSTRUTTORE|MARCA)[:\s]*([A-Z][A-Za-z\s]{2,30})',
                recovered_raw, re.IGNORECASE
            )
            brand = m.group(1).strip() if m else None
        if not model:
            m = re.search(
                r'(?:MODEL|TYPE|MOD|MODELLO)[:\s]*([A-Z0-9][A-Z0-9\s\-]{2,30})',
                recovered_raw, re.IGNORECASE
            )
            model = m.group(1).strip() if m else None

        # Norme armonizzate dal testo grezzo
        norme = re.findall(
            r'\b(?:prEN\s+|EN\s+|UNI\s+EN\s+|UNI\s+|ISO\s+|IEC\s+)\d[\d\-\.:]*',
            recovered_raw, re.IGNORECASE
        )

        return PlateOCRResult(
            brand=brand,
            model=model,
            machine_type=machine_type,
            year=year,
            norme=[n.strip() for n in norme],
            raw_text=recovered_raw,
            confidence=confidence if confidence in ("high", "medium", "low") else "low",
            ce_marking=ce_marking,
            notes="Risposta OCR parzialmente recuperata (JSON malformato). Verificare i dati estratti.",
        )
