"""
Routers analisi:
  POST /analyze/ocr   → solo OCR, ritorna PlateOCRResult (JSON)
  POST /analyze/full  → pipeline completa SSE (search → download → analisi)
                        riceve brand/model già confermati dall'utente
"""
import json
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from app.models.requests import PlateAnalysisRequest, FullAnalysisRequest
from app.models.responses import SSEEvent
from app.services import image_service, vision_service, search_service, pdf_service, analysis_service, safety_gate_service, quality_service

router = APIRouter()


# ── Endpoint 1: solo OCR ──────────────────────────────────────────────────────

@router.post("/ocr")
async def analyze_ocr(request: Request, body: PlateAnalysisRequest):
    """
    Esegue preprocessing + OCR sulla targa e restituisce i dati estratti.
    Il frontend mostra un form modificabile prima di procedere.
    """
    processed = image_service.preprocess_plate_image(body.image_base64)
    brightness = image_service.check_image_brightness(body.image_base64)
    result = await vision_service.extract_plate_info(processed)

    return {
        "brand": result.brand,
        "model": result.model,
        "machine_type": result.machine_type,
        "serial_number": result.serial_number,
        "year": result.year,
        "confidence": result.confidence,
        "raw_text": result.raw_text,
        "notes": result.notes,
        "brightness_warning": (
            "Immagine molto scura — OCR potrebbe essere impreciso." if brightness["is_too_dark"]
            else "Immagine sovraesposta — OCR potrebbe essere impreciso." if brightness["is_too_bright"]
            else None
        ),
    }


# ── Endpoint 2: pipeline completa SSE ────────────────────────────────────────

def _sse(event: SSEEvent) -> str:
    payload = json.dumps(event.model_dump(), ensure_ascii=False)
    return f"data: {payload}\n\n"


