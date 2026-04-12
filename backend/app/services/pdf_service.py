"""
Download e processamento dei manuali PDF.
Gestisce: download streaming, controllo dimensioni, estrazione testo, chunking.
"""
import io
import base64
import logging
from typing import Optional, Tuple
from app.config import settings

_logger = logging.getLogger(__name__)

# Keywords per identificare pagine di sicurezza rilevanti — lette dal DB
_SAFETY_KEYWORDS_FALLBACK = frozenset({
    "rischio", "pericolo", "sicurezza", "protezione", "dpi", "avvertenza",
    "avviso", "attenzione", "warning", "danger", "risk", "safety", "hazard",
    "proteggere", "indossare", "vietato", "proibito", "dispositivo",
    "guanti", "elmetto", "casco", "occhiali", "stivali", "imbracatura",
})


def _get_safety_keywords() -> frozenset:
    from app.services.config_service import get_list
    return frozenset(get_list("safety_keywords", _SAFETY_KEYWORDS_FALLBACK))


# Alias di compatibilità per eventuale riferimento esterno
SAFETY_KEYWORDS = _SAFETY_KEYWORDS_FALLBACK


async def head_check_url(url: str, timeout: int = 8) -> tuple[bool, str]:
    """
    Verifica HEAD prima di scaricare: Content-Type, Content-Length.
    Ritorna (ok, motivo_rifiuto). Se HEAD non supportato (405/501) → (True, "") → procedi.
    Salta il check per URL locali (file system).
    """
    if url.startswith("/manuals/"):
        return True, ""
    import httpx
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ManualFinder/1.0)"},
        ) as c:
            r = await c.head(url)
        if r.status_code in (405, 501, 400, 403):
            return True, ""  # HEAD non supportato o bloccato: procedi comunque
        if r.status_code >= 400:
            return False, f"HTTP {r.status_code}"
        ct = r.headers.get("content-type", "").lower()
        # Rifiuta solo se CHIARAMENTE non-PDF (text/html e URL non finisce con .pdf)
        if "text/html" in ct and not url.lower().endswith(".pdf"):
            return False, f"Content-Type: {ct}"
        cl = r.headers.get("content-length")
        if cl:
            max_bytes = settings.max_pdf_size_mb * 1024 * 1024
            if int(cl) > max_bytes:
                return False, f"Troppo grande: {int(cl) // 1024 // 1024}MB"
        return True, ""
    except Exception:
        return True, ""  # Fallback: non bloccare la pipeline


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
    machine_type_id: Optional[int] = None,
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
    NORMAL_KW = list(_get_safety_keywords()) + [
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

    # Keyword strutturali — indicano presenza di indice/capitoli nelle prime pagine
    # Un documento con questi elementi è quasi certamente un manuale, non una brochure
    MANUAL_TOC_KW = [
        "indice", "sommario", "table of contents", "contents", "inhaltsverzeichnis", "sommaire",
        "capitolo 1", "capitolo 2", "chapter 1", "chapter 2", "kapitel 1", "chapitre 1",
        "sezione 1", "sezione 2", "section 1", "section 2", "abschnitt 1",
        "1.1 ", "1.2 ", "2.1 ", "2.2 ",   # numerazione sotto-sezioni
        "parte i", "parte ii", "part i", "part ii", "teil i",
        "introduzione", "introduction", "einleitung", "introduction",
        "avvertenze generali", "general warnings", "allgemeine warnhinweise",
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

        # ── Controllo struttura: TOC/capitoli nelle prime 3 pagine ───────────
        # Un manuale reale ha indice e capitoli — una brochure non ce li ha mai
        first_pages_text = full_text[:4000]
        toc_hits = sum(1 for kw in MANUAL_TOC_KW if kw in first_pages_text)
        if toc_hits >= 3:
            raw += 15   # struttura manuale ben definita
        elif toc_hits >= 1:
            raw += 5    # qualche elemento strutturale
        elif total_pages < 15 and manual_hits < 3 and high_hits < 2:
            raw -= 20   # corto, senza struttura e senza keyword chiave → brochure

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
                cat_keywords = _get_category_keywords(machine_type, machine_type_id)
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


def _get_category_keywords(
    machine_type: str,
    machine_type_id: Optional[int] = None,
) -> list[str]:
    """
    Restituisce le keyword di categoria per il machine_type dato, leggendole
    dalla tabella machine_aliases (più nome canonico machine_types.name).
    Non ci sono alias hardcoded: ogni variante deve esistere in DB.
    """
    try:
        from app.services.machine_type_service import get_category_keywords as _db_kw
        return _db_kw(machine_type=machine_type or None, machine_type_id=machine_type_id)
    except Exception as e:
        _logger.warning("_get_category_keywords: fallback a parole del machine_type: %s", e)
        if not machine_type:
            return []
        mt_lower = machine_type.lower().strip()
        return sorted({mt_lower, *[w for w in mt_lower.split() if len(w) >= 4]})


def classify_pdf_match(
    pdf_bytes: bytes,
    brand: str,
    model: str,
    machine_type: str = "",
    machine_type_id: Optional[int] = None,
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

        # Campione testo prime 3 pagine (cover + introduzione): segnale più affidabile
        head_text = text[:4000]

        # "exact": il brand appare nella cover/prime pagine (forte segnale)
        #   O appare >= 2 volte nel documento intero (non solo menzione di passaggio)
        # Per modello: >= 2 occorrenze nel testo intero (evita match casuali su stringhe corte)
        brand_in_head = len(brand_norm) >= 3 and brand_norm in head_text
        brand_count = text.count(brand_norm) if len(brand_norm) >= 3 else 0
        model_count = text.count(model_norm) if len(model_norm) >= 3 else 0

        brand_found = brand_in_head or brand_count >= 2
        model_found = model_count >= 2

        if brand_found or model_found:
            return "exact"

        # PDF scansionato (solo immagini, nessun testo): non possiamo verificare la categoria,
        # ma è comunque un documento reale — restituiamo "category" per non scartarlo.
        if len(text.strip()) < 200 and total_pages >= 10:
            return "category"

        # Cerca categoria in tutte le lingue supportate.
        # Soglia uniforme >= 3 occorrenze: evita falsi positivi su documenti generici
        # multi-categoria (es. "Macchine in edilizia" che cita ogni tipo di macchina 1-2 volte).
        cat_keywords = _get_category_keywords(machine_type, machine_type_id)
        total_count = 0
        if cat_keywords:
            total_count = sum(text.count(kw) for kw in cat_keywords)
            if total_count >= 3:
                return "category"

        _logger.info(
            "classify_pdf_match → unrelated: machine_type=%r id=%s "
            "keywords=%d (%s) total_hits=%d brand=%r model=%r text_sample=%d chars",
            machine_type, machine_type_id, len(cat_keywords),
            ",".join(cat_keywords[:8]), total_count,
            brand, model, len(text),
        )
        return "unrelated"
    except Exception as e:
        _logger.warning("classify_pdf_match error: %s", e)
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
            score = sum(1 for kw in _get_safety_keywords() if kw in text)
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


async def ai_quick_validate(
    pdf_bytes: bytes,
    brand: str,
    model: str,
    machine_type: str,
    provider: str,
) -> bool:
    """
    Validazione AI rapida: il PDF è un manuale d'uso/operatore?
    Usato solo per i casi ambigui (score 5-35 da score_pdf_safety_relevance).
    Usa modello economico (Haiku/Flash-Lite), costo ~$0.00002 per chiamata.
    Fallisce silenziosamente → True (non blocca la pipeline).
    """
    import asyncio as _asyncio
    try:
        # Estrai testo prime 3 pagine (cover + indice + prime istruzioni)
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = min(3, len(doc))
        first_text = "".join(doc[i].get_text() for i in range(pages)).strip()
        doc.close()

        if not first_text or len(first_text) < 80:
            return True  # PDF scansionato o vuoto: non scartare

        prompt = (
            f"Stai cercando un MANUALE D'USO E MANUTENZIONE per: {brand} {model}"
            f" ({machine_type or 'macchinario industriale'}).\n\n"
            f"TESTO PRIME PAGINE PDF:\n{first_text[:1800]}\n\n"
            "Questo documento è un MANUALE D'USO/OPERATORE (libretto istruzioni per l'operatore)?\n"
            "Rispondi SOLO con una parola: MANUALE oppure NON_MANUALE\n"
            "MANUALE: libretto uso, manuale operatore, istruzioni d'uso, operator manual, bedienungsanleitung\n"
            "NON_MANUALE: catalogo ricambi, brochure commerciale, datasheet, scheda prodotto, "
            "manuale officina/riparazione, service manual, listino prezzi"
        )

        answer = ""
        if provider == "anthropic":
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            resp = await _asyncio.wait_for(
                client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=5,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=8,
            )
            answer = resp.content[0].text.strip().upper()

        elif provider == "gemini":
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=settings.gemini_api_key)
            resp = await _asyncio.wait_for(
                client.aio.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        max_output_tokens=5, temperature=0.0,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                ),
                timeout=8,
            )
            answer = resp.text.strip().upper()

        else:
            return True

        return "NON_MANUALE" not in answer

    except Exception:
        return True  # Fallback silenzioso — non blocca la pipeline


async def ai_compare_manuals(
    pdf_a: bytes,
    pdf_b: bytes,
    machine_type: str,
    provider: str,
) -> int:
    """
    Confronto AI tra due PDF di categoria simile: restituisce 0 se A è migliore, 1 se B è migliore.

    Usato quando il manuale specifico del produttore non è disponibile e si trovano
    più candidati di categoria simile in locale. Usa modello economico (Haiku/Flash)
    per mantenere basso il costo (~$0.00003 per chiamata).
    Fallisce silenziosamente → 0 (usa A, già il migliore per score).
    """
    import asyncio as _asyncio
    try:
        import fitz

        def _first_pages_text(pdf_bytes: bytes, n_pages: int = 4) -> str:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            pages = min(n_pages, len(doc))
            text = "".join(doc[i].get_text() for i in range(pages)).strip()
            doc.close()
            return text

        text_a = _first_pages_text(pdf_a)[:2000]
        text_b = _first_pages_text(pdf_b)[:2000]

        if not text_a and not text_b:
            return 0  # Entrambi scansionati: usa A (già ordinato per score)

        prompt = (
            f"Devi scegliere il manuale più pertinente per la sicurezza di: {machine_type}.\n\n"
            f"MANUALE A (prime pagine):\n{text_a or '[testo non estraibile - PDF scansionato]'}\n\n"
            f"MANUALE B (prime pagine):\n{text_b or '[testo non estraibile - PDF scansionato]'}\n\n"
            "Quale manuale è più rilevante per la sicurezza e l'uso corretto di questa categoria di macchina?\n"
            "Considera: rischi specifici, procedure operative, norme di sicurezza, componenti tipici.\n"
            "Rispondi SOLO con una lettera: A oppure B"
        )

        answer = ""
        if provider == "anthropic":
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            resp = await _asyncio.wait_for(
                client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=3,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=10,
            )
            answer = resp.content[0].text.strip().upper()

        elif provider == "gemini":
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=settings.gemini_api_key)
            resp = await _asyncio.wait_for(
                client.aio.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        max_output_tokens=3, temperature=0.0,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                ),
                timeout=10,
            )
            answer = resp.text.strip().upper()

        else:
            return 0

        return 1 if answer.startswith("B") else 0

    except Exception:
        return 0  # Fallback silenzioso — usa A (già il migliore per score)


def pdf_to_base64(pdf_bytes: bytes) -> str:
    """Converte bytes PDF in base64 per l'invio all'API Claude."""
    return base64.standard_b64encode(pdf_bytes).decode("utf-8")
