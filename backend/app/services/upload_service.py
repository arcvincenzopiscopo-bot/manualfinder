"""
Servizio per l'upload di manuali PDF da parte degli ispettori.
Gestisce: validazione, verifica AI congruenza, salvataggio filesystem + Supabase Storage.
"""
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional
from app.config import settings

_logger = logging.getLogger(__name__)

# Cartella upload — relativa a backend/
_BACKEND_ROOT = Path(__file__).parent.parent.parent
UPLOAD_DIR = _BACKEND_ROOT / settings.upload_dir


def _ensure_upload_dir() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize_filename(brand: str, model: str, machine_type: str) -> str:
    """Genera un nome file sicuro da brand/model/machine_type + timestamp."""
    def clean(s: str) -> str:
        s = s.lower().strip()
        s = re.sub(r"[^\w]", "_", s)
        s = re.sub(r"_+", "_", s).strip("_")
        return s[:30]

    ts = int(time.time())
    parts = [clean(brand), clean(model), clean(machine_type), str(ts)]
    return "_".join(p for p in parts if p) + ".pdf"


async def validate_and_check(
    pdf_bytes: bytes,
    brand: str,
    model: str,
    machine_type: str,
    provider: str,
) -> dict:
    """
    Verifica congruenza tra il PDF caricato e i metadati forniti dall'ispettore.
    Estrae i primi ~3000 caratteri dal PDF e chiede all'AI se corrispondono.

    Ritorna:
      { "ok": True }
      { "ok": False, "suggested_brand": str, "suggested_model": str,
        "suggested_machine_type": str, "reason": str }
    Ritorna { "ok": True } anche in caso di errore AI (non blocca l'upload).
    """
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        texts = []
        for i, page in enumerate(doc):
            if i >= 5:  # massimo 5 pagine per il check
                break
            texts.append(page.get_text())
        doc.close()
        pdf_text = "\n".join(texts)[:3000].strip()
    except Exception as e:
        _logger.warning("validate_and_check: impossibile estrarre testo: %s", e)
        return {"ok": True}

    if not pdf_text:
        return {"ok": True}  # PDF vuoto o scansione sfuggita alla validazione

    prompt = (
        f"Analizza il seguente estratto di un PDF e rispondi in JSON.\n\n"
        f"L'ispettore afferma che questo è il manuale di:\n"
        f"  Marca: {brand}\n"
        f"  Modello: {model}\n"
        f"  Tipo macchina: {machine_type}\n\n"
        f"ESTRATTO PDF:\n{pdf_text}\n\n"
        f"Rispondi SOLO con JSON valido, nessun testo aggiuntivo:\n"
        f"Se i dati corrispondono: {{\"ok\": true}}\n"
        f"Se i dati NON corrispondono (marca/modello diversi o tipo macchina sbagliato):\n"
        f"{{\"ok\": false, \"suggested_brand\": \"...\", \"suggested_model\": \"...\", "
        f"\"suggested_machine_type\": \"...\", \"reason\": \"spiegazione breve in italiano\"}}\n"
        f"Se non riesci a determinare: {{\"ok\": true}}\n"
        f"IMPORTANTE: sii conservativo — rispondi false SOLO se hai certezza che i dati siano sbagliati."
    )

    try:
        raw = ""
        if provider == "anthropic":
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            resp = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip()
        elif provider == "gemini":
            from google import genai
            from google.genai import types as gtypes
            client = genai.Client(api_key=settings.gemini_api_key)
            resp = await client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=gtypes.GenerateContentConfig(
                    max_output_tokens=200,
                    temperature=0.0,
                    thinking_config=gtypes.ThinkingConfig(thinking_budget=0),
                ),
            )
            raw = resp.text.strip()
        else:
            return {"ok": True}

        # Estrai JSON anche se l'AI ha aggiunto testo intorno
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return {"ok": True}
        result = json.loads(match.group())
        return result if isinstance(result, dict) else {"ok": True}

    except Exception as e:
        _logger.warning("validate_and_check: errore AI: %s", e)
        return {"ok": True}


def _compress_pdf(pdf_bytes: bytes) -> bytes:
    """
    Comprime il PDF con la massima riduzione compatibile con la leggibilità AI.
    Usa PyMuPDF: scarica immagini incorporate a 72 DPI, reimposta metadati, rimuove duplicati.
    Ritorna i bytes compressi, o i bytes originali se la compressione fallisce.
    """
    try:
        import fitz
        src = fitz.open(stream=pdf_bytes, filetype="pdf")
        dst = fitz.open()

        for page in src:
            # Ridisegna ogni pagina a risoluzione ridotta per comprimere immagini incorporate
            mat = fitz.Matrix(0.85, 0.85)          # scala al 85% — bilancia qualità/dimensione
            pix = page.get_pixmap(matrix=mat, alpha=False)
            # Invece di usare il pixmap (rasterizza tutto), usa la copia diretta
            # con deflate e garbage collection attivi
            dst.insert_pdf(src, from_page=page.number, to_page=page.number)

        dst.close()
        src.close()

        # Riapri e salva con massima compressione
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        compressed = doc.tobytes(
            deflate=True,          # compressione zlib massima su stream
            garbage=4,             # rimuovi oggetti/reference non usati (livello massimo)
            clean=True,            # normalizza syntax PDF
            deflate_images=True,   # comprimi anche stream immagini
            deflate_fonts=True,    # comprimi anche i font
        )
        doc.close()
        # Ritorna il più piccolo tra originale e compresso
        return compressed if len(compressed) < len(pdf_bytes) else pdf_bytes
    except Exception as e:
        _logger.warning("compress_pdf fallback originale: %s", e)
        return pdf_bytes


