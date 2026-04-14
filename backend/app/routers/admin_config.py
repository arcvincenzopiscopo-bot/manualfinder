"""
Admin endpoints per gestione configurazioni (config_lists, config_maps,
domain_classifications, brand_machine_type_hints).
Tutti protetti da X-Admin-Token.
"""
from typing import Optional, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import config_service

router = APIRouter(prefix="/admin/config", tags=["Admin Config"])


# ─── config_lists ─────────────────────────────────────────────────────────────

@router.get("/lists")
def list_keys():
    return {"keys": config_service.list_keys()}


@router.get("/lists/{list_key}")
def get_list_items(list_key: str):
    return {"list_key": list_key, "items": config_service.get_list_with_meta(list_key)}


class ListItemIn(BaseModel):
    item: str
    meta: Optional[dict] = None


@router.post("/lists/{list_key}")
def add_list_item(list_key: str, body: ListItemIn):
    ok = config_service.add_list_item(list_key, body.item, body.meta)
    if not ok:
        raise HTTPException(500, "Inserimento fallito")
    return {"status": "ok", "list_key": list_key, "item": body.item}


@router.delete("/lists/{list_key}/{item:path}")
def delete_list_item(list_key: str, item: str):
    config_service.delete_list_item(list_key, item)
    return {"status": "deleted"}


# ─── config_maps ──────────────────────────────────────────────────────────────

@router.get("/maps")
def map_keys():
    return {"keys": config_service.map_keys()}


@router.get("/maps/{map_key}")
def get_map_entries(map_key: str):
    return {"map_key": map_key, "entries": config_service.list_map_entries(map_key)}


class MapEntryIn(BaseModel):
    k: str
    v: Any


@router.post("/maps/{map_key}")
def set_map_entry(map_key: str, body: MapEntryIn):
    ok = config_service.set_map_entry(map_key, body.k, body.v)
    if not ok:
        raise HTTPException(500, "Inserimento fallito")
    return {"status": "ok", "map_key": map_key, "k": body.k}


@router.delete("/maps/{map_key}/{k:path}")
def delete_map_entry(map_key: str, k: str):
    config_service.delete_map_entry(map_key, k)
    return {"status": "deleted"}


# ─── domain_classifications ──────────────────────────────────────────────────

@router.get("/domains")
def get_domains(kind: Optional[str] = None):
    return {"domains": config_service.list_domains(kind), "kinds": config_service.domain_kinds()}


class DomainIn(BaseModel):
    domain: str
    kind: str
    brand: Optional[str] = None


@router.post("/domains")
def add_domain(body: DomainIn):
    ok = config_service.add_domain(body.domain, body.kind, body.brand)
    if not ok:
        raise HTTPException(500, "Inserimento fallito")
    return {"status": "ok"}


@router.delete("/domains/{row_id}")
def delete_domain(row_id: int):
    config_service.delete_domain(row_id)
    return {"status": "deleted"}


# ─── brand_machine_type_hints ─────────────────────────────────────────────────

@router.get("/brand-hints")
def get_brand_hints():
    return {"hints": config_service.list_brand_hints()}


class BrandHintIn(BaseModel):
    brand: str
    machine_type_text: str
    model_prefix: Optional[str] = None
    machine_type_id: Optional[int] = None


@router.post("/brand-hints")
def add_brand_hint(body: BrandHintIn):
    ok = config_service.add_brand_hint(
        body.brand, body.machine_type_text, body.model_prefix, body.machine_type_id
    )
    if not ok:
        raise HTTPException(500, "Inserimento fallito")
    return {"status": "ok"}


@router.delete("/brand-hints/{row_id}")
def delete_brand_hint(row_id: int):
    config_service.delete_brand_hint(row_id)
    return {"status": "deleted"}


# ─── cache invalidation ───────────────────────────────────────────────────────

@router.post("/cache-clear")
def clear_config_cache():
    config_service.invalidate_cache()
    return {"status": "ok", "message": "Config cache invalidata."}


# ─── AI usage & provider order ────────────────────────────────────────────────

@router.get("/ai-usage")
async def get_ai_usage():
    """Contatori utilizzo odierno per provider (gemini, groq1, groq2)."""
    from app.services.llm_router import llm_router
    return await llm_router.get_all_usage_today()


class ProviderOrderIn(BaseModel):
    order: list[str]


@router.get("/ai-provider-order")
def get_ai_provider_order():
    """Ordine provider per ogni tipo di funzione AI (da config_maps)."""
    from app.services.llm_router import _DEFAULT_ORDER
    task_types = list(_DEFAULT_ORDER.keys())
    result = {}
    order_map = config_service.get_map("ai_provider_order")
    for task_type in task_types:
        val = order_map.get(task_type)
        result[task_type] = val if isinstance(val, list) else _DEFAULT_ORDER.get(task_type, [])
    return result


@router.put("/ai-provider-order/{task_type}")
def set_ai_provider_order(task_type: str, body: ProviderOrderIn):
    """Aggiorna l'ordine provider per un task type e invalida la cache del router."""
    from app.services.llm_router import llm_router, _DEFAULT_ORDER, DAILY_LIMITS
    valid_task_types = set(_DEFAULT_ORDER.keys())
    if task_type not in valid_task_types:
        raise HTTPException(400, f"task_type non valido. Valori ammessi: {sorted(valid_task_types)}")
    valid_providers = set(DAILY_LIMITS.keys()) | {"tesseract"}
    invalid = [p for p in body.order if p not in valid_providers]
    if invalid:
        raise HTTPException(400, f"Provider non validi: {invalid}. Ammessi: {sorted(valid_providers)}")
    config_service.set_map_entry("ai_provider_order", task_type, body.order)
    llm_router.invalidate_order_cache()
    return {"status": "ok", "task_type": task_type, "order": body.order}