async def _pipeline(request: FullAnalysisRequest):
    """Generatore SSE: search → download → analisi. OCR già fatto."""

    brand = request.brand.strip()
    model = request.model.strip()
    machine_type = request.machine_type.strip() if request.machine_type else None
    machine_year = request.year.strip() if getattr(request, "year", None) else None
    serial_number = getattr(request, "serial_number", None) or None
    norme = getattr(request, "norme", None) or []
    qr_url = getattr(request, "qr_url", None)

    # ── STEP 1: Ricerca Manuale ──────────────────────────────────────────
    search_msg = f"Ricerca manuale per {brand} {model}"
    if machine_type:
        search_msg += f" (tipo: {machine_type})"
    is_ante_ce = False
    is_allegato_v = False  # Macchine ante-1996: Allegato V D.Lgs. 81/08
    if machine_year:
        try:
            year_int = int(machine_year)
            is_ante_ce = year_int < 2006
            is_allegato_v = year_int < 1996  # Prima della prima Direttiva Macchine
            search_msg += f", anno {machine_year}"
            if is_allegato_v:
                search_msg += " ⚠ Allegato V D.Lgs.81"
            elif is_ante_ce:
                search_msg += " ⚠ ante-CE"
        except (ValueError, TypeError):
            pass
    search_msg += "..."

    yield _sse(SSEEvent(
        step="search", status="started", progress=10,
        message=search_msg,
    ))
    await asyncio.sleep(0)

    try:
        # Esegui ricerca manuale e Safety Gate in parallelo
        search_results, safety_alerts = await asyncio.gather(
            search_service.search_manual(
                brand=brand,
                model=model,
                machine_type=machine_type,
                lang=request.preferred_language,
                machine_year=machine_year,
                serial_number=serial_number,
            ),
            safety_gate_service.check_safety_alerts(brand, model),
            return_exceptions=True,
        )
        if isinstance(search_results, Exception):
            search_results = []
        if isinstance(safety_alerts, Exception):
            safety_alerts = []
    except Exception:
        search_results = []
        safety_alerts = []

    pdf_candidates = [r for r in search_results if r.is_pdf]
    
    # Controlla se c'è un manuale locale
    local_manual_found = any(r.source_type == "inail" and "Locale" in r.title for r in search_results)

    search_message = f"Trovati {len(search_results)} risultati ({len(pdf_candidates)} PDF)."
    if qr_url:
        search_message = f"QR Code rilevato sulla targa — link diretto al manuale. " + search_message
    if local_manual_found:
        search_message = f"Manuale INAIL locale trovato per '{machine_type}'. + {len(search_results) - 1} risultati online."

    # Prepara alert Safety Gate da includere nel payload
    safety_alerts_data = [a.to_dict() for a in safety_alerts] if safety_alerts else []
    if safety_alerts:
        serious = [a for a in safety_alerts if a.risk_level == "serious"]
        alert_msg = f" ⚠ ATTENZIONE: {len(safety_alerts)} avviso/i Safety Gate EU"
        if serious:
            alert_msg = f" 🚨 ALERT: {len(serious)} avviso GRAVE Safety Gate EU per {brand} {model}!"
        search_message += alert_msg

    yield _sse(SSEEvent(
        step="search", status="completed", progress=35,
        message=search_message if search_results else "Nessun manuale trovato online. Procedo con analisi AI.",
        data={
            "results": [r.model_dump() for r in search_results[:5]],
            "found": bool(search_results),
            "local_manual": local_manual_found,
            "safety_alerts": safety_alerts_data,
        },
    ))

    # ── STEP 2: Download PDF ─────────────────────────────────────────────
    # (lo scraping HTML è ora dentro search_manual — i pdf_candidates già includono
    #  i PDF trovati per scraping di produttore e pagine HTML)

    # Se il QR Code sulla targa punta direttamente a un manuale, aggiungilo come candidato prioritario
    if qr_url:
        from app.models.responses import ManualSearchResult as MSR
        qr_candidate = MSR(
            url=qr_url,
            title=f"Manuale da QR Code — {brand} {model}",
            source_type="manufacturer",
            language="unknown",
            is_pdf=qr_url.lower().endswith(".pdf"),
            relevance_score=95,  # Alta priorità: link diretto dal costruttore
        )
        pdf_candidates.insert(0, qr_candidate)

    # Domini che ospitano schede normative/INAIL — trattati come INAIL, non produttore
    INAIL_MIRROR_DOMAINS = [
        "necsi.it", "aliseo", "ispesl.it", "dors.it",
        "salute.gov.it", "lavoro.gov.it", "inail.it",
        "ausl.", "asl.", "spresal", "spisal",
        "portaleagenti.it", "sicurezzaentipubblici",
        # CPT/FormedilTorino: "Le macchine in edilizia" — buono per cantiere,
        # ma è un documento GENERICO multi-categoria → trattalo come INAIL e
        # applica il classify_pdf_match per verificare la pertinenza al tipo specifico
        "formediltorinofsc.it",
        # PuntoSicuro e altri portali istituzionali sicurezza
        "puntosicuro.it",
        "suva.ch",
    ]

    def _is_inail_mirror(url: str) -> bool:
        from urllib.parse import urlparse
        full = (urlparse(url).netloc + urlparse(url).path).lower()
        return any(d in full for d in INAIL_MIRROR_DOMAINS)

    # Separa candidati: INAIL locale/mirror vs manuale produttore online
    inail_candidates = [r for r in pdf_candidates
                        if r.source_type == "inail" or _is_inail_mirror(r.url)]
    producer_candidates = [r for r in pdf_candidates
                           if r.source_type != "inail" and not _is_inail_mirror(r.url)]

    inail_bytes = None
    inail_url = None
    producer_bytes = None
    producer_url = None
    producer_pages = 0
    producer_match_type = "unknown"
    producer_source_label = f"Produttore ({brand})"

    if pdf_candidates:
        download_parts = []
        if inail_candidates:
            download_parts.append("scheda INAIL")
        if producer_candidates:
            download_parts.append("manuale produttore")

        yield _sse(SSEEvent(
            step="download", status="started", progress=40,
            message=f"Download {' + '.join(download_parts)} in corso...",
        ))

        # Scarica scheda INAIL — prova fino a 3 candidati in parallelo, scegli il più pertinente
        async def _download_inail(candidate):
            pdf_data, _ = await pdf_service.download_pdf(candidate.url)
            if pdf_data:
                score = pdf_service.score_pdf_safety_relevance(
                    pdf_data, brand=brand, model=model, machine_type=machine_type or ""
                )
                return (score, pdf_data, candidate.url)
            return None

        inail_downloads = await asyncio.gather(
            *[_download_inail(c) for c in inail_candidates[:3]], return_exceptions=True
        )
        inail_scored = sorted(
            [r for r in inail_downloads if isinstance(r, tuple)],
            key=lambda x: x[0], reverse=True
        )
        if inail_scored:
            # Scegli il migliore con score minimo: un documento INAIL a 0/100 è generico
            # (es. manuale generico edilizia invece di scheda specifica carrelli/PLE)
            INAIL_MIN_SCORE = 5
            for inail_entry in inail_scored:
                _iscore, _ibytes, _iurl = inail_entry
                if _iscore < INAIL_MIN_SCORE:
                    continue
                # Verifica pertinenza tipo macchina: scarta se categoricamente non correlato
                if machine_type:
                    _imatch = pdf_service.classify_pdf_match(_ibytes, brand, model, machine_type)
                    if _imatch == "unrelated":
                        continue  # prova il prossimo candidato
                inail_bytes, inail_url = _ibytes, _iurl
                break

        # Filtra URL con domini o path chiaramente non industriali prima di scaricare
        def _is_industrial_url(url: str) -> bool:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            path = parsed.path.lower()
            full = domain + path

            # Domini non industriali
            NON_INDUSTRIAL_DOMAINS = [
                "ospedale", "hospital", "clinic", "sanit", "medic", "salute",
                "infermier", "farmac", "bambin", "pediatr",
                "universit", "scuola", "school", "college", "accadem", "istruzion",
                "news", "giornale", "corriere", "gazzett", "notizie", "stampa",
                "comune.", "provincia.", "regione.", "governo.", "pubblica-amminist",
                "tribunale", "prefettura", "questura",
            ]
            if any(p in domain for p in NON_INDUSTRIAL_DOMAINS):
                return False

            # Attrezzatura per ufficio — non macchine da cantiere
            # Controlla sia dominio che path dell'URL
            OFFICE_EQUIPMENT = [
                "ricoh", "canon", "epson", "brother", "xerox", "konica", "kyocera",
                "streampunch", "laminator", "shredder", "binder", "binding",
                "fellowes", "gbc.com", "acco.", "leitz", "rexel",
                "printer", "copier", "scanner", "fax",
            ]
            if any(p in full for p in OFFICE_EQUIPMENT):
                return False

            # Cataloghi attrezzature/utensili — non manuali d'uso sicurezza
            CATALOG_URL_SIGNALS = [
                "tooling_catalog", "tooling-catalog", "tooling_guide",
                "parts_catalog", "parts-catalog", "spare_parts",
                "catalogo_ricambi", "catalogo_attrezzature", "catalogo_utensili",
                "price_list", "listino_prezzi",
            ]
            if any(p in path.replace(" ", "_").replace("%20", "_") for p in CATALOG_URL_SIGNALS):
                return False

            return True

        producer_candidates = [c for c in producer_candidates if _is_industrial_url(c.url)]

        # Filtra per titolo: scarta risultati il cui titolo contraddice il brand/modello cercato
        def _title_is_plausible(candidate, brand: str, model: str) -> bool:
            title = candidate.title.lower()
            brand_l = brand.lower()
            # Marchi palesemente estranei nel titolo → scarta
            OFFICE_BRANDS_IN_TITLE = [
                "ricoh", "canon", "epson", "brother", "xerox", "konica", "kyocera",
                "streampunch", "fellowes", "leitz", "rexel", "acco", "dymo",
                "samsung", "lg", "sony", "philips", "siemens home",
            ]
            if any(b in title for b in OFFICE_BRANDS_IN_TITLE):
                # Ammetti solo se il titolo menziona anche il brand cercato
                return brand_l in title
            return True

        producer_candidates = [
            c for c in producer_candidates if _title_is_plausible(c, brand, model)
        ]

        # Selezione candidati produttore per tier di affidabilità:
        # Tier 1 (score >= 55): produttore ufficiale o portale noleggio con PDF
        # Tier 2 (score 25–54): aggregatori e web con PDF
        # Scarica prima il tier 1, poi tier 2 solo se tier 1 non basta
        tier1 = [c for c in producer_candidates if c.relevance_score >= 55]
        tier2 = [c for c in producer_candidates if c.relevance_score < 55]
        ordered_candidates = (tier1 + tier2)[:5]

        async def _download_and_score(candidate):
            pdf_data, _ = await pdf_service.download_pdf(candidate.url)
            if pdf_data:
                pages = pdf_service.count_pdf_pages(pdf_data)
                score = pdf_service.score_pdf_safety_relevance(
                    pdf_data, brand=brand, model=model,
                    machine_type=machine_type or "",
                )
                return (score, pdf_data, candidate.url, candidate.relevance_score, pages)
            return None

        download_tasks = [_download_and_score(c) for c in ordered_candidates]
        download_results = await asyncio.gather(*download_tasks)
        producer_scored: list[tuple[int, bytes, str, int, int]] = [r for r in download_results if r is not None]
        _brochure_note = None  # impostato sotto se il PDF viene scartato

        # Soglie qualità:
        # - safety score < 20 → bassa pertinenza sicurezza (raised from 12 to reject catalogs)
        # - pagine < 8 → quasi certamente brochure/datasheet, non manuale
        # Se il PDF è sia corto che a basso score, viene scartato in favore del fallback AI
        LOW_QUALITY_THRESHOLD = 20
        MIN_MANUAL_PAGES = 8

        if producer_scored:
            # Sort combinato: content score (70%) + autorità fonte dalla ricerca (30%).
            # Evita che un PDF da fonte sconosciuta con score marginalmente più alto
            # batta un PDF dal sito ufficiale del produttore.
            producer_scored.sort(
                key=lambda x: x[0] * 0.7 + x[3] * 0.3,
                reverse=True
            )

            # Cerca il migliore che soddisfi i criteri di qualità.
            # Documenti molto corti (< 8 pag.) richiedono score alto (≥ 45) per essere accettati:
            # una brochure da 2 pagine con score 30 non è un manuale, anche se "passa" la soglia base.
            best = None
            for entry in producer_scored:
                score, pdf_data, url, rel_score, pages = entry
                if pages >= MIN_MANUAL_PAGES and score >= LOW_QUALITY_THRESHOLD:
                    best = entry  # documento sufficientemente lungo e rilevante
                    break
                if pages < MIN_MANUAL_PAGES and score >= 45:
                    best = entry  # documento corto ma con contenuto sicurezza molto specifico
                    break

            # Se tutti i PDF sono brochure cortissime a basso score, scarta
            if best is None:
                best_pages = producer_scored[0][4]
                best_score_val = producer_scored[0][0]
                # Logga il motivo dello scarto nel messaggio SSE (sotto)
                producer_scored = []  # forza fallback AI
                _brochure_note = (
                    f"PDF scartato: {best_pages} pag., score {best_score_val}/100 "
                    "(brochure o datasheet senza dati di sicurezza). Procedo con analisi AI."
                )
            else:
                _brochure_note = None
                best_score, producer_bytes, producer_url, _, producer_pages = best

        # Classifica il PDF produttore selezionato: exact | category | unrelated
        if producer_bytes:
            producer_match_type = pdf_service.classify_pdf_match(
                producer_bytes, brand, model, machine_type or ""
            )
            if producer_match_type == "category":
                producer_source_label = f"Manuale categoria simile ({machine_type or 'macchina'})"
            elif producer_match_type == "unrelated":
                producer_bytes = None
                producer_source_label = "AI"

        # Deduplica: se il PDF produttore è lo stesso documento dell'INAIL (mirror),
        # non ha senso analizzarlo due volte — meglio fallback AI per le raccomandazioni
        if producer_bytes and inail_bytes:
            if pdf_service.are_pdfs_same_content(producer_bytes, inail_bytes):
                producer_bytes = None
                producer_source_label = "AI"
                _brochure_note = (
                    "Manuale produttore identico alla scheda INAIL — "
                    "raccomandazioni specifiche generate da conoscenza AI."
                )

        parts_ok = []
        if inail_bytes:
            parts_ok.append(f"INAIL ({pdf_service.count_pdf_pages(inail_bytes)} pag.)")
        if producer_bytes:
            n_tried = len(producer_scored)
            safety_score = producer_scored[0][0] if producer_scored else 0
            quality_label = "" if safety_score >= LOW_QUALITY_THRESHOLD else " ⚠ bassa pertinenza"
            match_label = "" if producer_match_type == "exact" else " ⚠ categoria simile"
            parts_ok.append(
                f"produttore ({producer_pages} pag., "
                f"selezionato tra {n_tried} — sicurezza: {safety_score}/100{quality_label}{match_label})"
            )

        if not parts_ok and _brochure_note:
            dl_msg = _brochure_note
        elif parts_ok:
            dl_msg = f"Scaricati: {', '.join(parts_ok)}."
        else:
            dl_msg = "Impossibile scaricare i PDF. Procedo con analisi AI."

        yield _sse(SSEEvent(
            step="download", status="completed", progress=60,
            message=dl_msg,
            data={"inail_url": inail_url, "producer_url": producer_url,
                  "producer_pages": producer_pages},
        ))
    else:
        yield _sse(SSEEvent(
            step="download", status="completed", progress=60,
            message="Nessun PDF disponibile. Analisi basata su conoscenza AI.",
            data={"inail_url": None, "producer_url": None, "producer_pages": 0},
        ))

    # ── STEP 3: Analisi Sicurezza ────────────────────────────────────────
    has_both = inail_bytes and producer_bytes
    if has_both:
        match_note = "" if producer_match_type == "exact" else " (categoria simile)"
        msg = f"Analisi combinata INAIL + manuale produttore{match_note}..."
    elif inail_bytes:
        msg = f"Analisi scheda INAIL ({pdf_service.count_pdf_pages(inail_bytes)} pag.)..."
    elif producer_bytes:
        match_note = "" if producer_match_type == "exact" else " (categoria simile)"
        msg = f"Analisi manuale produttore{match_note} ({producer_pages} pag.)..."
    else:
        msg = "Generazione scheda sicurezza dalla conoscenza AI..."

    yield _sse(SSEEvent(step="analysis", status="started", progress=65, message=msg))

    try:
        safety_card = await analysis_service.generate_safety_card(
            brand=brand, model=model,
            inail_bytes=inail_bytes, inail_url=inail_url,
            producer_bytes=producer_bytes, producer_url=producer_url,
            producer_page_count=producer_pages,
            machine_year=machine_year,
            machine_type=machine_type,
            is_ante_ce=is_ante_ce,
            is_allegato_v=is_allegato_v,
            norme=norme,
            producer_source_label=producer_source_label,
        )
    except Exception as e:
        yield _sse(SSEEvent(
            step="analysis", status="failed", progress=65,
            message=f"Errore analisi: {str(e)}", data={"error": str(e)},
        ))
        return

    # Aggiungi alert Safety Gate alla scheda
    if safety_alerts_data:
        safety_card.safety_alerts = safety_alerts_data

    # ── Quality logging (non-blocking, non solleva eccezioni) ─────────────
    quality_service.log_analysis(
        brand=brand, model=model, machine_type=machine_type,
        safety_card=safety_card,
        producer_match_type=producer_match_type,
        producer_pages=producer_pages,
        inail_url=inail_url,
        producer_url=producer_url,
    )

    yield _sse(SSEEvent(step="analysis", status="completed", progress=90, message="Scheda generata."))

    # ── COMPLETE ──────────────────────��──────────────────────────────────
    yield _sse(SSEEvent(
        step="complete", status="completed", progress=100,
        message="Analisi completata.",
        data={"safety_card": safety_card.model_dump()},
    ))


