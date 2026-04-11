"""
Routers analisi:
  POST /analyze/ocr   → solo OCR, ritorna PlateOCRResult (JSON)
  POST /analyze/full  → pipeline completa SSE (search → download → analisi)
                        riceve brand/model già confermati dall'utente
"""
import json
import asyncio
from typing import Optional
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from app.models.requests import PlateAnalysisRequest, FullAnalysisRequest
from app.models.responses import SSEEvent
from app.services import image_service, vision_service, search_service, pdf_service, analysis_service, safety_gate_service, quality_service
from app.config import settings

router = APIRouter()

# URL QR che non puntano a documenti (portali assistenza, landing page, ecc.)
_QR_SERVICE_PATTERNS = [
    "service/scan", "/scan?", "/aftersales", "/support/scan",
    "cat.com/service", "komatsu.com/scan", "/qrcode/", "/qr?",
    "parts.cat.com", "sos.cat.com",
]


def _filter_qr_urls(urls: list[str]) -> list[str]:
    """Scarta URL QR che puntano a portali-servizio invece che a documenti."""
    filtered = []
    for u in urls:
        u_low = u.lower()
        if not any(p in u_low for p in _QR_SERVICE_PATTERNS):
            filtered.append(u)
    return filtered


# ── Endpoint 1: solo OCR ──────────────────────────────────────────────────────

