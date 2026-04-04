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
- Per "machine_type": identifica il TIPO di macchina e scrivi SEMPRE in italiano, anche se sulla targa appare un termine inglese. Esempi di traduzione obbligatoria:
  - "DUMPER" → "dumper" (termine accettato in italiano) oppure "autocarro ribaltabile"
  - "EXCAVATOR" → "escavatore"
  - "CRANE" → "gru"
  - "PLATFORM" / "AERIAL WORK PLATFORM" / "AWP" → "piattaforma aerea"
  - "FORKLIFT" → "carrello elevatore"
  - "TELESCOPIC HANDLER" / "TELEHANDLER" → "sollevatore telescopico"
  - "LOADER" / "WHEEL LOADER" → "pala caricatrice"
  - "ROLLER" / "COMPACTOR" → "rullo compattatore"
  - "GENERATOR" / "GENSET" → "generatore"
  - "COMPRESSOR" → "compressore"
  - "CONCRETE PUMP" → "pompa calcestruzzo"
  - "DRILL" / "DRILL RIG" → "perforatrice"
  - "PAVER" / "FINISHER" → "finitrice"
  - "PRESS BRAKE" / "BENDING MACHINE" → "pressa piegatrice"
  - "CRANE TRUCK" / "TRUCK MOUNTED CRANE" → "camion gru"
  - "SCISSOR LIFT" → "piattaforma a forbice"
  - NON lasciare MAI termini in inglese nel campo machine_type
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


async def extract_plate_info(image_base64: str) -> PlateOCRResult:
    provider = settings.get_vision_provider()

    if provider == "anthropic":
        return await _extract_with_claude(image_base64)
    elif provider == "gemini":
        return await _extract_with_gemini(image_base64)
    else:
        return await _extract_with_tesseract(image_base64)


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
