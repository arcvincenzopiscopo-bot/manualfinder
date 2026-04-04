from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.routers import analyze, manual, health, manuals
from app.config import settings

# Rate limiting
limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_minute}/minute"])

app = FastAPI(
    title="ManualFinder API",
    description="Identifica macchinari da cantiere e recupera i manuali di sicurezza",
    version="1.1.0",
)

app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allowed_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Troppe richieste. Attendi qualche secondo e riprova.",
            "retry_after": 60
        },
    )

app.include_router(health.router)
app.include_router(analyze.router, prefix="/analyze")
app.include_router(manual.router, prefix="/manual")
app.include_router(manuals.router, prefix="/manuals")


@app.on_event("startup")
async def on_startup():
    """Svuota la cache di ricerca ad ogni avvio — garantisce che le modifiche al codice siano attive."""
    from app.services.cache_service import search_cache
    if hasattr(search_cache, "_store"):
        search_cache._store.clear()
    elif hasattr(search_cache, "_fallback"):
        search_cache._fallback._store.clear()


@app.get("/admin/cache-clear")
async def cache_clear():
    """Svuota manualmente la cache di ricerca (utile dopo aggiornamenti del codice)."""
    from app.services.cache_service import search_cache
    if hasattr(search_cache, "_store"):
        n = len(search_cache._store)
        search_cache._store.clear()
    elif hasattr(search_cache, "_fallback"):
        n = len(search_cache._fallback._store)
        search_cache._fallback._store.clear()
    else:
        n = 0
    return {"cleared": n, "message": f"Cache svuotata: {n} voci rimosse."}


@app.get("/")
async def root():
    return {
        "name": "ManualFinder API",
        "version": "1.1.0",
        "docs": "/docs",
        "vision_provider": settings.get_vision_provider(),
        "search_provider": settings.get_search_provider(),
        "analysis_provider": settings.get_analysis_provider(),
    }

