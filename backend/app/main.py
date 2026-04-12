from fastapi import FastAPI, Request, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.routers import analyze, manual, health, manuals, machine_types, rag_admin, feedback
from app.config import settings


def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    """Dependency: verifica X-Admin-Token se admin_token è configurato in settings."""
    expected = settings.admin_token
    if expected and x_admin_token != expected:
        raise HTTPException(status_code=401, detail="X-Admin-Token non valido o mancante.")

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
app.include_router(machine_types.router)
app.include_router(rag_admin.router, dependencies=[Depends(require_admin_token)])
app.include_router(feedback.router, prefix="/feedback")


@app.on_event("startup")
async def on_startup():
    """Svuota la cache di ricerca ad ogni avvio — garantisce che le modifiche al codice siano attive."""
    from app.services.cache_service import search_cache
    if hasattr(search_cache, "_store"):
        search_cache._store.clear()
    elif hasattr(search_cache, "_fallback"):
        search_cache._fallback._store.clear()
    # Esegui migrazioni DB versionato (idempotente)
    try:
        from app.db.migrations import run_migrations
        run_migrations()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Migrazioni DB fallite: %s", e)
    # Inizializza catalogo tipi macchina: crea tabelle + seed + carica alias map
    try:
        from app.services.machine_type_service import _ensure_tables
        _ensure_tables()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("machine_type_service init fallito: %s", e)
    # Esporta alias hardcodati in machine_aliases DB
    try:
        from app.services.local_manuals_service import _seed_local_aliases_into_db
        _seed_local_aliases_into_db()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("seed local aliases fallito: %s", e)
    # Esporta mappa quaderni INAIL in inail_manual_assignments DB
    try:
        from app.services.local_manuals_service import _seed_inail_assignments_if_empty
        _seed_inail_assignments_if_empty()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("seed inail assignments fallito: %s", e)
    # Aggiorna flags normativi (should_have_manual, is_officina) in machine_types
    try:
        from app.services.quality_service import _seed_machine_type_flags_if_needed
        _seed_machine_type_flags_if_needed()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("seed machine type flags fallito: %s", e)
    # Esporta normative in machine_type_normative DB
    try:
        from app.data.machine_normative import _seed_normative_if_empty
        _seed_normative_if_empty()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("seed normative fallito: %s", e)
    # Esporta riferimenti normativi in riferimenti_normativi DB
    try:
        from app.data.riferimenti_normativi import _seed_riferimenti_if_empty
        _seed_riferimenti_if_empty()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("seed riferimenti fallito: %s", e)
    # Invalida cache RAG — corpus potrebbe essere stato aggiornato offline
    try:
        from app.services import rag_service
        rag_service.invalidate_cache()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("RAG cache invalidation fallita: %s", e)
    # Avvia crawler scheduler notturno
    try:
        from app.services.crawl_scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Crawl scheduler non avviato: %s", e)


@app.on_event("shutdown")
async def on_shutdown():
    try:
        from app.services.crawl_scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass


@app.get("/admin/cache-clear", dependencies=[Depends(require_admin_token)])
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

