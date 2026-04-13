"""
Router per servire i manuali locali INAIL, gestire i manuali salvati su Supabase
e gestire l'upload di nuovi manuali PDF da parte degli ispettori.
"""
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import List, Optional
from app.services import local_manuals_service, saved_manuals_service, upload_service
from app.services import feedback_analyzer_service
from app.models.requests import SaveManualRequest
from app.utils.errors import internal_error, service_unavailable

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/local")
async def get_local_manuals(
    machine_type: Optional[str] = Query(None, description="Tipo di macchina per filtrare"),
    machine_type_id: Optional[int] = Query(None, description="ID tipo macchina (prioritario su machine_type)"),
) -> List[dict]:
    """Restituisce la lista di tutti i manuali locali disponibili, o filtra per tipo macchina."""
    if machine_type_id is not None or machine_type:
        manual = local_manuals_service.find_local_manual(
            machine_type=machine_type or "",
            machine_type_id=machine_type_id,
        )
        if manual:
            return [manual]
        return []
    return local_manuals_service.list_local_manuals()


@router.get("/local/file/{filename}")
async def get_local_manual_file(filename: str):
    """Scarica un manuale locale specifico."""
    import re as _re
    if not _re.match(r'^[\w\-. ]+\.pdf$', filename, _re.IGNORECASE):
        raise HTTPException(status_code=400, detail="Nome file non valido.")
    base_dir = local_manuals_service.PDF_MANUALS_DIR.resolve()
    filepath = (base_dir / filename).resolve()
    # Path traversal guard: il percorso risolto deve restare dentro base_dir
    try:
        filepath.relative_to(base_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="Percorso non consentito.")
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail=f"File non trovato: {filename}")

    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/pdf",
    )


# ── Manuali salvati su Supabase ───────────────────────────────────────────────

@router.get("/check-url")
async def check_url_saved(url: str = Query(..., description="URL del PDF da verificare")):
    """Verifica se un URL è già presente nel database dei manuali salvati."""
    already_saved = saved_manuals_service.check_url_saved(url)
    return {"url": url, "already_saved": already_saved}


@router.post("/feedback")
async def submit_feedback(
    url: str = Form(...),
    feedback_type: str = Form(...),   # 'not_a_manual' | 'wrong_category' | 'useful_other_category'
    brand: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    machine_type: Optional[str] = Form(None),
    machine_type_id: Optional[int] = Form(None),
    useful_for_type: Optional[str] = Form(None),
    useful_for_type_id: Optional[int] = Form(None),
    notes: Optional[str] = Form(None),
):
    """
    Raccoglie il feedback dell'ispettore su un documento trovato.
    Tipi:
      not_a_manual         — non è un manuale d'uso (brochure, catalogo, scheda tecnica, ecc.)
      wrong_category       — è un manuale ma per un tipo di macchina diverso da quello cercato
      useful_other_category— manuale utile per un altro tipo macchina (specificare in useful_for_type)
    """
    # Auto-resolve ID se non forniti
    try:
        from app.services.machine_type_service import resolve_machine_type_id as _resolve
        if machine_type_id is None and machine_type:
            machine_type_id = _resolve(machine_type)
        if useful_for_type_id is None and useful_for_type:
            useful_for_type_id = _resolve(useful_for_type)
    except Exception:
        pass
    saved_manuals_service.save_feedback(
        url=url,
        feedback_type=feedback_type,
        brand=brand,
        model=model,
        machine_type=machine_type,
        machine_type_id=machine_type_id,
        useful_for_type=useful_for_type,
        useful_for_type_id=useful_for_type_id,
        notes=notes,
    )

    # Se l'URL è segnalato come non-manuale: rimuovilo da saved_manuals e invalida la cache
    if feedback_type == "not_a_manual" and url:
        try:
            saved_manuals_service.delete_manual_by_url(url)
        except Exception:
            pass
        try:
            from app.services.cache_service import search_cache
            search_cache.evict_containing_url(url)
        except Exception:
            pass

    # Auto-trigger analisi ogni 5 nuovi feedback non ancora processati
    try:
        unanalyzed = saved_manuals_service.count_unanalyzed_feedback()
        if unanalyzed >= 5:
            from app.config import settings as _settings
            asyncio.create_task(
                feedback_analyzer_service.run_analysis(_settings.get_analysis_provider())
            )
    except Exception:
        pass

    return {"status": "ok"}


