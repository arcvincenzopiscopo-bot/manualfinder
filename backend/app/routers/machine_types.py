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
import logging
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional

from app.services import machine_type_service, scan_log_service
from app.utils.errors import internal_error

logger = logging.getLogger(__name__)
from app.config import settings


def _require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    """Verifica X-Admin-Token per endpoint admin."""
    expected = settings.admin_token
    if expected and x_admin_token != expected:
        raise HTTPException(status_code=401, detail="X-Admin-Token non valido o mancante.")


_admin = [Depends(_require_admin_token)]

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

@router.get("/admin/stats", dependencies=_admin)
def admin_stats():
    """Statistiche pannello admin: totali, top-10 tipi per utilizzo, pending stale."""
    return machine_type_service.admin_get_stats()


# ── Admin: gestione pending (punto 3) ────────────────────────────────────────

@router.get("/admin/pending", dependencies=_admin)
def admin_list_pending():
    """Lista delle proposte utente in attesa di revisione."""
    return machine_type_service.admin_get_pending()


@router.post("/admin/pending/{pending_id}/resolve", dependencies=_admin)
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

@router.get("/{machine_type_id}/aliases", dependencies=_admin)
def admin_get_aliases(machine_type_id: int):
    """Lista degli alias di un tipo macchina."""
    return machine_type_service.admin_get_aliases(machine_type_id)


@router.post("/{machine_type_id}/aliases", dependencies=_admin)
def admin_add_alias(machine_type_id: int, req: AddAliasRequest):
    """Aggiunge un alias manuale a un tipo macchina."""
    result = machine_type_service.admin_add_alias(machine_type_id, req.alias_text)
    if result.get("status") == "duplicate":
        raise HTTPException(status_code=409, detail="Alias già esistente")
    return result


@router.delete("/aliases/{alias_id}", dependencies=_admin)
def admin_delete_alias(alias_id: int):
    """Elimina un alias."""
    return machine_type_service.admin_delete_alias(alias_id)


@router.post("/{machine_type_id}/autopopulate-aliases", dependencies=_admin)
async def admin_autopopulate_aliases(machine_type_id: int):
    """
    Popola machine_aliases con termini equivalenti in EN/DE/FR/ES generati dall'AI.
    Alias salvati con source='ai_i18n' (promovibili a 'admin' dopo revisione).
    """
    provider = settings.get_analysis_provider()
    result = await machine_type_service.admin_autopopulate_aliases(machine_type_id, provider)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Tipo macchina non trovato")
    return result


