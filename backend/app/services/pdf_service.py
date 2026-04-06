"""
Download e processamento dei manuali PDF.
Gestisce: download streaming, controllo dimensioni, estrazione testo, chunking.
"""
import io
import base64
from typing import Optional, Tuple
from app.config import settings

# Keywords per identificare pagine di sicurezza rilevanti
SAFETY_KEYWORDS = [
    "rischio", "pericolo", "sicurezza", "protezione", "dpi", "avvertenza",
    "avviso", "attenzione", "warning", "danger", "risk", "safety", "hazard",
    "proteggere", "indossare", "vietato", "proibito", "dispositivo",
    "guanti", "elmetto", "casco", "occhiali", "stivali", "imbracatura",
]


async def download_pdf(url: str) -> Tuple[Optional[bytes], str]:
    """
    Scarica un PDF dall'URL fornito o legge un file locale.
    Restituisce (bytes, error_message). Se errore, bytes è None.
    """
    import httpx

    max_bytes = settings.max_pdf_size_mb * 1024 * 1024

    # Gestisci URL locali (file system) — sia INAIL che manuali caricati dagli ispettori
    if url.startswith("/manuals/local/") or url.startswith("/manuals/uploaded/"):
        try:
            if url.startswith("/manuals/local/"):
                from app.services import local_manuals_service
                filename = url.split("/")[-1]
                filepath = local_manuals_service.PDF_MANUALS_DIR / filename
            else:
                from app.services import upload_service
                filename = url.split("/")[-1]
                filepath = upload_service.UPLOAD_DIR / filename

            if not filepath.exists():
                return None, f"File locale non trovato: {filename}"

            pdf_bytes = filepath.read_bytes()
            if len(pdf_bytes) > max_bytes:
                return None, f"PDF troppo grande (> {settings.max_pdf_size_mb}MB)"

            if not pdf_bytes.startswith(b"%PDF"):
                return None, "Il file locale non è un PDF valido"

            return pdf_bytes, ""
        except Exception as e:
            return None, f"Errore lettura file locale: {str(e)}"

    try:
        async with httpx.AsyncClient(
            timeout=60,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ManualFinder/1.0)"},
        ) as client:
            async with client.stream("GET", url) as response:
                if response.status_code != 200:
                    return None, f"HTTP {response.status_code}"

                content_type = response.headers.get("content-type", "")
                if "pdf" not in content_type and not url.lower().endswith(".pdf"):
                    # Potrebbe essere comunque un PDF, proviamo
                    pass

                chunks = []
                total = 0
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    total += len(chunk)
                    if total > max_bytes:
                        return None, f"PDF troppo grande (> {settings.max_pdf_size_mb}MB)"
                    chunks.append(chunk)

                pdf_bytes = b"".join(chunks)

                # Verifica firma PDF
                if not pdf_bytes.startswith(b"%PDF"):
                    return None, "Il file scaricato non è un PDF valido"

                return pdf_bytes, ""

    except httpx.TimeoutException:
        return None, "Timeout durante il download del PDF"
    except Exception as e:
        return None, f"Errore download: {str(e)}"