@router.post("/ocr")
async def analyze_ocr(request: Request, body: PlateAnalysisRequest):
    """
    Esegue preprocessing + OCR sulla targa e restituisce i dati estratti.
    Il frontend mostra un form modificabile prima di procedere.
    """
    from fastapi import HTTPException as _HTTPException
    # Validazione preliminare: rifiuta immagini che non sono targhe/etichette macchina
    is_plate = await vision_service.validate_plate_image(body.image_base64)
    if not is_plate:
        raise _HTTPException(
            status_code=422,
            detail={
                "code": "not_a_plate",
                "message": (
                    "L'immagine caricata non sembra essere una targa o etichetta di macchinario. "
                    "Scatta una foto ravvicinata della targa identificativa del macchinario "
                    "(quella con marca, modello e matricola)."
                ),
            },
        )
    brightness = image_service.check_image_brightness(body.image_base64)
    # Scegli il preprocessing ottimale in base alla luminosità rilevata
    if brightness["is_too_dark"]:
        processed = image_service.preprocess_plate_image_variant(body.image_base64, 1)  # alto contrasto
    elif brightness["is_too_bright"]:
        processed = image_service.preprocess_plate_image_variant(body.image_base64, 2)  # denoised
    else:
        processed = image_service.preprocess_plate_image(body.image_base64)             # standard
    result = await vision_service.extract_plate_info(processed)
    # Multi-shot OCR: confidence bassa, brand non estratto, o testo quasi assente
    _should_multishot = (
        result.confidence == "low"
        or result.brand is None
        or len((result.raw_text or "").strip()) < 30
    )
    if _should_multishot:
        result = await vision_service.extract_plate_info_multishot(body.image_base64)

    return {
        "brand": result.brand,
        "model": result.model,
        "machine_type": result.machine_type,
        "machine_type_id": result.machine_type_id,
        "serial_number": result.serial_number,
        "year": result.year,
        "confidence": result.confidence,
        "raw_text": result.raw_text,
        "notes": result.notes,
        "qr_url": result.qr_url,
        "qr_urls": result.qr_urls,
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
    machine_type_id: Optional[int] = getattr(request, "machine_type_id", None)
    machine_year = request.year.strip() if getattr(request, "year", None) else None
    serial_number = getattr(request, "serial_number", None) or None
    norme = getattr(request, "norme", None) or []
    # Risolve qr_urls: usa lista nuova se disponibile, altrimenti fallback su singolo qr_url
    _qr_urls_raw: list[str] = list(getattr(request, "qr_urls", None) or [])
    _qr_legacy = getattr(request, "qr_url", None)
    if not _qr_urls_raw and _qr_legacy:
        _qr_urls_raw = [_qr_legacy]
    qr_urls = _filter_qr_urls(_qr_urls_raw)
    qr_url = qr_urls[0] if qr_urls else None  # backward compat per messaggi SSE

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

    # Timeout differenziati: ricerca manuale lenta (120s), safety alerts breve (30s).
    # Eseguiamo i due task con timeout individuali così uno slow brand non blocca tutto.
    _log = __import__("logging").getLogger(__name__)

    async def _search_with_timeout():
        try:
            return await asyncio.wait_for(
                search_service.search_manual(
                    brand=brand,
                    model=model,
                    machine_type=machine_type,
                    lang=request.preferred_language,
                    machine_year=machine_year,
                    serial_number=serial_number,
                    machine_type_id=machine_type_id,
                ),
                timeout=120,
            )
        except asyncio.TimeoutError:
            _log.warning("search_manual timeout (120s) per %s %s", brand, model)
            return []
        except Exception as e:
            _log.warning("search_manual errore per %s %s: %s", brand, model, e)
            return []

    async def _alerts_with_timeout():
        try:
            return await asyncio.wait_for(
                safety_gate_service.check_safety_alerts(brand, model),
                timeout=30,
            )
        except asyncio.TimeoutError:
            _log.warning("check_safety_alerts timeout (30s) per %s %s", brand, model)
            return []
        except Exception:
            return []

    search_results, safety_alerts = await asyncio.gather(
        _search_with_timeout(),
        _alerts_with_timeout(),
    )

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

    # Se i QR Code sulla targa puntano direttamente a manuali, aggiungili come candidati prioritari
    if qr_urls:
        from app.models.responses import ManualSearchResult as MSR
        for i, qu in enumerate(qr_urls):
            qr_candidate = MSR(
                url=qu,
                title=f"Manuale da QR Code — {brand} {model}",
                source_type="manufacturer",
                language="unknown",
                is_pdf=qu.lower().endswith(".pdf"),
                relevance_score=95 - i,  # Alta priorità; primo QR > secondo
            )
            pdf_candidates.insert(i, qr_candidate)

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

    # Separa candidati: INAIL locale/mirror vs datasheet vs manuale produttore online
    inail_candidates = [r for r in pdf_candidates
                        if r.source_type == "inail" or _is_inail_mirror(r.url)]
    datasheet_candidates = [r for r in pdf_candidates
                            if r.source_type == "datasheet" and not _is_inail_mirror(r.url)]
    producer_candidates = [r for r in pdf_candidates
                           if r.source_type not in ("inail", "datasheet") and not _is_inail_mirror(r.url)]

    inail_bytes = None
    inail_url = None
    datasheet_bytes = None
    datasheet_url = None
    producer_bytes = None
    producer_url = None
    producer_pages = 0
    producer_match_type = "unknown"
    producer_source_label = f"Produttore ({brand})"
    _brochure_note = None
    _producer_scored_count = 0

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
            INAIL_MIN_SCORE = 5
            # Passo 1: priorità assoluta ai PDF locali (/manuals/local/).
            # Schede INAIL preapprovate dall'admin: si usano sempre, nessun controllo
            # score/classify (sono scansionate, generiche di categoria, il brand/model
            # non ci sarà mai). Regola esplicita dell'utente.
            for inail_entry in inail_scored:
                _iscore, _ibytes, _iurl = inail_entry
                if _iurl.startswith("/manuals/local/"):
                    inail_bytes, inail_url = _ibytes, _iurl
                    break
            # Passo 2: nessun locale → usa il miglior PDF online non-unrelated
            if inail_bytes is None:
                for inail_entry in inail_scored:
                    _iscore, _ibytes, _iurl = inail_entry
                    if _iscore < INAIL_MIN_SCORE:
                        continue
                    if _iurl.startswith("/manuals/local/"):
                        continue  # già tentato nel passo 1
                    if machine_type:
                        _imatch = pdf_service.classify_pdf_match(_ibytes, brand, model, machine_type)
                        if _imatch == "unrelated":
                            continue
                    inail_bytes, inail_url = _ibytes, _iurl
                    break

        # Scarica scheda tecnica commerciale (datasheet) — usata solo per limiti_operativi
        # Soglia pagine: <= 20 = datasheet breve. Se più lungo → reindirizza a producer.
        DATASHEET_MAX_PAGES = 20
        if datasheet_candidates:
            for ds_candidate in datasheet_candidates[:2]:
                try:
                    ok, _ = await pdf_service.head_check_url(ds_candidate.url)
                    if not ok:
                        continue
                    ds_data, _ = await pdf_service.download_pdf(ds_candidate.url)
                    if not ds_data:
                        continue
                    ds_pages = pdf_service.count_pdf_pages(ds_data)
                    if ds_pages > DATASHEET_MAX_PAGES:
                        # Documento troppo lungo: reindirizza al percorso manuale
                        if not producer_bytes:
                            producer_bytes = ds_data
                            producer_url = ds_candidate.url
                            producer_pages = ds_pages
                    else:
                        datasheet_bytes = ds_data
                        datasheet_url = ds_candidate.url
                    break
                except Exception:
                    continue

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
                "depliant", "flyer", "leaflet",
                "product-line", "product_line", "productline", "lineup", "line-up",
                "tv-product", "range-overview", "portfolio",
            ]
            if any(p in path.replace(" ", "_").replace("%20", "_") for p in CATALOG_URL_SIGNALS):
                return False

            # Domini che producono solo cataloghi/listini
            from app.services.search_service import _EXCLUDE_DOMAINS
            if any(d in domain for d in _EXCLUDE_DOMAINS):
                return False

            # Regole dinamiche apprese dai feedback ispettori (cache 15 min)
            try:
                from app.services.feedback_analyzer_service import get_dynamic_rules
                _dyn_domains, _dyn_fragments, _ = get_dynamic_rules()
                if any(d in domain for d in _dyn_domains):
                    return False
                if any(f in path for f in _dyn_fragments):
                    return False
            except Exception:
                pass

            # URL segnalati dagli ispettori — blocco differenziato per tipo di segnalazione
            try:
                from app.services.saved_manuals_service import (
                    get_blocked_urls, get_context_blocked_urls
                )
                # not_a_manual: non è un manuale → scarta sempre
                if url in get_blocked_urls():
                    return False
                # wrong_category: manuale valido ma per altra categoria → scarta solo
                # se la ricerca attuale è per lo stesso tipo macchina in cui è stato segnalato
                if machine_type:
                    mt_lower = machine_type.lower().strip()
                    ctx_blocked = get_context_blocked_urls()
                    if (url, mt_lower) in ctx_blocked:
                        return False
            except Exception:
                pass

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

        _analysis_provider = settings.get_analysis_provider()

        async def _download_and_score(candidate):
            # Pre-screening HEAD: evita di scaricare pagine HTML o file troppo grandi
            import logging as _log
            ok, reason = await pdf_service.head_check_url(candidate.url)
            if not ok:
                _log.getLogger(__name__).info("HEAD skip: %s — %s", candidate.url[:80], reason)
                return None
            pdf_data, err = await pdf_service.download_pdf(candidate.url)
            if pdf_data:
                pages = pdf_service.count_pdf_pages(pdf_data)
                score = pdf_service.score_pdf_safety_relevance(
                    pdf_data, brand=brand, model=model,
                    machine_type=machine_type or "",
                )
                # Validazione AI per casi ambigui: score basso su PDF di dimensione media
                # (troppo corto per sicuri, ma non chiaramente una brochure)
                if 5 <= score <= 30 and pages < 25 and _analysis_provider in ("anthropic", "gemini"):
                    is_manual = await pdf_service.ai_quick_validate(
                        pdf_data, brand, model, machine_type or "", _analysis_provider
                    )
                    if not is_manual:
                        score = 0  # Forza rifiuto — l'AI ha confermato non-manuale
                return (score, pdf_data, candidate.url, candidate.relevance_score, pages)
            _log.getLogger(__name__).info("PDF download failed: %s — %s", candidate.url[:80], err)
            return None

        download_tasks = [_download_and_score(c) for c in ordered_candidates]
        download_results = await asyncio.gather(*download_tasks)
        producer_scored: list[tuple[int, bytes, str, int, int]] = [r for r in download_results if r is not None]
        _producer_scored_count = len(producer_scored)  # conta prima degli scarti

        # Soglie qualità:
        # Un PDF viene accettato se:
        #   A) Ha testo estraibile (score > 0) ed è abbastanza lungo (>= 8 pag.)
        #   B) È molto lungo (>= 30 pag.) anche con score 0 — probabilmente scansionato
        #      ma comunque un documento reale, non una brochure da 2 pagine
        #   C) È corto ma con score di sicurezza molto alto (>= 40) — spec sheet con
        #      sezioni sicurezza esplicite
        # Viene scartato SOLO se è corto E non ha contenuto sicurezza rilevante.
        LOW_QUALITY_THRESHOLD = 8   # score minimo per PDF corti (< 30 pag.)
        MIN_MANUAL_PAGES = 5        # sotto questa soglia serve score >= 40; schede tecniche 5-7pp già validate dall'AI ora accettate
        SCANNED_PAGES_THRESHOLD = 30  # PDF lungo anche senza testo → probabilmente scansionato

        if producer_scored:
            # Sort combinato: content score (70%) + autorità fonte dalla ricerca (30%).
            producer_scored.sort(
                key=lambda x: x[0] * 0.7 + x[3] * 0.3,
                reverse=True
            )

            best = None
            rejection_reasons = []
            # Set URL dei manuali DB (preapprovati dall'admin): bypassano il quality
            # threshold e hanno priorità assoluta sui risultati web, anche con score
            # più basso. Sono stati verificati a mano dall'admin: se presenti, si usano.
            _db_urls = {
                c.url for c in ordered_candidates if c.title.startswith("[DB]")
            }
            # Pass 1: priorità assoluta ai manuali DB preapprovati.
            _db_entries = [e for e in producer_scored if e[2] in _db_urls]
            if _db_entries:
                # Preferisci specifico (brand+model in titolo) vs categoria
                def _db_priority(entry):
                    url = entry[2]
                    cand = next((c for c in ordered_candidates if c.url == url), None)
                    if cand is None:
                        return 0
                    title = cand.title.lower()
                    specific = brand.lower() in title and model.lower() in title
                    return (2 if specific else 1, entry[0])
                _db_entries.sort(key=_db_priority, reverse=True)
                best = _db_entries[0]
            for entry in (producer_scored if best is None else []):
                score, pdf_data, url, rel_score, pages = entry
                short_url = url[-60:]
                # Accetta PDF lunghi anche se scansionati (score=0): sono documenti reali
                if pages >= SCANNED_PAGES_THRESHOLD:
                    best = entry
                    break
                # Accetta PDF con testo e abbastanza pagine
                if pages >= MIN_MANUAL_PAGES and score >= LOW_QUALITY_THRESHOLD:
                    best = entry
                    break
                # Accetta PDF corti ma con alto contenuto sicurezza
                if pages < MIN_MANUAL_PAGES and score >= 40:
                    best = entry
                    break
                rejection_reasons.append(f"{pages}pp score={score} ({short_url})")

            if best is None:
                best_pages = producer_scored[0][4]
                best_score_val = producer_scored[0][0]
                reasons_str = "; ".join(rejection_reasons[:3])
                producer_scored = []  # forza fallback AI
                _brochure_note = (
                    f"PDF scartato: {best_pages} pag., score {best_score_val}/100 "
                    f"(brochure/datasheet). Dettagli: {reasons_str}. Procedo con analisi AI."
                )
            else:
                _brochure_note = None
                best_score, producer_bytes, producer_url, _, producer_pages = best

        # Classifica il PDF produttore selezionato: exact | category | unrelated
        if producer_bytes:
            # Riconosci risultati dal DB Supabase (titolo inizia con "[DB]")
            _producer_from_db = producer_url and any(
                c.url == producer_url and c.title.startswith("[DB]")
                for c in ordered_candidates
            )
            if _producer_from_db:
                # Manuali DB verificati da ispettori: skip classify, label dedicata.
                # Distingue tra:
                #   - Manuale specifico: brand+model combaciano con quelli cercati
                #   - Manuale di categoria: brand/model GENERICO o diversi da quelli cercati
                _db_candidate = next(
                    (c for c in ordered_candidates if c.url == producer_url and c.title.startswith("[DB]")),
                    None,
                )
                _is_db_generic = _db_candidate and "generico" in _db_candidate.title.lower()
                _db_title_lower = (_db_candidate.title.lower() if _db_candidate else "")
                _brand_in_title = brand.lower() in _db_title_lower
                _model_in_title = model.lower() in _db_title_lower
                _is_db_exact_match = _brand_in_title and _model_in_title

                if _is_db_generic:
                    producer_source_label = f"Manuale DB — categoria {machine_type or 'macchina'}"
                    producer_match_type = "category"
                elif _is_db_exact_match:
                    producer_source_label = f"Manuale DB {brand} {model}"
                    producer_match_type = "exact"
                else:
                    producer_source_label = f"Manuale DB categoria simile ({machine_type or 'macchina'})"
                    producer_match_type = "category"
            else:
                producer_match_type = pdf_service.classify_pdf_match(
                    producer_bytes, brand, model, machine_type or ""
                )
                if producer_match_type == "category":
                    producer_source_label = f"Manuale categoria simile ({machine_type or 'macchina'})"
                elif producer_match_type == "unrelated":
                    producer_bytes = None
                    producer_source_label = "AI"
                    _brochure_note = (
                        f"PDF scartato: non pertinente per {machine_type or brand} "
                        "(documento di categoria diversa). Procedo con analisi AI."
                    )

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
            n_tried = _producer_scored_count
            safety_score = producer_scored[0][0] if producer_scored else 0
            quality_label = "" if safety_score >= LOW_QUALITY_THRESHOLD else " ⚠ bassa pertinenza"
            match_label = "" if producer_match_type == "exact" else " ⚠ categoria simile"
            parts_ok.append(
                f"produttore ({producer_pages} pag., "
                f"selezionato tra {n_tried} — sicurezza: {safety_score}/100{quality_label}{match_label})"
            )

        n_pdf_found = len(pdf_candidates)
        n_downloaded = _producer_scored_count + (1 if inail_bytes else 0)

        if not parts_ok and _brochure_note:
            dl_msg = _brochure_note
        elif parts_ok:
            dl_msg = f"Scaricati: {', '.join(parts_ok)}."
        elif n_pdf_found > 0 and n_downloaded == 0:
            dl_msg = f"Trovati {n_pdf_found} PDF ma nessuno scaricabile (timeout o accesso negato). Procedo con analisi AI."
        elif n_pdf_found > 0 and n_downloaded > 0:
            dl_msg = f"Trovati {n_pdf_found} PDF, {n_downloaded} scaricati ma tutti scartati (score troppo basso o non pertinenti). Procedo con analisi AI."
        else:
            dl_msg = "Nessun PDF trovato nella ricerca. Procedo con analisi AI."

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
            datasheet_bytes=datasheet_bytes, datasheet_url=datasheet_url,
            machine_year=machine_year,
            machine_type=machine_type,
            machine_type_id=machine_type_id,
            is_ante_ce=is_ante_ce,
            is_allegato_v=is_allegato_v,
            norme=norme,
            producer_source_label=producer_source_label,
            workplace_context=getattr(request, "workplace_context", None),
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

    # ── Inietta vita utile e hazard intelligence dal catalogo machine_types ──
    if machine_type_id:
        from app.services import machine_type_service as _mt_svc
        _all_types = {t["id"]: t for t in _mt_svc.get_all_types()}
        _mt = _all_types.get(machine_type_id)
        if _mt:
            safety_card.vita_utile_anni = _mt.get("vita_utile_anni")
        _hazard = _mt_svc.get_hazard(machine_type_id)
        if _hazard:
            safety_card.focus_rischi_categoria = _hazard.get("focus_testo")
            safety_card.categoria_inail = _hazard.get("categoria_inail")

    # ── Quality logging (non-blocking, non solleva eccezioni) ─────────────
    quality_service.log_analysis(
        brand=brand, model=model, machine_type=machine_type,
        safety_card=safety_card,
        producer_match_type=producer_match_type,
        producer_pages=producer_pages,
        inail_url=inail_url,
        producer_url=producer_url,
    )

    # ── Scan log: storico letture targa per batch e analytics ──────────────
    from app.services import scan_log_service
    _scan_id = scan_log_service.log_scan(
        brand=brand, model=model,
        machine_type=machine_type,
        machine_type_id=machine_type_id,
        serial_number=serial_number,
        machine_year=machine_year,
        norme=norme,
        qr_urls=qr_urls,
        inail_url=inail_url,
        producer_url=producer_url,
        producer_pages=producer_pages,
        fonte_tipo=getattr(safety_card, "fonte_tipo", None),
        is_ante_ce=is_ante_ce,
        is_allegato_v=is_allegato_v,
        safety_alerts_count=len(safety_alerts_data),
        session_id=getattr(request, "session_id", None),
    )
    # Salva foto etichetta compressa (max 800px JPEG q=65, ~60-100KB, conservata 30gg)
    if _scan_id and request.image_base64:
        scan_log_service.store_scan_image(_scan_id, request.image_base64)

    yield _sse(SSEEvent(step="analysis", status="completed", progress=90, message="Scheda generata."))

    # ── COMPLETE ──────────────────────��──────────────────────────────────
    yield _sse(SSEEvent(
        step="complete", status="completed", progress=100,
        message="Analisi completata.",
        data={"safety_card": safety_card.model_dump()},
    ))


