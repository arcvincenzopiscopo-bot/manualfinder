"""
Router per servire i manuali locali INAIL e gestire i manuali salvati su Supabase.
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from typing import List, Optional
from app.services import local_manuals_service, saved_manuals_service
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