def score_pdf_safety_relevance(
    pdf_bytes: bytes,
    max_pages: int = 80,
    brand: str = "",
    model: str = "",
    machine_type: str = "",
) -> int:
    """
    Assegna un punteggio di pertinenza sicurezza al PDF (0–100).
    Confronta più candidati: vince quello con più contenuto su salute e sicurezza.
    Penalizza documenti tecnici non-sicurezza (cataloghi ricambi, manuali officina).
    Se brand/model forniti, verifica che il PDF parli della macchina giusta.
    """
    # ── Struttura obbligatoria di un manuale macchina CE ─────────────────────
    # Termini che compaiono quasi ESCLUSIVAMENTE in libretti d'uso di macchinari.
    # Fonte: Direttiva Macchine 2006/42/CE Allegato I §1.7.4, EN ISO 12100.
    MANUAL_STRUCTURE_KW = [
        # ── Titolo e identificazione (IT) ──────────────────────────────────
        "libretto d'uso", "libretto di uso", "libretto istruzioni",
        "manuale d'uso e manutenzione", "manuale operatore",
        "istruzioni per l'operatore", "istruzioni per l'uso",
        "manuale di istruzioni", "istruzioni originali",
        "traduzione delle istruzioni originali",   # frase CE obbligatoria
        # ── Frasi obbligatorie CE (IT) — compaiono in ogni manuale conforme ─
        "leggere attentamente le istruzioni prima dell'uso",
        "prima di utilizzare",                     # da manuale reale E17Z
        "leggere attentamente i segnali di sicurezza",
        "conservare questo manuale", "conservare il manuale",
        "questo manuale è parte integrante della macchina",
        "il costruttore declina ogni responsabilità",
        "uso non conforme", "uso improprio",
        "dichiarazione di conformità ce", "dichiarazione ce di conformità",
        "dichiarazione di incorporazione",
        # ── Identificazione macchina (IT) ──────────────────────────────────
        "numero di serie", "n. di serie", "n° di serie",
        "posizioni dei numeri di serie",           # da manuale reale E17Z
        "matricola macchina", "anno di fabbricazione", "anno di costruzione",
        "proprietario/operatore",                  # da manuale reale E17Z
        # ── Capitoli standard (IT) — da struttura reale manuale E17Z ──────
        "risorse per la sicurezza e la formazione",  # da manuale reale E17Z
        "avvertenza per la sicurezza dell'operatore",  # da manuale reale E17Z
        "istruzioni per l'uso",                    # capitolo standard
        "manutenzione preventiva",                 # da manuale reale E17Z
        "dati tecnici", "specifiche tecniche", "caratteristiche tecniche della macchina",
        "messa in servizio", "messa fuori servizio", "dismissione",
        "manutenzione programmata", "piano di manutenzione",
        "fluidi, lubrificanti e carburante",       # da manuale reale E17Z
        "lubrificazione",
        "ricerca guasti", "ricerca dei guasti", "anomalie e rimedi",
        "impianto idraulico", "circuito idraulico", "sistema idraulico",
        "impianto elettrico", "schema elettrico di bordo",
        # ── Callout obbligatori (compaiono in OGNI manuale macchina) ──────
        "pericolo!", "avvertenza!", "avvertimento!", "nota importante",
        "non utilizzare la macchina", "spegnere il motore prima",
        "indossare i dispositivi di protezione individuale",
        # ── Inglese ───────────────────────────────────────────────────────
        "operator's manual", "operator manual", "instruction manual",
        "original instructions", "read this manual before",
        "keep this manual", "keep this manual with the machine",
        "declaration of conformity", "declaration of incorporation",
        "serial number", "year of manufacture", "model number",
        "technical data", "technical specifications",
        "putting into service", "taking out of service", "scheduled maintenance",
        "fault finding", "troubleshooting", "maintenance schedule",
        "hydraulic system", "hydraulic circuit", "electrical system",
        "danger!", "warning!", "caution!", "notice!",
        "do not operate", "shut down the engine before",
        "wear personal protective equipment",
        # ── Tedesco ───────────────────────────────────────────────────────
        "betriebsanleitung", "bedienungsanleitung", "originalbetriebsanleitung",
        "vor inbetriebnahme lesen", "anleitung aufbewahren",
        "konformitätserklärung", "einbauerklärung",
        "seriennummer", "baujahr", "technische daten",
        "hydraulikanlage", "elektrische anlage",
        "gefahr!", "warnung!", "achtung!", "hinweis!",
        # ── Francese ──────────────────────────────────────────────────────
        "notice d'utilisation", "manuel d'utilisation", "instructions originales",
        "lire attentivement avant utilisation", "conserver cette notice",
        "déclaration de conformité", "déclaration d'incorporation",
        "numéro de série", "année de fabrication", "données techniques",
        "système hydraulique", "installation électrique",
        "danger!", "avertissement!", "attention!", "remarque!",
    ]

    # Keyword ad alto peso: indicano sezioni dedicate alla sicurezza
    HIGH_WEIGHT_KW = [
        # Italiano INAIL/D.Lgs.81
        "dispositivi di sicurezza", "rischi per la sicurezza", "norme di sicurezza",
        "istruzioni di sicurezza", "avvertenze di sicurezza", "misure di sicurezza",
        "rischi residui", "dispositivi di protezione individuale",
        "verifiche periodiche", "verifiche di sicurezza", "check list",
        "abilitazione operatore", "formazione operatore",
        "d.lgs. 81", "d.lgs.81", "dlgs 81", "testo unico sicurezza",
        "direttiva macchine", "marcatura ce", "dichiarazione di conformit",
        "libretto di istruzione", "manuale di uso e manutenzione",
        # Inglese
        "safety instructions", "safety warnings", "safety precautions",
        "residual risks", "personal protective equipment",
        "declaration of conformity", "machinery directive",
        "operator qualification", "safety check",
        # Tedesco/Francese (comuni nei manuali europei)
        "sicherheitshinweise", "restrisiken", "schutzausrüstung",
        "consignes de sécurité", "équipements de protection",
    ]

    # Keyword a peso normale (vocabolario sicurezza generico)
    NORMAL_KW = SAFETY_KEYWORDS + [
        "ribaltamento", "investimento", "schiacciamento", "caduta",
        "folgorazione", "esplosione", "incendio", "ustione",
        "rumore", "vibrazione", "polvere", "gas", "vapore",
        "casco", "guanti", "occhiali", "stivali", "imbracatura", "elmetto",
        "estintore", "segnaletica", "evacuazione", "pronto soccorso",
        "overturning", "crushing", "falling", "electrocution",
        "helmet", "gloves", "goggles", "harness", "boots",
    ]

    # Keyword specifiche per lavorazione metalli / macchine utensili
    HIGH_WEIGHT_KW = HIGH_WEIGHT_KW + [
        "pressa piegatrice", "piegatrice idraulica", "punzonatrice",
        "riparo frontale", "riparo posteriore", "protezione punzone",
        "schiacciamento dita", "trappola delle mani", "zona di piegatura",
        "corsa del pistone", "velocità di avvicinamento", "velocità di lavoro",
        "pedana di comando", "pedale bivalente", "sistema laser di sicurezza",
        "EN 12622", "EN 13736",  # norme armonizzate presse piegatrici / punzonatrici
    ]
    NORMAL_KW = NORMAL_KW + [
        "pressa", "punzone", "matrice", "piega", "piegatura", "punzonatura",
        "lamiera", "staffa", "operatore pressa", "zona pericolosa pressa",
        "apertura stampo", "chiusura stampo",
    ]

    # Segnali negativi: indicano documenti NON-sicurezza
    NEGATIVE_SIGNALS = [
        "spare parts", "parts catalog", "catalogo ricambi", "part number",
        "ersatzteile", "listino prezzi", "price list",
        "workshop manual", "service manual", "repair manual",
        "manuale officina", "manuale riparazione",
        "schematic diagram", "wiring diagram", "schema elettrico",
        "torque specifications", "coppie di serraggio",
        # Cataloghi attrezzature/utensili (es. Amada tooling catalog)
        "tooling catalog", "tooling guide", "standard tooling",
        "punch and die", "punzone e matrice", "catalogo attrezzatura",
        "catalogo utensili", "utensili standard", "upper tool", "lower tool",
        "intermediate plate", "radius tooling", "hemming tool",
        # Cataloghi commerciali / listini prezzi
        "product catalogue", "product catalog", "catalogo prodotti",
        "ordering code", "order code", "codice ordine", "codice articolo",
    ]

    # Segnali dominio sbagliato — penalità massima: NON sono manuali macchine
    # Contenuto medico/sanitario
    WRONG_DOMAIN_SIGNALS = [
        "paziente", "pazienti", "terapia", "diagnosi", "reparto", "infermier",
        "medico", "chirurgi", "ospedale", "ambulatori", "pronto soccorso medic",
        "farmaco", "posologia", "dosaggio", "anestesia", "radiologi",
        "patient", "therapy", "diagnosis", "hospital", "clinical",
        "medical device", "dispositivo medico", "dispositivo medico attivo",
        # Contenuto accademico/scolastico
        "tesi di laurea", "università degli studi", "dottorato", "laureando",
        "facoltà di", "dipartimento di", "corso di laurea", "esame di stato",
        # Contenuto edilizio/strutturale non macchinari
        "capitolato speciale", "computo metrico", "prezziario regionale",
        "progetto esecutivo", "relazione tecnica generale",
        # Documenti legali/amministrativi
        "gazzetta ufficiale", "decreto legislativo n.", "delibera",
        "bando di gara", "avviso pubblico", "modulistica",
    ]

    # Segnali brochure commerciale — penalità forte
    BROCHURE_SIGNALS = [
        "brochure", "product sheet", "scheda prodotto", "scheda commerciale",
        "optional", "optionals disponibili", "accessori optional",
        "contattaci", "contact us", "richiedi offerta", "request a quote",
        "scopri di più", "learn more", "visita il sito", "visit our website",
        "caratteristiche tecniche principali",  # tipico delle brochure, non dei manuali
    ]

    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        pages_to_check = min(max_pages, total_pages)
        full_text = "".join(doc[i].get_text() for i in range(pages_to_check)).lower()
        doc.close()

        if not full_text.strip():
            return 0

        manual_hits = sum(1 for kw in MANUAL_STRUCTURE_KW if kw in full_text)
        high_hits = sum(1 for kw in HIGH_WEIGHT_KW if kw in full_text)
        normal_hits = sum(1 for kw in NORMAL_KW if kw in full_text)
        negative_hits = sum(1 for s in NEGATIVE_SIGNALS if s in full_text)
        brochure_hits = sum(1 for s in BROCHURE_SIGNALS if s in full_text)
        wrong_domain_hits = sum(1 for s in WRONG_DOMAIN_SIGNALS if s in full_text)

        raw = (manual_hits * 10) + (high_hits * 6) + (normal_hits * 2) \
              - (negative_hits * 4) - (brochure_hits * 8) - (wrong_domain_hits * 15)

        # Penalità pagine: meno pagine = più probabile che sia brochure/datasheet
        if total_pages < 5:
            raw -= 35   # quasi certamente brochure o copertina
        elif total_pages < 10:
            raw -= 18   # scheda tecnica sintetica, probabilmente non sufficiente
        elif total_pages < 20:
            raw -= 6    # leggera penalità: potrebbe essere manuale sintetico

        # ── Brand/model relevance check ──────────────────────────────────────
        # Se brand o model forniti, verifica che il PDF riguardi la macchina giusta.
        # Un manuale di un prodotto completamente diverso non deve mai vincere.
        if brand or model:
            brand_norm = brand.lower().strip()
            model_norm = model.lower().strip()

            # Cerca nelle prime 8000 chars (copertina + prime pagine)
            head_text = full_text[:8000]

            brand_in_head = brand_norm and brand_norm in head_text
            model_in_head = model_norm and len(model_norm) >= 3 and model_norm in head_text
            brand_in_full = brand_norm and brand_norm in full_text
            model_in_full = model_norm and len(model_norm) >= 3 and model_norm in full_text

            if brand_in_head:
                raw += 25   # brand nelle prime pagine → ottimo segnale
            elif brand_in_full:
                raw += 10   # brand nel documento ma non in copertina

            if model_in_head:
                raw += 20   # modello nelle prime pagine → ottimo segnale
            elif model_in_full:
                raw += 8    # modello nel corpo

            # Penalità se il brand non compare MAI nel documento intero.
            # Se però la categoria macchina corrisponde, penalità ridotta:
            # un manuale di escavatore generico è meglio di un manuale Ricoh.
            if brand_norm and len(brand_norm) >= 3 and not brand_in_full:
                # Usa keyword multilingua per riconoscere categoria anche in DE/EN/FR
                cat_keywords = _get_category_keywords(machine_type)
                category_match = bool(cat_keywords and any(kw in full_text for kw in cat_keywords))
                if category_match:
                    raw -= 15   # stessa categoria, brand diverso → penalità lieve
                else:
                    raw -= 45   # prodotto completamente diverso → scarta

            # Penalità aggiuntiva se nemmeno il modello compare (doppia assenza)
            if model_norm and len(model_norm) >= 3 and not model_in_full and not brand_in_full:
                raw -= 20

        return max(0, min(100, raw))

    except Exception:
        return 0