@router.get("/feedback")
async def get_feedback(
    feedback_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """
    [Admin] Restituisce i feedback raccolti dagli ispettori.
    Utile per identificare URL da aggiungere a _PDF_EXCLUDE_TERMS o BROCHURE_SIGNALS.
    """
    if not saved_manuals_service.settings.database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL non configurata")
    try:
        import psycopg2.extras
        conditions = []
        params: list = []
        if feedback_type:
            conditions.append("feedback_type = %s")
            params.append(feedback_type)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM manual_feedback {where} ORDER BY ts DESC LIMIT %s"
        params.append(limit)
        with saved_manuals_service._get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            r["id"] = str(r["id"])
            r["ts"] = str(r["ts"])
        return {"count": len(rows), "entries": rows}
    except Exception as e:
        raise internal_error(logger, e, context="list feedback")


@router.post("/feedback/analyze")
async def analyze_feedback():
    """
    [Admin] Trigger manuale: analizza tutti i feedback in sospeso e crea/aggiorna
    le regole di filtraggio URL in url_filter_rules.
    """
    from app.config import settings as _settings
    provider = _settings.get_analysis_provider()
    try:
        result = await feedback_analyzer_service.run_analysis(provider)
        return result
    except Exception as e:
        raise internal_error(logger, e, context="analyze feedback")


@router.get("/feedback/rules")
async def get_filter_rules(limit: int = Query(100, ge=1, le=500)):
    """
    [Admin] Lista regole di filtraggio URL attive estratte dai feedback ispettori.
    """
    if not saved_manuals_service.settings.database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL non configurata")
    try:
        import psycopg2.extras
        with saved_manuals_service._get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, rule_type, rule_value, context_machine_type_id,
                           reason, feedback_count, source_urls, is_active, created_at
                    FROM url_filter_rules
                    ORDER BY feedback_count DESC, created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            r["id"] = str(r["id"])
            r["created_at"] = str(r["created_at"])
        return {"count": len(rows), "rules": rows}
    except Exception as e:
        raise internal_error(logger, e, context="get filter rules")


@router.post("/save")
async def save_manual(body: SaveManualRequest):
    """Salva un link manuale confermato dall'ispettore su Supabase."""
    try:
        data = body.model_dump(exclude_none=True)
        # Auto-resolve machine_type_id dal testo se non fornito
        try:
            from app.services.machine_type_service import resolve_machine_type_id
            if data.get("machine_type_id") is None and data.get("manual_machine_type"):
                resolved = resolve_machine_type_id(data["manual_machine_type"])
                if resolved:
                    data["machine_type_id"] = resolved
            if data.get("search_machine_type_id") is None and data.get("search_machine_type"):
                resolved = resolve_machine_type_id(data["search_machine_type"])
                if resolved:
                    data["search_machine_type_id"] = resolved
        except Exception:
            pass
        result = saved_manuals_service.save_manual(data)
        # Converti UUID e datetime in stringhe per la serializzazione JSON
        result["id"] = str(result["id"])
        result["created_at"] = str(result["created_at"])
        return result
    except RuntimeError as e:
        raise service_unavailable(logger, e, context="save manual")
    except Exception as e:
        raise internal_error(logger, e, context="save manual")


@router.get("/saved")
async def get_saved_manuals(
    machine_type: Optional[str] = Query(None),
    machine_type_id: Optional[int] = Query(None),
    brand: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=100),
):
    """Cerca manuali salvati per tipo macchina, brand o modello."""
    try:
        results = saved_manuals_service.search_saved(
            machine_type=machine_type,
            machine_type_id=machine_type_id,
            brand=brand,
            model=model,
            limit=limit,
        )
        for r in results:
            r["id"] = str(r["id"])
            r["created_at"] = str(r["created_at"])
        return results
    except RuntimeError as e:
        raise service_unavailable(logger, e, context="search saved manuals")
    except Exception as e:
        raise internal_error(logger, e, context="search saved manuals")


# ── Upload manuali PDF da ispettori ──────────────────────────────────────────

