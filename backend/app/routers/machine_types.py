"""
API per il catalogo tipi macchina.
GET  /api/machine-types                          → lista completa per dropdown frontend
POST /api/machine-types/suggest                  → proponi nuovo tipo (→ pending_machine_types)
POST /api/machine-types/feedback                 → conferma/correzione tipo (→ increment_usage)

Admin endpoints (punti 3-4-5-6):
GET  /api/machine-types/admin/stats              → statistiche generali
GET  /api/machine-types/admin/pending            → proposte pending
POST /api/machine-types/admin/pending/{id}/resolve → risolvi proposta
GET  /api/machine-types/{id}/aliases             → alias di un tipo
POST /api/machine-types/{id}/aliases             → aggiungi alias
DELETE /api/machine-types/aliases/{alias_id}     → elimina alias
PATCH /api/machine-types/{id}/flags              → aggiorna flags normativi
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.services import machine_type_service, scan_log_service
from app.config import settings

router = APIRouter(prefix="/machine-types", tags=["machine-types"])


# ── Modelli request ───────────────────────────────────────────────────────────

class SuggestRequest(BaseModel):
    proposed_name: str = Field(..., min_length=2, max_length=100)
    session_id: Optional[str] = None


class FeedbackRequest(BaseModel):
    machine_type_id: int
    outcome: str = Field(..., pattern="^(confirmed|corrected|skipped)$")
    corrected_name: Optional[str] = None


class ResolveRequest(BaseModel):
    action: str = Field(..., pattern="^(alias|promote|reject)$")
    merge_into_id: Optional[int] = None        # richiesto se action == "alias"
    new_type_name: Optional[str] = None        # opzionale se action == "promote"
    new_requires_patentino: bool = True
    new_requires_verifiche: bool = True


class AddAliasRequest(BaseModel):
    alias_text: str = Field(..., min_length=2, max_length=100)


class UpdateFlagsRequest(BaseModel):
    requires_patentino: bool
    requires_verifiche: bool
    inail_search_hint: Optional[str] = None
    vita_utile_anni: Optional[int] = None


class HazardUpdateRequest(BaseModel):
    categoria_inail: str = Field(..., min_length=2, max_length=200)
    focus_testo: str = Field(..., min_length=10)


# ── Endpoint pubblici ─────────────────────────────────────────────────────────

@router.get("")
def list_machine_types():
    """Lista completa dei tipi macchina verificati (id, name, requires_patentino)."""
    return machine_type_service.get_all_types()


@router.post("/suggest")
def suggest_machine_type(req: SuggestRequest):
    """Propone un nuovo tipo macchina (entra in pending)."""
    if not req.proposed_name.strip():
        raise HTTPException(status_code=422, detail="proposed_name non può essere vuoto")
    return machine_type_service.suggest_new_type(
        proposed_name=req.proposed_name.strip(),
        session_id=req.session_id or "",
    )


@router.post("/feedback")
def submit_feedback(req: FeedbackRequest):
    """Registra feedback ispettore. Incrementa usage_count su confirmed/corrected."""
    if req.outcome in ("confirmed", "corrected"):
        machine_type_service.increment_usage(req.machine_type_id)
    return {"status": "ok", "machine_type_id": req.machine_type_id, "outcome": req.outcome}


# ── Admin: statistiche (punto 6) ──────────────────────────────────────────────

@router.get("/admin/stats")
def admin_stats():
    """Statistiche pannello admin: totali, top-10 tipi per utilizzo, pending stale."""
    return machine_type_service.admin_get_stats()


# ── Admin: gestione pending (punto 3) ────────────────────────────────────────

@router.get("/admin/pending")
def admin_list_pending():
    """Lista delle proposte utente in attesa di revisione."""
    return machine_type_service.admin_get_pending()


@router.post("/admin/pending/{pending_id}/resolve")
def admin_resolve_pending(pending_id: int, req: ResolveRequest):
    """
    Risolve una proposta pending.
    action=alias   → salva come alias di merge_into_id
    action=promote → crea nuovo tipo canonico
    action=reject  → scarta
    """
    if req.action == "alias" and not req.merge_into_id:
        raise HTTPException(status_code=422, detail="merge_into_id richiesto per action=alias")
    result = machine_type_service.admin_resolve_pending(
        pending_id=pending_id,
        action=req.action,
        merge_into_id=req.merge_into_id,
        new_type_name=req.new_type_name,
        new_requires_patentino=req.new_requires_patentino,
        new_requires_verifiche=req.new_requires_verifiche,
    )
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Proposta non trovata")
    return result


# ── Admin: gestione alias (punto 4) ──────────────────────────────────────────

@router.get("/{machine_type_id}/aliases")
def admin_get_aliases(machine_type_id: int):
    """Lista degli alias di un tipo macchina."""
    return machine_type_service.admin_get_aliases(machine_type_id)


@router.post("/{machine_type_id}/aliases")
def admin_add_alias(machine_type_id: int, req: AddAliasRequest):
    """Aggiunge un alias manuale a un tipo macchina."""
    result = machine_type_service.admin_add_alias(machine_type_id, req.alias_text)
    if result.get("status") == "duplicate":
        raise HTTPException(status_code=409, detail="Alias già esistente")
    return result


@router.delete("/aliases/{alias_id}")
def admin_delete_alias(alias_id: int):
    """Elimina un alias."""
    return machine_type_service.admin_delete_alias(alias_id)


# ── Admin: aggiorna flags normativi (punto 5) ─────────────────────────────────

@router.patch("/{machine_type_id}/flags")
def admin_update_flags(machine_type_id: int, req: UpdateFlagsRequest):
    """Aggiorna requires_patentino, requires_verifiche, inail_search_hint e vita_utile_anni di un tipo."""
    return machine_type_service.admin_update_flags(
        machine_type_id=machine_type_id,
        requires_patentino=req.requires_patentino,
        requires_verifiche=req.requires_verifiche,
        inail_search_hint=req.inail_search_hint,
        vita_utile_anni=req.vita_utile_anni,
    )


# ── Vita utile ────────────────────────────────────────────────────────────────

@router.post("/admin/populate-vita-utile")
async def admin_populate_vita_utile():
    """Chiama AI per popolare vita_utile_anni per tutti i tipi con valore NULL."""
    provider = settings.get_analysis_provider()
    return await machine_type_service.admin_populate_vita_utile(provider)


# ── Hazard Intelligence ───────────────────────────────────────────────────────

@router.get("/{machine_type_id}/hazard")
def get_hazard(machine_type_id: int):
    """Restituisce i dati hazard di un tipo macchina."""
    return machine_type_service.get_hazard(machine_type_id) or {}


@router.post("/{machine_type_id}/hazard")
def update_hazard(machine_type_id: int, req: HazardUpdateRequest):
    """Inserisce o aggiorna manualmente i dati hazard di un tipo macchina."""
    machine_type_service.admin_upsert_hazard(machine_type_id, req.categoria_inail, req.focus_testo, "admin")
    return {"ok": True}


@router.post("/admin/populate-hazard")
async def admin_populate_hazard():
    """Chiama AI per generare i dati hazard per tutti i tipi senza dati o dati > 90 giorni."""
    provider = settings.get_analysis_provider()
    return await machine_type_service.admin_populate_hazard(provider)


@router.post("/admin/populate-inail-hint")
async def admin_populate_inail_hint():
    """Chiama AI per associare il quaderno INAIL locale a tutti i tipi con inail_search_hint NULL."""
    provider = settings.get_analysis_provider()
    return await machine_type_service.admin_populate_inail_hint(provider)


# ── Admin: scan log (storico analisi) ────────────────────────────────────────

@router.get("/admin/scan-log")
def admin_scan_log(limit: int = 100, fonte: Optional[str] = None, exclude_exact: bool = False):
    """
    Lista scansioni per il pannello admin (escluse le dismissed).
    fonte='fallback_ai' per mostrare solo quelle senza manuale trovato.
    exclude_exact=true per escludere le scansioni con manuale esatto (inail+produttore).
    """
    return scan_log_service.get_admin_scans(limit=limit, fonte_filter=fonte, exclude_exact=exclude_exact)


@router.post("/admin/scan-log/{scan_id}/dismiss")
def admin_dismiss_scan(scan_id: int):
    """Nasconde una scansione dal pannello admin (non la cancella dal DB)."""
    ok = scan_log_service.dismiss_scan(scan_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Scansione non trovata o DB non disponibile")
    return {"ok": True}


@router.get("/admin/scan-log/{scan_id}/image")
def admin_scan_image(scan_id: int):
    """
    Restituisce la foto dell'etichetta compressa (JPEG) per una scansione.
    Conservata per 30 giorni dal momento della scansione.
    """
    from fastapi.responses import Response
    img = scan_log_service.get_scan_image(scan_id)
    if img is None:
        raise HTTPException(status_code=404, detail="Immagine non disponibile")
    return Response(content=img, media_type="image/jpeg")


# ── Lista file INAIL locali ───────────────────────────────────────────────────

@router.get("/inail-local-files")
def list_inail_local_files():
    """
    Restituisce la lista dei PDF INAIL presenti nella cartella locale.
    Usato dal pannello admin (tab Flags) per il dropdown di associazione file.
    Risposta: [{ filename, title, exists }]
    """
    from app.services.local_manuals_service import PDF_MANUALS_DIR, LOCAL_MANUALS_MAP
    result = []
    seen = set()
    # Prima elenca i file noti dalla mappa (anche se non presenti su disco)
    for canonical, filename in LOCAL_MANUALS_MAP.items():
        if filename in seen:
            continue
        seen.add(filename)
        filepath = PDF_MANUALS_DIR / filename
        result.append({
            "filename": filename,
            "title": filename.replace(".pdf", "").strip(),
            "exists": filepath.exists(),
        })
    # Poi aggiunge eventuali file extra trovati su disco non nella mappa
    if PDF_MANUALS_DIR.exists():
        for f in sorted(PDF_MANUALS_DIR.glob("*.pdf")):
            if f.name not in seen:
                result.append({
                    "filename": f.name,
                    "title": f.name.replace(".pdf", "").strip(),
                    "exists": True,
                })
    result.sort(key=lambda x: x["filename"])
    return result


# ── Ricerca email produttore ──────────────────────────────────────────────────

@router.get("/manufacturer-email")
async def get_manufacturer_email(brand: str, model: str = ""):
    """
    Cerca l'email del servizio assistenza tecnica italiano del produttore.
    Usato da: pannello admin (tab Ricerche) e SafetyCard (bottone email).
    Risposta: { email: "italy.service@brand.com" | null }
    """
    from app.services.manufacturer_email_service import find_manufacturer_email
    provider = settings.get_analysis_provider()
    email = await find_manufacturer_email(brand.strip(), provider)
    return {"email": email}