@router.get("/infer-machine-type")
async def infer_machine_type(brand: str, model: str, hint: str = ""):
    """
    Determina il tipo di macchina da brand+modello tramite AI.
    Chiamato dal frontend quando l'utente corregge marca/modello nel form OCR.
    Parametri:
      brand  — marca corretta dall'utente
      model  — modello corretto dall'utente
      hint   — tipo estratto dall'OCR (opzionale, può essere vuoto)
    """
    from app.services import vision_service
    from app.config import settings

    provider = settings.get_vision_provider()
    machine_type = await vision_service._infer_machine_type(
        brand=brand,
        model=model,
        provider=provider,
        ocr_hint=hint.strip() or None,
    )
    return {"machine_type": machine_type}


@router.get("/quality-log")
async def get_quality_log(
    only_issues: bool = False,
    severity: str = "low",
    summary_only: bool = False,
    report: bool = False,
):
    """
    Log di qualità delle analisi accumulate in questa sessione del server.
    Parametri:
      only_issues=true   → mostra solo analisi con almeno un issue
      severity=medium    → mostra solo issue di severità >= medium/high
      summary_only=true  → solo statistiche aggregate, nessun dettaglio
      report=true        → genera analisi critica AI con suggerimenti miglioramento
                           (~$0.0003, chiamare manualmente quando il log è popolato)
    """
    if report:
        return await quality_service.generate_improvement_report()
    if summary_only:
        return quality_service.get_summary()
    return {
        "summary": quality_service.get_summary(),
        "entries": quality_service.get_log(only_with_issues=only_issues, min_severity=severity),
    }


