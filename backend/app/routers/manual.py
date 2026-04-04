from fastapi import APIRouter, Query, Request
from typing import List
from app.services import search_service
from app.models.responses import ManualSearchResult

router = APIRouter()


@router.get("/search", response_model=List[ManualSearchResult])
async def search_manual(
    request: Request,
    brand: str = Query(..., description="Marca del macchinario"),
    model: str = Query(..., description="Modello del macchinario"),
    lang: str = Query("it", description="Lingua preferita: it|en"),
):
    """
    Cerca il manuale online per marca e modello.
    Utile per una nuova ricerca senza dover ricaricare la foto.
    """
    results = await search_service.search_manual(brand, model, lang)
    return results