# Keyword di categoria in IT/EN/DE/FR per il matching multilingua
_CATEGORY_MULTILANG: dict[str, list[str]] = {
    # Perforatrici / Drilling rigs
    "perforatrice": ["perforatrice", "perforazione", "drill", "drilling", "bohrgerät", "bohranlage", "foreuse", "foreuse hydraulique"],
    "sonda": ["sonda", "drill rig", "bohrturm", "foreuse"],
    # Escavatori
    "escavatore": ["escavatore", "excavator", "bagger", "pelle", "pelleteuse", "minibagger"],
    "miniescavatore": ["miniescavatore", "mini excavator", "minibagger", "mini-pelle"],
    # Gru
    "gru": ["gru", "crane", "kran", "grue"],
    "autogru": ["autogru", "mobile crane", "mobilkran", "grue mobile", "grue automotrice"],
    # Piattaforme aeree
    "piattaforma aerea": ["piattaforma aerea", "aerial", "nacelle", "hubarbeitsbühne", "nacelle élévatrice"],
    "cestello": ["cestello", "boom lift", "arbeitsbühne", "plateforme"],
    # Carrelli elevatori
    "carrello elevatore": ["carrello elevatore", "forklift", "gabelstapler", "chariot élévateur"],
    # Compressori
    "compressore": ["compressore", "compressor", "kompressor", "compresseur"],
    # Betoniere / Pompe
    "betoniera": ["betoniera", "concrete mixer", "betonmischer", "bétonnière"],
    "pompa": ["pompa", "pump", "pumpe", "pompe"],
    # Macchine stradali
    "finitrice": ["finitrice", "paver", "fertiger", "finisseuse"],
    "rullo": ["rullo", "roller", "walze", "rouleau compresseur"],
    # Presse / Macchine utensili
    "pressa": ["pressa", "press", "presse", "presse plieuse"],
    "piegatrice": ["piegatrice", "bending", "abkantpresse", "presse plieuse"],
    # Generatori
    "generatore": ["generatore", "generator", "generator", "groupe électrogène"],
    # Sollevamento
    "paranchi": ["paranchi", "hoist", "hebezeug", "palan"],
    "sollevatore": ["sollevatore", "lift", "heber", "élévateur"],
}

