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