@router.post("/upload")
async def upload_manual(
    file: UploadFile = File(...),
    brand: str = Form(...),
    model: str = Form(...),
    machine_type: str = Form(...),
    machine_type_id: Optional[int] = Form(None),
    manual_year: Optional[str] = Form(None),
    manual_language: str = Form("it"),
    is_generic: bool = Form(False),
    notes: Optional[str] = Form(None),
    force: bool = Form(False),  # se True salta il check AI (già confermato dal frontend)
):
    """
    Carica un manuale PDF fornito dall'ispettore.
    Valida che sia un PDF nativo (non scansione), verifica congruenza con AI,
    salva in manuali_locali/ + Supabase Storage (se configurato) e registra su Supabase DB.
    """
    from app.config import settings
    from app.services.pdf_service import is_native_pdf

    # 1) Leggi file
    pdf_bytes = await file.read()

    # 2) Valida firma PDF
    if not pdf_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Il file caricato non è un PDF valido.")

    # 3) Controlla dimensione
    max_bytes = settings.max_pdf_size_mb * 1024 * 1024
    if len(pdf_bytes) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File troppo grande (max {settings.max_pdf_size_mb} MB)."
        )

    # 4) Controlla che sia PDF nativo (non scansione)
    native, cpp = is_native_pdf(pdf_bytes)
    if not native:
        raise HTTPException(
            status_code=400,
            detail=(
                f"PDF non supportato: contiene solo immagini scansionate "
                f"({cpp:.0f} caratteri/pagina, minimo richiesto 100). "
                "Caricare solo PDF con testo nativo selezionabile."
            )
        )

    # 5) Check AI congruenza (solo se non force)
    if not force:
        provider = settings.get_analysis_provider()
        check = await upload_service.validate_and_check(
            pdf_bytes, brand, model, machine_type, provider
        )
        if not check.get("ok", True):
            return {
                "status": "mismatch",
                "suggestions": {
                    "brand": check.get("suggested_brand", brand),
                    "model": check.get("suggested_model", model),
                    "machine_type": check.get("suggested_machine_type", machine_type),
                    "reason": check.get("reason", ""),
                },
            }

    # 5b) Comprimi una volta sola per riutilizzare sia per Storage che per filesystem
    compressed_bytes = upload_service._compress_pdf(pdf_bytes)
    filename = upload_service._sanitize_filename(brand, model, machine_type)

    # 6) Carica su Supabase Storage (se configurato) — URL persistente che sopravvive ai redeploy
    storage_url = await upload_service._upload_to_supabase_storage(compressed_bytes, filename)

    # 7) Salva file su filesystem locale + registra su Supabase DB
    try:
        result = upload_service.save_uploaded_pdf(
            pdf_bytes=pdf_bytes,
            brand=brand,
            model=model,
            machine_type=machine_type,
            machine_type_id=machine_type_id,
            manual_year=manual_year,
            manual_language=manual_language,
            is_generic=is_generic,
            notes=notes,
            _storage_url=storage_url,
            _precomputed_filename=filename,
            _precompressed_bytes=compressed_bytes,
        )
    except ValueError as e:
        # Messaggi di ValueError sono controllati e pensati per essere mostrati
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise internal_error(logger, e, context="save uploaded pdf")

    storage_warning = None
    if not storage_url:
        if settings.supabase_url and settings.supabase_service_key:
            storage_warning = (
                "Il PDF è stato salvato solo localmente (il caricamento su Supabase Storage è fallito). "
                f"Verifica che il bucket '{settings.supabase_storage_bucket}' esista e sia pubblico, "
                "e che SUPABASE_SERVICE_KEY sia la chiave service_role (non anon)."
            )
        else:
            storage_warning = (
                "SUPABASE_URL o SUPABASE_SERVICE_KEY non configurati: il PDF è salvato solo "
                "localmente e andrà perso al prossimo redeploy. "
                "Aggiungi le variabili d'ambiente su Render e ridistribuisci."
            )

    return {
        "status": "ok",
        "filename": result["filename"],
        "url": result["url"],
        "storage_persisted": storage_url is not None,
        "storage_warning": storage_warning,
    }


# ── Regole prompt per tipo macchina (admin) ──────────────────────────────────

@router.get("/prompt-rules")
async def get_prompt_rules(limit: int = Query(100, ge=1, le=500)):
    """[Admin] Lista regole prompt per tipo macchina da Supabase."""
    if not saved_manuals_service.settings.database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL non configurata")
    try:
        import psycopg2.extras
        with saved_manuals_service._get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM machine_prompt_rules ORDER BY machine_type LIMIT %s",
                    (limit,),
                )
                rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            r["id"] = str(r["id"])
            if r.get("updated_at"):
                r["updated_at"] = str(r["updated_at"])
        return {"count": len(rows), "rules": rows}
    except Exception as e:
        raise internal_error(logger, e, context="get prompt rules")