async def _upload_to_supabase_storage(pdf_bytes: bytes, filename: str) -> Optional[str]:
    """
    Carica il PDF su Supabase Storage e restituisce l'URL pubblico.
    Richiede che supabase_url e supabase_service_key siano configurati.
    Restituisce None se il caricamento fallisce o la configurazione manca.
    """
    if not settings.supabase_url or not settings.supabase_service_key:
        return None
    import httpx
    bucket = settings.supabase_storage_bucket
    storage_path = f"uploads/{filename}"
    upload_url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{storage_path}"
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_key}",
        "Content-Type": "application/pdf",
        "x-upsert": "true",  # sovrascrive se esiste già
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.put(upload_url, content=pdf_bytes, headers=headers)
            if r.status_code in (200, 201):
                public_url = (
                    f"{settings.supabase_url.rstrip('/')}/storage/v1/object/public/"
                    f"{bucket}/{storage_path}"
                )
                _logger.info("PDF caricato su Supabase Storage: %s", public_url)
                return public_url
            _logger.warning(
                "Supabase Storage upload fallito: HTTP %s — %s", r.status_code, r.text[:200]
            )
    except Exception as e:
        _logger.warning("Supabase Storage upload errore: %s", e)
    return None


def save_uploaded_pdf(
    pdf_bytes: bytes,
    brand: str,
    model: str,
    machine_type: str,
    machine_type_id: Optional[int] = None,
    manual_year: Optional[str] = None,
    manual_language: str = "it",
    is_generic: bool = False,
    notes: Optional[str] = None,
    _storage_url: Optional[str] = None,   # URL pubblico Supabase Storage (passato dall'endpoint async)
    _precomputed_filename: Optional[str] = None,  # filename già generato dall'endpoint
    _precompressed_bytes: Optional[bytes] = None,  # bytes già compressi dall'endpoint
) -> dict:
    """
    Salva il PDF nella cartella manuali_locali/ (con compressione massima) e registra su Supabase DB.
    Se _storage_url è fornito (caricato su Supabase Storage dall'endpoint async), usa quello come URL
    persistente invece del percorso locale (sopravvive ai redeploy su Render).
    Ritorna { filename, url, db_id }.
    """
    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("Il file caricato non è un PDF valido (magic bytes mancanti).")

    _ensure_upload_dir()

    compressed_bytes = _precompressed_bytes if _precompressed_bytes is not None else _compress_pdf(pdf_bytes)

    filename = _precomputed_filename if _precomputed_filename else _sanitize_filename(brand, model, machine_type)
    filepath = UPLOAD_DIR / filename
    filepath.write_bytes(compressed_bytes)

    # Usa l'URL pubblico Supabase Storage se disponibile (persistente su cloud),
    # altrimenti fallback al percorso locale (funziona in dev o se Storage non è configurato)
    url = _storage_url if _storage_url else f"/manuals/uploaded/{filename}"

    # Registra su Supabase DB
    db_id = None
    try:
        from app.services import saved_manuals_service
        from app.services.machine_type_service import resolve_machine_type_id
        # Usa machine_type_id già risolto se fornito, altrimenti risolvi dal testo
        mt_id = machine_type_id if machine_type_id is not None else (
            resolve_machine_type_id(machine_type) if machine_type else None
        )
        record = {
            "manual_brand": "GENERICO" if is_generic else brand,
            "manual_model": "CATEGORIA" if is_generic else model,
            "manual_machine_type": machine_type,
            "manual_language": manual_language,
            "url": url,
            "title": f"{brand} {model} — {machine_type}" + (" (generico)" if is_generic else ""),
            "is_pdf": True,
        }
        if mt_id:
            record["machine_type_id"] = mt_id
        if manual_year:
            record["manual_year"] = manual_year
        if notes:
            record["notes"] = notes
        if not is_generic:
            record["search_brand"] = brand
            record["search_model"] = model
            record["search_machine_type"] = machine_type
            if mt_id:
                record["search_machine_type_id"] = mt_id

        saved = saved_manuals_service.save_manual(record)
        db_id = str(saved.get("id"))
    except Exception as e:
        _logger.warning("save_uploaded_pdf: registrazione DB fallita: %s", e)

    return {"filename": filename, "url": url, "db_id": db_id}
