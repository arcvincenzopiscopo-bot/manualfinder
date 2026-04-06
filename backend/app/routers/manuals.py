"""
Router per servire i manuali locali INAIL, gestire i manuali salvati su Supabase
e gestire l'upload di nuovi manuali PDF da parte degli ispettori.
"""
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import List, Optional
from app.services import local_manuals_service, saved_manuals_service, upload_service
from app.models.requests import SaveManualRequest

router = APIRouter()


@router.get("/local")
async def get_local_manuals(machine_type: Optional[str] = Query(None, description="Tipo di macchina per filtrare")) -> List[dict]:
    """Restituisce la lista di tutti i manuali locali disponibili, o filtra per tipo macchina."""
    if machine_type:
        manual = local_manuals_service.find_local_manual(machine_type)
        if manual:
            return [manual]
        return []
    return local_manuals_service.list_local_manuals()


@router.get("/local/file/{filename}")
async def get_local_manual_file(filename: str):
    """Scarica un manuale locale specifico."""
    filepath = local_manuals_service.PDF_MANUALS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"File non trovato: {filename}")
    
    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/pdf",
    )


# ── Manuali salvati su Supabase ───────────────────────────────────────────────

@router.post("/save")
async def save_manual(body: SaveManualRequest):
    """Salva un link manuale confermato dall'ispettore su Supabase."""
    try:
        data = body.model_dump(exclude_none=True)
        result = saved_manuals_service.save_manual(data)
        # Converti UUID e datetime in stringhe per la serializzazione JSON
        result["id"] = str(result["id"])
        result["created_at"] = str(result["created_at"])
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore salvataggio: {e}")


@router.get("/saved")
async def get_saved_manuals(
    machine_type: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=100),
):
    """Cerca manuali salvati per tipo macchina, brand o modello."""
    try:
        results = saved_manuals_service.search_saved(
            machine_type=machine_type,
            brand=brand,
            model=model,
            limit=limit,
        )
        for r in results:
            r["id"] = str(r["id"])
            r["created_at"] = str(r["created_at"])
        return results
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore ricerca: {e}")


# ── Upload manuali PDF da ispettori ──────────────────────────────────────────

@router.post("/upload")
async def upload_manual(
    file: UploadFile = File(...),
    brand: str = Form(...),
    model: str = Form(...),
    machine_type: str = Form(...),
    manual_year: Optional[str] = Form(None),
    manual_language: str = Form("it"),
    is_generic: bool = Form(False),
    notes: Optional[str] = Form(None),
    force: bool = Form(False),  # se True salta il check AI (già confermato dal frontend)
):
    """
    Carica un manuale PDF fornito dall'ispettore.
    Valida che sia un PDF nativo (non scansione), verifica congruenza con AI,
    salva in manuali_locali/ e registra su Supabase.
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

    # 6) Salva file + Supabase
    try:
        result = upload_service.save_uploaded_pdf(
            pdf_bytes=pdf_bytes,
            brand=brand,
            model=model,
            machine_type=machine_type,
            manual_year=manual_year,
            manual_language=manual_language,
            is_generic=is_generic,
            notes=notes,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore salvataggio: {e}")

    return {"status": "ok", "filename": result["filename"], "url": result["url"]}


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