@router.get("/debug-search")
async def debug_search(brand: str = "Doosan", model: str = "D20NXP", machine_type: str = "carrello elevatore"):
    """
    Endpoint di diagnostica: testa local INAIL lookup + DuckDuckGo search.
    Non usare in produzione per utenti reali.
    """
    import os
    from app.services import local_manuals_service, search_service
    from app.config import settings

    # 1. Test percorso PDF locali
    pdf_dir = local_manuals_service.PDF_MANUALS_DIR
    pdf_dir_exists = pdf_dir.exists()
    pdf_files = list(pdf_dir.glob("*.pdf")) if pdf_dir_exists else []

    # 2. Test find_local_manual
    local_result = local_manuals_service.find_local_manual(machine_type)

    # 3. Test DuckDuckGo search
    ddg_results = []
    ddg_error = None
    try:
        from duckduckgo_search import DDGS
        import asyncio
        loop = asyncio.get_event_loop()
        hits = await loop.run_in_executor(None, lambda: list(DDGS().text(f"{brand} {model} manual pdf", max_results=5, safesearch="off")))
        ddg_results = [{"title": h.get("title"), "url": h.get("href")} for h in hits]
    except Exception as e:
        ddg_error = f"{type(e).__name__}: {e}"

    # 4. Test provider configurato
    provider = settings.get_search_provider()

    return {
        "pdf_dir": str(pdf_dir),
        "pdf_dir_exists": pdf_dir_exists,
        "pdf_files_count": len(pdf_files),
        "pdf_files": [f.name for f in pdf_files[:5]],
        "local_manual_found": local_result,
        "search_provider": provider,
        "ddg_results": ddg_results,
        "ddg_error": ddg_error,
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