def _get_category_keywords(machine_type: str) -> list[str]:
    """
    Restituisce le keyword di categoria in tutte le lingue per il machine_type dato.
    Cerca sia corrispondenza esatta che per sottostringa.
    """
    if not machine_type:
        return []
    mt_lower = machine_type.lower().strip()
    keywords: set[str] = set()

    for key, kws in _CATEGORY_MULTILANG.items():
        if key in mt_lower or mt_lower in key:
            keywords.update(kws)

    # Fallback: parole singole dal machine_type (≥4 char) come prima
    if not keywords:
        keywords.update(w for w in mt_lower.split() if len(w) >= 4)

    return list(keywords)


def classify_pdf_match(
    pdf_bytes: bytes,
    brand: str,
    model: str,
    machine_type: str = "",
) -> str:
    """
    Classifica la pertinenza del PDF rispetto alla macchina cercata.
    Funziona con manuali in IT/EN/DE/FR.
    Returns:
      "exact"     — brand o modello trovati → manuale del produttore specifico
      "category"  — stessa categoria (qualsiasi lingua) ma brand diverso → manuale simile
      "unrelated" — né brand né categoria → documento non pertinente
    """
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        sample_pages = min(15, total_pages)
        text = "".join(doc[i].get_text() for i in range(sample_pages)).lower()
        doc.close()

        brand_norm = brand.lower().strip()
        model_norm = model.lower().strip()

        brand_found = len(brand_norm) >= 3 and brand_norm in text
        model_found = len(model_norm) >= 3 and model_norm in text

        if brand_found or model_found:
            return "exact"

        # PDF scansionato (solo immagini, nessun testo): non possiamo verificare la categoria,
        # ma è comunque un documento reale — restituiamo "category" per non scartarlo.
        if len(text.strip()) < 200 and total_pages >= 10:
            return "category"

        # Cerca categoria in tutte le lingue supportate.
        # Soglia occorrenze dipende dalla dimensione del documento:
        # - PDF lungo (>20 pag): servono >=3 occorrenze per evitare falsi positivi su
        #   documenti generici multi-categoria (es. "Macchine in edilizia")
        # - PDF corto (<=20 pag): basta 1 occorrenza — è un documento focalizzato
        cat_keywords = _get_category_keywords(machine_type)
        if cat_keywords:
            total_count = sum(text.count(kw) for kw in cat_keywords)
            min_occ = 1 if total_pages <= 20 else 3
            if total_count >= min_occ:
                return "category"

        return "unrelated"
    except Exception:
        return "unknown"


