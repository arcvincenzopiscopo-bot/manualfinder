"""
Router per servire i manuali locali INAIL.
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from typing import List, Optional
from app.services import local_manuals_service

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
