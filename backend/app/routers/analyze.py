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

# URL QR — ora in DB (config_lists:"qr_service_patterns"). Fallback statico.
_FB_QR_SERVICE_PATTERNS = {
    "service/scan", "/scan?", "/aftersales", "/support/scan",
    "cat.com/service", "komatsu.com/scan", "/qrcode/", "/qr?",
    "parts.cat.com", "sos.cat.com",
}


def _qr_patterns() -> set:
    from app.services.config_service import get_list
    return get_list("qr_service_patterns", _FB_QR_SERVICE_PATTERNS)


def _filter_qr_urls(urls: list[str]) -> list[str]:
    """Scarta URL QR che puntano a portali-servizio invece che a documenti."""
    patterns = _qr_patterns()
    return [u for u in urls if not any(p in u.lower() for p in patterns)]


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


async def _pipeline(request: FullAnalysisRequest, http_request: Optional[Request] = None):
    """
    Generatore SSE: search → download → analisi. OCR già fatto dal frontend.
    Orchestratore snello: le fasi pesanti sono delegate a pipeline/search_phase.py
    e pipeline/download_phase.py.
    """
    from app.services.pipeline.search_phase import (
        compute_year_flags,
        build_search_start_message,
        run_search_phase,
    )
    from app.services.pipeline.download_phase import run_download_phase, DownloadPhaseResult
    from app.services.config_service import get_debug_mode

    # ── Debug overlay ─────────────────────────────────────────────────────────
    _debug_enabled = get_debug_mode()
    _debug_buf: list[SSEEvent] = []

    def _emit_debug(category: str, level: str, message: str, details: dict = {}) -> None:
        _debug_buf.append(SSEEvent(
            step="debug", status=level, message=message,
            data={"category": category, **details},
        ))

    _dbg = _emit_debug if _debug_enabled else None

    async def _flush_debug():
        for ev in _debug_buf:
            yield _sse(ev)
        _debug_buf.clear()

    async def _client_gone() -> bool:
        if http_request is None:
            return False
        return await http_request.is_disconnected()

    # ── Parsing request ──────────────────────────────────────────────────
    brand = request.brand.strip()
    model = request.model.strip()
    if not brand and not model:
        yield _sse(SSEEvent(type="error", message="Brand e modello mancanti. Ripetere la scansione della targa."))
        return

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
    qr_url = qr_urls[0] if qr_urls else None

    # ── PRE-CHECK: Manuale INAIL locale ─────────────────────────────────
    # Verifica prima della ricerca se esiste un manuale INAIL locale per questo tipo
    # macchina. Se sì, la ricerca INAIL online (livelli 1-2) viene saltata.
    from app.services.local_manuals_service import find_local_manual as _find_local_manual
    _local_inail: Optional[dict] = None
    if machine_type or machine_type_id:
        try:
            _local_inail = _find_local_manual(
                machine_type=machine_type or "",
                machine_type_id=machine_type_id,
            )
        except Exception:
            _local_inail = None
    has_local_inail: bool = _local_inail is not None

    # ── STEP 1: Ricerca ──────────────────────────────────────────────────
    if await _client_gone():
        return

    is_ante_ce, is_allegato_v = compute_year_flags(machine_year)
    yield _sse(SSEEvent(
        step="search", status="started", progress=10,
        message=build_search_start_message(brand, model, machine_type, machine_year, is_ante_ce, is_allegato_v),
    ))
    await asyncio.sleep(0)

    sr = await run_search_phase(
        brand=brand, model=model,
        machine_type=machine_type, machine_type_id=machine_type_id,
        machine_year=machine_year, serial_number=serial_number,
        preferred_language=request.preferred_language,
        has_local_inail=has_local_inail,
        qr_url=qr_url,
        debug_callback=_dbg,
    )

    yield _sse(SSEEvent(
        step="search", status="completed", progress=35,
        message=sr.search_message if sr.search_results else "Nessun manuale trovato online. Procedo con analisi AI.",
        data={
            "results": [r.model_dump() for r in sr.search_results[:5]],
            "found": bool(sr.search_results),
            "local_manual": sr.local_manual_found,
            "safety_alerts": sr.safety_alerts_data,
            "debug_warnings": sr.search_warnings,
        },
    ))
    async for ev in _flush_debug():
        yield ev

    # ── STEP 2: Download PDF ─────────────────────────────────────────────
    if await _client_gone():
        return

    if sr.pdf_candidates or (has_local_inail and _local_inail):
        # Messaggio "started": stima veloce i tipi di fonte disponibili
        _dl_parts: list[str] = []
        if has_local_inail or any(r.source_type == "inail" for r in sr.pdf_candidates):
            _dl_parts.append("scheda INAIL")
        if any(r.source_type not in ("inail", "datasheet", "supplemental") for r in sr.pdf_candidates):
            _dl_parts.append("manuale produttore")
        yield _sse(SSEEvent(
            step="download", status="started", progress=40,
            message=f"Download {' + '.join(_dl_parts)} in corso..." if _dl_parts else "Download PDF in corso...",
        ))

        dr = await run_download_phase(
            brand=brand, model=model,
            machine_type=machine_type, machine_type_id=machine_type_id,
            pdf_candidates=sr.pdf_candidates,
            qr_urls=qr_urls,
            has_local_inail=has_local_inail,
            local_inail=_local_inail,
            analysis_provider=settings.get_analysis_provider(),
            debug_callback=_dbg,
        )

        yield _sse(SSEEvent(
            step="download", status="completed", progress=60,
            message=dr.dl_message,
            data={"inail_url": dr.inail_url, "producer_url": dr.producer_url,
                  "producer_pages": dr.producer_pages},
        ))
        async for ev in _flush_debug():
            yield ev
    else:
        dr = DownloadPhaseResult()
        yield _sse(SSEEvent(
            step="download", status="completed", progress=60,
            message="Nessun PDF disponibile. Analisi basata su conoscenza AI.",
            data={"inail_url": None, "producer_url": None, "producer_pages": 0},
        ))
        if _dbg:
            _dbg("download", "warning", "Nessun candidato PDF — analisi basata su sola conoscenza AI", {})
        async for ev in _flush_debug():
            yield ev

    # ── STEP 3: Analisi Sicurezza ────────────────────────────────────────
    if await _client_gone():
        return

    has_both = dr.inail_bytes and dr.producer_bytes
    if has_both:
        match_note = "" if dr.producer_match_type == "exact" else " (categoria simile)"
        analysis_msg = f"Analisi combinata INAIL + manuale produttore{match_note}..."
    elif dr.inail_bytes:
        analysis_msg = f"Analisi scheda INAIL ({pdf_service.count_pdf_pages(dr.inail_bytes)} pag.)..."
    elif dr.producer_bytes:
        match_note = "" if dr.producer_match_type == "exact" else " (categoria simile)"
        analysis_msg = f"Analisi manuale produttore{match_note} ({dr.producer_pages} pag.)..."
    else:
        analysis_msg = "Generazione scheda sicurezza dalla conoscenza AI..."

    yield _sse(SSEEvent(step="analysis", status="started", progress=65, message=analysis_msg))

    # Coda SSE per i sub-eventi di avanzamento emessi durante l'analisi AI.
    # generate_safety_card() gira come task separato; il generatore SSE drena la
    # coda ogni 300ms in modo da streamare i messaggi in tempo reale al browser.
    _sub_queue: asyncio.Queue = asyncio.Queue()

    async def _emit_sub(message: str, sub_progress: int = 70) -> None:
        await _sub_queue.put(_sse(SSEEvent(
            step="analysis", status="info",
            progress=sub_progress, message=message,
        )))

    _ai_debug_info: dict = {}
    _analysis_task = asyncio.create_task(
        analysis_service.generate_safety_card(
            brand=brand, model=model,
            inail_bytes=dr.inail_bytes, inail_url=dr.inail_url,
            producer_bytes=dr.producer_bytes, producer_url=dr.producer_url,
            producer_page_count=dr.producer_pages,
            datasheet_bytes=dr.datasheet_bytes, datasheet_url=dr.datasheet_url,
            machine_year=machine_year,
            machine_type=machine_type,
            machine_type_id=machine_type_id,
            is_ante_ce=is_ante_ce,
            is_allegato_v=is_allegato_v,
            norme=norme,
            producer_source_label=dr.producer_source_label,
            workplace_context=getattr(request, "workplace_context", None),
            similar_category_local=dr.similar_category_used,
            supplemental_bytes=dr.supplemental_bytes,
            supplemental_url=dr.supplemental_url,
            supplemental_label=dr.supplemental_label,
            debug_info=_ai_debug_info if _debug_enabled else None,
            progress_fn=_emit_sub,
        )
    )

    # Drena la coda mentre il task gira: ogni 300ms yield gli eventi accumulati
    try:
        while not _analysis_task.done():
            while not _sub_queue.empty():
                yield _sub_queue.get_nowait()
            await asyncio.sleep(0.3)
        # Drena eventuali messaggi finali rimasti in coda
        while not _sub_queue.empty():
            yield _sub_queue.get_nowait()
        safety_card = await _analysis_task  # propaga eccezioni se il task è fallito
    except Exception as e:
        if _dbg:
            _dbg("analysis", "error", f"Errore analisi: {e}", {"error": str(e)})
        async for ev in _flush_debug():
            yield ev
        yield _sse(SSEEvent(
            step="analysis", status="failed", progress=65,
            message=f"Errore analisi: {str(e)}", data={"error": str(e)},
        ))
        return

    if _dbg and _ai_debug_info:
        _dbg("ai", "info",
            f"AI: {_ai_debug_info.get('provider','?')} — {_ai_debug_info.get('model','?')} "
            f"[{_ai_debug_info.get('task_type','?')}] metodo={_ai_debug_info.get('method','text')}",
            _ai_debug_info
        )
    async for ev in _flush_debug():
        yield ev

    # Aggiungi alert Safety Gate alla scheda
    if sr.safety_alerts_data:
        safety_card.safety_alerts = sr.safety_alerts_data

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

    # ── Quality logging (non-blocking) ────────────────────────────────────
    quality_service.log_analysis(
        brand=brand, model=model, machine_type=machine_type,
        safety_card=safety_card,
        producer_match_type=dr.producer_match_type,
        producer_pages=dr.producer_pages,
        inail_url=dr.inail_url,
        producer_url=dr.producer_url,
    )

    # ── Scan log ─────────────────────────────────────────────────────────
    from app.services import scan_log_service
    _scan_id = scan_log_service.log_scan(
        brand=brand, model=model,
        machine_type=machine_type, machine_type_id=machine_type_id,
        serial_number=serial_number, machine_year=machine_year,
        norme=norme, qr_urls=qr_urls,
        inail_url=dr.inail_url, producer_url=dr.producer_url,
        producer_pages=dr.producer_pages,
        fonte_tipo=getattr(safety_card, "fonte_tipo", None),
        is_ante_ce=is_ante_ce, is_allegato_v=is_allegato_v,
        safety_alerts_count=len(sr.safety_alerts_data),
        session_id=getattr(request, "session_id", None),
    )
    if _scan_id and request.image_base64:
        scan_log_service.store_scan_image(_scan_id, request.image_base64)

    yield _sse(SSEEvent(step="analysis", status="completed", progress=90, message="Scheda generata."))

    # ── COMPLETE ──────────────────────────────────────────────────────────
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
        _pipeline(body, http_request=request),
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
