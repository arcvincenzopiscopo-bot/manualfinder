"""
OCR targa identificativa tramite Claude Vision (Livello 1) o Gemini Vision (Livello 2).
Estrae: brand, modello, numero di serie, anno di fabbricazione.
"""
import json
import re
from typing import Optional
from app.config import settings
from app.models.responses import PlateOCRResult

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
  "qr_url": "URL decodificato dal QR Code se presente nella foto, altrimenti null",
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
- Per "qr_url": se nell'immagine è presente un QR Code, tentane la decodifica anche se parzialmente visibile (almeno 3 angoli leggibili). Se riesci, riporta l'URL completo. Se il QR è presente ma illeggibile, scrivi null e aggiungi "QR Code presente ma illeggibile" nelle notes. Spesso rimanda direttamente al manuale digitale del produttore.
- confidence "high": testo chiaramente leggibile senza dubbi
- confidence "medium": leggibile ma con qualche incertezza su alcuni caratteri o valori
- confidence "low": molto difficile da leggere, probabili errori di interpretazione
- Se la targa è plurilingue (es. "ANNO / YEAR / BAUJAHR: 2015"), estrai il valore UNA SOLA VOLTA senza ripetere per ogni lingua
- La targa può essere ossidata, sporca o con illuminazione scarsa: fai del tuo meglio

Rispondi SOLO con il JSON valido, senza markdown, senza testo aggiuntivo."""

GEMINI_MODEL = "gemini-2.5-flash"


_GENERIC_TYPES = {None, "", "macchinario", "macchina", "attrezzatura", "equipment", "machine"}

async def extract_plate_info(image_base64: str) -> PlateOCRResult:
    provider = settings.get_vision_provider()

    if provider == "anthropic":
        result = await _extract_with_claude(image_base64)
    elif provider == "gemini":
        result = await _extract_with_gemini(image_base64)
    else:
        result = await _extract_with_tesseract(image_base64)

    # Determina sempre il tipo di macchina da brand+modello tramite AI.
    # L'OCR raramente legge il tipo dalla targa (quasi mai è scritto), quindi
    # l'AI ha sempre più contesto dal codice modello che dalla targa stessa.
    # Il risultato OCR viene usato come hint ma l'AI ha l'ultima parola.
    if result.brand and result.model:
        ocr_hint = (result.machine_type or "").strip()
        # Passa il tipo OCR come hint — l'AI può confermarlo o correggerlo
        enriched = await _infer_machine_type(result.brand, result.model, provider, ocr_hint=ocr_hint or None)
        if enriched:
            result.machine_type = enriched

    return result


async def _infer_machine_type(brand: str, model: str, provider: str, ocr_hint: Optional[str] = None) -> Optional[str]:
    """
    Determina il tipo di macchina da brand+modello tramite AI.
    Chiamata sempre dopo l'OCR: l'AI conosce i modelli industriali meglio
    di quanto l'OCR possa leggere dalla targa (il tipo raramente è scritto).
    ocr_hint: tipo estratto dall'OCR, usato come contesto (può essere None).
    """
    hint_line = f"L'OCR ha letto dalla targa il tipo: '{ocr_hint}' — verifica se è corretto o correggilo.\n" if ocr_hint else ""
    prompt = (
        f"Rispondi con UNA SOLA RIGA di testo, senza spiegazioni.\n"
        f"Qual è il tipo di macchinario industriale '{brand} {model}'?\n"
        f"{hint_line}"
        f"Usa il brand come indizio forte per la categoria:\n"
        f"- Polieri, Casadei, SCM, Griggio, Felder, Altendorf → macchine per la lavorazione del legno\n"
        f"- Trumpf, Amada, Bystronic, Prima Industrie, Salvagnini → macchine per la lavorazione della lamiera\n"
        f"- Manitou, JLG, Haulotte, Genie, Skyjack, Merlo → macchine di sollevamento\n"
        f"- Caterpillar, Komatsu, Volvo CE, JCB, Liebherr → macchine movimento terra\n"
        f"Esempi cantiere/sollevamento: 'escavatore idraulico', 'piattaforma a forbice', "
        f"'carrello elevatore', 'carrello elevatore telescopico', 'gru mobile', "
        f"'sollevatore telescopico', 'compressore', 'pala caricatrice frontale', "
        f"'dumper', 'rullo compattatore', 'finitrice', 'pompa calcestruzzo', 'betoniera'.\n"
        f"Esempi macchine utensili: 'sega circolare', 'sega a nastro', 'sega a disco', "
        f"'pialla', 'fresatrice CNC', 'tornio', 'pressa piegatrice', 'punzonatrice', "
        f"'laser taglio', 'saldatrice', 'cesoie', 'troncatrice'.\n"
        f"Usa il termine italiano standard INAIL se esiste.\n"
        f"Se non lo conosci con certezza scrivi solo: null"
    )
    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            resp = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=30,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            answer = resp.content[0].text.strip().lower()
        elif provider == "gemini":
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=settings.gemini_api_key)
            resp = await client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=30,
                    temperature=0.0,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            answer = resp.text.strip().lower()
        else:
            return None

        if answer in ("null", "non so", "sconosciuto", "unknown", ""):
            return None
        # Rimuovi eventuali virgolette o punteggiatura residua
        return answer.strip('"\'.,').strip()
    except Exception:
        return None


async def _extract_with_claude(image_base64: str) -> PlateOCRResult:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_base64,
                    },
                },
                {"type": "text", "text": PLATE_OCR_PROMPT},
            ],
        }],
    )
    return _parse_ocr_json(response.content[0].text.strip())


async def _extract_with_gemini(image_base64: str) -> PlateOCRResult:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)

    response = await client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(
                data=__import__('base64').b64decode(image_base64),
                mime_type="image/jpeg",
            ),
            PLATE_OCR_PROMPT,
        ],
    )
    return _parse_ocr_json(response.text.strip())


async def _extract_with_tesseract(image_base64: str) -> PlateOCRResult:
    import base64, io
    import pytesseract
    from PIL import Image

    image_bytes = base64.b64decode(image_base64)
    img = Image.open(io.BytesIO(image_bytes))
    raw_text = pytesseract.image_to_string(img, lang="ita+eng")

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
            qr_url=data.get("qr_url"),
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
