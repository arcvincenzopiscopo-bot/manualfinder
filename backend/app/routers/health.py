from fastapi import APIRouter
from datetime import datetime
from app.config import settings

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "providers": {
            "vision": settings.get_vision_provider(),
            "search": settings.get_search_provider(),
            "analysis": settings.get_analysis_provider(),
        },
    }