@router.post("/prompt-rules")
async def upsert_prompt_rule(body: dict):
    """
    [Admin] Crea o aggiorna una regola prompt per tipo macchina.
    Campi: machine_type (obbligatorio), extra_context, specific_risks,
           normative_refs, inspection_focus, is_active.
    """
    if not saved_manuals_service.settings.database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL non configurata")
    machine_type = body.get("machine_type", "").strip().lower()
    if not machine_type:
        raise HTTPException(status_code=400, detail="machine_type obbligatorio")
    mt_id = None
    try:
        from app.services.machine_type_service import resolve_machine_type_id as _resolve
        mt_id = _resolve(machine_type)
    except Exception:
        pass
    try:
        with saved_manuals_service._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO machine_prompt_rules
                        (machine_type, machine_type_id, extra_context, specific_risks, normative_refs,
                         inspection_focus, is_active, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (machine_type) DO UPDATE SET
                        machine_type_id  = COALESCE(EXCLUDED.machine_type_id,
                                                    machine_prompt_rules.machine_type_id),
                        extra_context    = EXCLUDED.extra_context,
                        specific_risks   = EXCLUDED.specific_risks,
                        normative_refs   = EXCLUDED.normative_refs,
                        inspection_focus = EXCLUDED.inspection_focus,
                        is_active        = EXCLUDED.is_active,
                        updated_at       = now()
                    """,
                    (
                        machine_type,
                        mt_id,
                        body.get("extra_context"),
                        body.get("specific_risks"),
                        body.get("normative_refs"),
                        body.get("inspection_focus"),
                        body.get("is_active", True),
                    ),
                )
            conn.commit()
        # Invalida cache per applicare immediatamente
        try:
            from app.services.prompt_rules_service import invalidate_cache
            invalidate_cache()
        except Exception:
            pass
        return {"status": "ok", "machine_type": machine_type}
    except Exception as e:
        raise internal_error(logger, e, context="upsert prompt rule")


@router.post("/prompt-rules/{machine_type}/improve")
async def improve_prompt_rule(machine_type: str):
    """
    [Admin] Migliora la regola prompt per un tipo macchina basandosi su quality_log
    e feedback ispettori. Trigger manuale — utile per aggiornare immediatamente
    dopo un ciclo di analisi o per tipi con problemi noti.
    """
    from app.config import settings as _s
    from app.services import prompt_optimizer_service
    provider = _s.get_analysis_provider()
    if provider == "none":
        raise HTTPException(status_code=503, detail="Provider AI non configurato")
    result = await prompt_optimizer_service.improve_single(machine_type, provider)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Nessun dato sufficiente per migliorare '{machine_type}' (servono ≥1 analisi in quality_log)"
        )
    return {
        "machine_type": machine_type,
        "changes_summary": result.get("quality_notes", "Regola aggiornata"),
        "updated_rule": {k: result.get(k) for k in ("extra_context", "specific_risks", "normative_refs", "inspection_focus")},
    }


@router.delete("/prompt-rules/{machine_type}")
async def delete_prompt_rule(machine_type: str):
    """[Admin] Disattiva una regola prompt (is_active = false)."""
    if not saved_manuals_service.settings.database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL non configurata")
    try:
        with saved_manuals_service._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE machine_prompt_rules SET is_active = false, updated_at = now() WHERE machine_type = %s",
                    (machine_type.strip().lower(),),
                )
                updated = cur.rowcount
            conn.commit()
        try:
            from app.services.prompt_rules_service import invalidate_cache
            invalidate_cache()
        except Exception:
            pass
        return {"status": "ok", "disabled": updated > 0}
    except Exception as e:
        raise internal_error(logger, e, context="delete prompt rule")


@router.get("/local/available-pdfs")
async def list_available_pdfs():
    """[Admin] Lista dei PDF presenti nella cartella manuali locali (per dropdown assegnazione)."""
    return local_manuals_service.list_all_pdf_files()


@router.get("/local/assignments")
async def list_inail_assignments():
    """[Admin] Lista assegnazioni quaderni INAIL (machine_type_id → pdf_filename)."""
    return local_manuals_service.list_inail_assignments()


@router.post("/local/assignments")
async def upsert_inail_assignment(body: dict):
    """
    [Admin] Crea o aggiorna assegnazione quaderno INAIL.
    Body: { machine_type_id: int, pdf_filename: str, display_title: str | null }
    """
    mt_id = body.get("machine_type_id")
    pdf = body.get("pdf_filename", "").strip()
    if not mt_id or not pdf:
        raise HTTPException(status_code=422, detail="machine_type_id e pdf_filename sono obbligatori")
    local_manuals_service.upsert_inail_assignment(
        machine_type_id=int(mt_id),
        pdf_filename=pdf,
        display_title=body.get("display_title"),
    )
    return {"ok": True}


@router.delete("/local/assignments/{machine_type_id}")
async def delete_inail_assignment(machine_type_id: int):
    """[Admin] Elimina assegnazione quaderno INAIL per un tipo macchina."""
    local_manuals_service.delete_inail_assignment(machine_type_id)
    return {"ok": True}


@router.get("/uploaded/{filename}")
async def get_uploaded_manual(filename: str):
    """Serve un PDF caricato dagli ispettori dalla cartella manuali_locali/."""
    # Sanitizza il filename (evita path traversal)
    import re as _re
    if not _re.match(r'^[\w\-. ]+\.pdf$', filename, _re.IGNORECASE):
        raise HTTPException(status_code=400, detail="Nome file non valido.")
    filepath = upload_service.UPLOAD_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"File non trovato: {filename}")
    return FileResponse(path=str(filepath), filename=filename, media_type="application/pdf")