@router.get("/quality-log")
async def get_quality_log(
    only_issues: bool = False,
    severity: str = "low",
    summary_only: bool = False,
):
    """
    Log di qualità delle analisi accumulate in questa sessione del server.
    Parametri:
      only_issues=true   → mostra solo analisi con almeno un issue
      severity=medium    → mostra solo issue di severità >= medium/high
      summary_only=true  → solo statistiche aggregate, nessun dettaglio
    """
    if summary_only:
        return quality_service.get_summary()
    return {
        "summary": quality_service.get_summary(),
        "entries": quality_service.get_log(only_with_issues=only_issues, min_severity=severity),
    }


@router.post("/full")
async def analyze_full(request: Request, body: FullAnalysisRequest):
    """
    Pipeline completa (search → download → analisi) con SSE.
    Riceve brand e model già confermati/corretti dall'utente.
    """
    return StreamingResponse(
        _pipeline(body),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Endpoint legacy (manteniamo compatibilità) ────────────────────────────────
@router.post("/plate")
async def analyze_plate_legacy(request: Request, body: PlateAnalysisRequest):
    """Endpoint legacy: OCR + pipeline in un solo SSE. Usato solo come fallback."""
    from app.models.requests import FullAnalysisRequest as FAR

    async def _combined():
        yield _sse(SSEEvent(step="ocr", status="started", progress=5, message="Lettura targa..."))
        processed = image_service.preprocess_plate_image(body.image_base64)
        ocr = await vision_service.extract_plate_info(processed)
        yield _sse(SSEEvent(
            step="ocr", status="completed", progress=20,
            message=f"Identificato: {ocr.brand or '?'} {ocr.model or '?'}",
            data={"brand": ocr.brand, "model": ocr.model, "confidence": ocr.confidence},
        ))
        brand = ocr.brand or "Sconosciuto"
        model = ocr.model or "Sconosciuto"
        full_req = FAR(image_base64=body.image_base64, brand=brand, model=model)
        async for chunk in _pipeline(full_req):
            yield chunk

    return StreamingResponse(
        _combined(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