def are_pdfs_same_content(pdf1: bytes, pdf2: bytes, sample_chars: int = 1500) -> bool:
    """
    Confronta i primi sample_chars caratteri di testo dei due PDF.
    Ritorna True se il contenuto è identico o quasi (stesso documento su siti diversi).
    """
    try:
        import fitz

        def _head(data: bytes) -> str:
            doc = fitz.open(stream=data, filetype="pdf")
            pages = min(3, len(doc))
            text = "".join(doc[i].get_text() for i in range(pages))
            doc.close()
            # Normalizza: minuscolo, elimina spazi multipli
            import re
            return re.sub(r"\s+", " ", text.lower().strip())[:sample_chars]

        h1 = _head(pdf1)
        h2 = _head(pdf2)
        if not h1 or not h2:
            return False
        # Identici o quasi (tolleranza 5% per differenze di codifica/rendering)
        common = sum(1 for a, b in zip(h1, h2) if a == b)
        similarity = common / max(len(h1), len(h2))
        return similarity >= 0.90
    except Exception:
        return False


def is_native_pdf(pdf_bytes: bytes) -> tuple[bool, float]:
    """
    Controlla se il PDF contiene testo nativo (non è solo immagini scansionate).
    Ritorna (is_native: bool, chars_per_page: float).
    Soglia: >= 100 caratteri per pagina in media = PDF nativo.
    PDF con meno testo sono probabilmente scansioni e non analizzabili correttamente dall'AI.
    """
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_chars = sum(len(page.get_text()) for page in doc)
        pages = max(len(doc), 1)
        doc.close()
        cpp = total_chars / pages
        return cpp >= 100, round(cpp, 1)
    except Exception:
        return False, 0.0