@router.post("/aliases/{alias_id}/confirm", dependencies=_admin)
def admin_confirm_alias(alias_id: int):
    """Promuove un alias a source='admin' (revisionato da admin)."""
    result = machine_type_service.admin_confirm_alias(alias_id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Alias non trovato")
    return result


# ── Admin: aggiorna flags normativi (punto 5) ─────────────────────────────────

@router.patch("/{machine_type_id}/flags", dependencies=_admin)
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

@router.post("/admin/populate-vita-utile", dependencies=_admin)
async def admin_populate_vita_utile():
    """Chiama AI per popolare vita_utile_anni per tutti i tipi con valore NULL."""
    provider = settings.get_analysis_provider()
    return await machine_type_service.admin_populate_vita_utile(provider)


# ── Hazard Intelligence ───────────────────────────────────────────────────────

@router.get("/{machine_type_id}/hazard", dependencies=_admin)
def get_hazard(machine_type_id: int):
    """Restituisce i dati hazard di un tipo macchina."""
    return machine_type_service.get_hazard(machine_type_id) or {}


@router.post("/{machine_type_id}/hazard", dependencies=_admin)
def update_hazard(machine_type_id: int, req: HazardUpdateRequest):
    """Inserisce o aggiorna manualmente i dati hazard di un tipo macchina."""
    machine_type_service.admin_upsert_hazard(machine_type_id, req.categoria_inail, req.focus_testo, "admin")
    return {"ok": True}


@router.post("/admin/populate-hazard", dependencies=_admin)
async def admin_populate_hazard():
    """Chiama AI per generare i dati hazard per tutti i tipi senza dati o dati > 90 giorni."""
    provider = settings.get_analysis_provider()
    return await machine_type_service.admin_populate_hazard(provider)


@router.post("/admin/populate-inail-hint", dependencies=_admin)
async def admin_populate_inail_hint():
    """Chiama AI per associare il quaderno INAIL locale a tutti i tipi con inail_search_hint NULL."""
    provider = settings.get_analysis_provider()
    return await machine_type_service.admin_populate_inail_hint(provider)


# ── Admin: proposte da disco ──────────────────────────────────────────────────

@router.post("/admin/propose-from-disk", dependencies=_admin)
async def admin_propose_from_disk():
    """Scansiona la cartella pdf manuali e crea proposte per i file senza categoria associata."""
    return await machine_type_service.admin_propose_from_disk()


@router.get("/admin/disk-proposals", dependencies=_admin)
def admin_get_disk_proposals():
    """Ritorna le proposte pending generate dalla scansione disco."""
    return machine_type_service.admin_get_pending_proposals()


@router.post("/admin/disk-proposals/{proposal_id}/resolve", dependencies=_admin)
def admin_resolve_disk_proposal(proposal_id: int, body: dict):
    """
    Risolve una proposta.
    body: { action: 'approve'|'reject', final_name?: string }
    """
    return machine_type_service.admin_resolve_proposal(
        proposal_id,
        body.get("action", ""),
        body.get("final_name"),
    )


# ── Admin: scan log (storico analisi) ────────────────────────────────────────

@router.get("/admin/scan-log", dependencies=_admin)
def admin_scan_log(limit: int = 100, fonte: Optional[str] = None, exclude_exact: bool = False):
    """
    Lista scansioni per il pannello admin (escluse le dismissed).
    fonte='fallback_ai' per mostrare solo quelle senza manuale trovato.
    exclude_exact=true per escludere le scansioni con manuale esatto (inail+produttore).
    """
    return scan_log_service.get_admin_scans(limit=limit, fonte_filter=fonte, exclude_exact=exclude_exact)


@router.post("/admin/scan-log/{scan_id}/dismiss", dependencies=_admin)
def admin_dismiss_scan(scan_id: int):
    """Nasconde una scansione dal pannello admin (non la cancella dal DB)."""
    ok = scan_log_service.dismiss_scan(scan_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Scansione non trovata o DB non disponibile")
    return {"ok": True}


@router.get("/admin/scan-log/{scan_id}/image", dependencies=_admin)
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

@router.get("/inail-local-files", dependencies=_admin)
def list_inail_local_files():
    """
    Restituisce la lista dei PDF INAIL presenti nella cartella locale.
    Include assegnazioni DB + file su disco non ancora assegnati.
    Risposta: [{ filename, title, exists, machine_type_id? }]
    """
    from app.services.local_manuals_service import (
        PDF_MANUALS_DIR, list_inail_assignments, list_all_pdf_files
    )
    result = []
    seen: set = set()

    # Assegnazioni DB (con flag exists)
    for assignment in list_inail_assignments():
        fn = assignment["pdf_filename"]
        if fn in seen:
            continue
        seen.add(fn)
        result.append({
            "filename": fn,
            "title": assignment["display_title"],
            "machine_type_id": assignment["machine_type_id"],
            "machine_type_name": assignment["machine_type_name"],
            "exists": assignment["exists_on_disk"],
        })

    # File su disco non ancora assegnati
    for entry in list_all_pdf_files():
        if entry["filename"] not in seen:
            seen.add(entry["filename"])
            result.append({
                "filename": entry["filename"],
                "title": entry["title"],
                "machine_type_id": None,
                "machine_type_name": None,
                "exists": True,
            })

    result.sort(key=lambda x: x["filename"])
    return result


# ── Normative (admin CRUD) ───────────────────────────────────────────────────

@router.get("/normative/admin", dependencies=_admin)
def admin_list_normative(machine_type_id: Optional[int] = None):
    """[Admin] Lista normative da DB. machine_type_id=None restituisce tutto."""
    from app.config import settings as _s
    import psycopg2
    import psycopg2.extras
    if not _s.database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL non configurata")
    try:
        from app.services.db_pool import get_conn_raw
        conn = get_conn_raw()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if machine_type_id is not None:
                cur.execute(
                    "SELECT * FROM machine_type_normative WHERE machine_type_id = %s ORDER BY display_order",
                    (machine_type_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT n.*, mt.name AS machine_type_name
                    FROM machine_type_normative n
                    LEFT JOIN machine_types mt ON mt.id = n.machine_type_id
                    WHERE n.is_active = true
                    ORDER BY n.machine_type_id NULLS FIRST, n.display_order
                    """
                )
            rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        raise internal_error(logger, e, context="list normative")


@router.post("/normative", dependencies=_admin)
def admin_add_normativa(body: dict):
    """[Admin] Aggiunge una norma. Body: { machine_type_id?: int|null, norm_text: str, display_order?: int }"""
    from app.config import settings as _s
    import psycopg2
    norm_text = (body.get("norm_text") or "").strip()
    if not norm_text:
        raise HTTPException(status_code=422, detail="norm_text obbligatorio")
    if not _s.database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL non configurata")
    try:
        from app.services.db_pool import get_conn_raw
        conn = get_conn_raw()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO machine_type_normative (machine_type_id, norm_text, display_order)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (body.get("machine_type_id"), norm_text, body.get("display_order", 0)),
            )
            new_id = cur.fetchone()[0]
        conn.commit()
        conn.close()
        # Invalida cache
        try:
            from app.data.machine_normative import _load_cache
            _load_cache()
        except Exception:
            pass
        return {"ok": True, "id": new_id}
    except Exception as e:
        raise internal_error(logger, e, context="add normativa")


@router.delete("/normative/{norm_id}", dependencies=_admin)
def admin_delete_normativa(norm_id: int):
    """[Admin] Disattiva una norma (is_active = false)."""
    from app.config import settings as _s
    import psycopg2
    if not _s.database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL non configurata")
    try:
        from app.services.db_pool import get_conn_raw
        conn = get_conn_raw()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE machine_type_normative SET is_active = false WHERE id = %s",
                (norm_id,),
            )
            updated = cur.rowcount
        conn.commit()
        conn.close()
        if updated == 0:
            raise HTTPException(status_code=404, detail="Norma non trovata")
        try:
            from app.data.machine_normative import _load_cache
            _load_cache()
        except Exception:
            pass
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise internal_error(logger, e, context="delete normativa")


# ── Riferimenti normativi (admin CRUD) ────────────────────────────────────────

@router.get("/riferimenti/admin", dependencies=_admin)
def admin_list_riferimenti():
    """[Admin] Lista riferimenti normativi da DB."""
    from app.config import settings as _s
    import psycopg2
    import psycopg2.extras
    if not _s.database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL non configurata")
    try:
        from app.services.db_pool import get_conn_raw
        conn = get_conn_raw()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, norma_key, norma, titolo, machine_type_ids, is_active FROM riferimenti_normativi ORDER BY id"
            )
            rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        raise internal_error(logger, e, context="list riferimenti")


@router.patch("/riferimenti/{ref_id}", dependencies=_admin)
def admin_update_riferimento(ref_id: int, body: dict):
    """[Admin] Aggiorna machine_type_ids di un riferimento. Body: { machine_type_ids: int[] | null }"""
    from app.config import settings as _s
    import psycopg2
    if not _s.database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL non configurata")
    try:
        new_ids = body.get("machine_type_ids")  # None = universale, [] = nessuno
        from app.services.db_pool import get_conn_raw
        conn = get_conn_raw()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE riferimenti_normativi SET machine_type_ids = %s WHERE id = %s",
                (new_ids, ref_id),
            )
            updated = cur.rowcount
        conn.commit()
        conn.close()
        if updated == 0:
            raise HTTPException(status_code=404, detail="Riferimento non trovato")
        # Invalida cache riferimenti
        try:
            from app.data.riferimenti_normativi import _load_cache
            _load_cache()
        except Exception:
            pass
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise internal_error(logger, e, context="update riferimento")


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
