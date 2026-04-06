"""
Servizio per l'upload di manuali PDF da parte degli ispettori.
Gestisce: validazione, verifica AI congruenza, salvataggio filesystem + Supabase.
"""
import json
import re
import time
from pathlib import Path
from typing import Optional
from app.config import settings

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
    except Exception:
        return {"ok": True}  # Impossibile estrarre testo — non blocchiamo

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

    except Exception:
        return {"ok": True}  # Errore AI — non blocchiamo l'upload


def save_uploaded_pdf(
    pdf_bytes: bytes,
    brand: str,
    model: str,
    machine_type: str,
    manual_year: Optional[str] = None,
    manual_language: str = "it",
    is_generic: bool = False,
    notes: Optional[str] = None,
) -> dict:
    """
    Salva il PDF nella cartella manuali_locali/ e registra il record su Supabase.
    Ritorna { filename, url, db_id }.
    """
    _ensure_upload_dir()

    filename = _sanitize_filename(brand, model, machine_type)
    filepath = UPLOAD_DIR / filename
    filepath.write_bytes(pdf_bytes)

    url = f"/manuals/uploaded/{filename}"

    # Registra su Supabase
    db_id = None
    try:
        from app.services import saved_manuals_service
        record = {
            "manual_brand": "GENERICO" if is_generic else brand,
            "manual_model": "CATEGORIA" if is_generic else model,
            "manual_machine_type": machine_type,
            "manual_language": manual_language,
            "url": url,
            "title": f"{brand} {model} — {machine_type}" + (" (generico)" if is_generic else ""),
            "is_pdf": True,
        }
        if manual_year:
            record["manual_year"] = manual_year
        if notes:
            record["notes"] = notes
        if not is_generic:
            record["search_brand"] = brand
            record["search_model"] = model
            record["search_machine_type"] = machine_type

        saved = saved_manuals_service.save_manual(record)
        db_id = str(saved.get("id"))
    except Exception:
        pass  # Il file è salvato anche se Supabase non è raggiungibile

    return {"filename": filename, "url": url, "db_id": db_id}