def count_pdf_pages(pdf_bytes: bytes) -> int:
    """Conta il numero di pagine del PDF."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0


def extract_full_text(pdf_bytes: bytes) -> str:
    """
    Estrae tutto il testo dal PDF.
    Se il PDF è una scansione (testo vuoto), tenta OCR via PyMuPDF + Tesseract.
    """
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        texts = [page.get_text() for page in doc]
        doc.close()
        result = "\n".join(texts)

        # Se il testo estratto è quasi vuoto, il PDF è probabilmente una scansione
        if len(result.strip()) < 50:
            result = _ocr_pdf_fallback(pdf_bytes)

        return result
    except Exception:
        return ""


def _ocr_pdf_fallback(pdf_bytes: bytes, max_pages: int = 30) -> str:
    """
    OCR su PDF-immagine (scansioni) tramite PyMuPDF → immagine + Tesseract.
    Usato solo quando extract_full_text() restituisce testo vuoto.
    Limita a max_pages per non bloccare il server su documenti enormi.
    """
    try:
        import fitz
        import pytesseract
        from PIL import Image
        import io

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages_to_ocr = min(max_pages, len(doc))
        texts = []

        for i in range(pages_to_ocr):
            page = doc[i]
            # Render a 200 DPI — bilanciamento qualità/velocità
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            # Tenta prima italiano, poi inglese come fallback
            try:
                text = pytesseract.image_to_string(img, lang="ita+eng")
            except Exception:
                text = pytesseract.image_to_string(img)
            texts.append(text)

        doc.close()
        return "\n".join(texts)

    except ImportError:
        # Tesseract non installato: degrada silenziosamente
        return ""
    except Exception:
        return ""


def extract_safety_relevant_text(pdf_bytes: bytes, max_pages: int = 50) -> str:
    """
    Estrae il testo dalle pagine più rilevanti per la sicurezza.
    Per PDF molto grandi (>100 pagine): usa keyword scoring per selezionare le pagine migliori.
    """
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)

        if total_pages <= max_pages:
            # PDF piccolo: estrai tutto
            texts = []
            for page in doc:
                texts.append(page.get_text())
            doc.close()
            return "\n".join(texts)

        # PDF grande: score ogni pagina per rilevanza sicurezza
        page_scores = []
        for i, page in enumerate(doc):
            text = page.get_text().lower()
            score = sum(1 for kw in SAFETY_KEYWORDS if kw in text)
            page_scores.append((i, score, page.get_text()))

        doc.close()

        # Seleziona le prime `max_pages` pagine per score + le prime 5 e ultime 5
        priority_indices = set(range(min(5, total_pages)))          # prime 5
        priority_indices |= set(range(max(0, total_pages - 5), total_pages))  # ultime 5

        top_by_score = sorted(page_scores, key=lambda x: x[1], reverse=True)
        for idx, score, _ in top_by_score[:max_pages]:
            priority_indices.add(idx)

        selected = sorted(priority_indices)[:max_pages]
        return "\n".join(page_scores[i][2] for i in selected if i < len(page_scores))

    except Exception:
        return ""


def chunk_text(text: str, max_chars: int = 80000) -> list[str]:
    """
    Divide il testo in chunk da inviare all'AI in sequenza (map-reduce).
    Taglia ai fine-paragrafo per mantenere la coerenza.
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        if end >= len(text):
            chunks.append(text[start:])
            break

        # Taglia al fine-paragrafo più vicino
        cut = text.rfind("\n\n", start, end)
        if cut == -1:
            cut = text.rfind("\n", start, end)
        if cut == -1:
            cut = end

        chunks.append(text[start:cut])
        start = cut + 1

    return [c for c in chunks if c.strip()]


def pdf_to_base64(pdf_bytes: bytes) -> str:
    """Converte bytes PDF in base64 per l'invio all'API Claude."""
    return base64.standard_b64encode(pdf_bytes).decode("utf-8")
