"""
Server FastAPI locale per la GUI di indicizzazione corpus RAG.

Gira SOLO su localhost:7777 — non viene mai esposto su Render.
Avvio: python -m app.local_indexer  (dalla cartella backend/)

Funzionalità:
  - Lista PDF nel corpus con stato indicizzazione
  - Indicizzazione singola o completa con SSE progress
  - Upload PDF drag-and-drop
  - Export ZIP del ChromaDB per upload su Render
  - Apertura cartella corpus in Explorer
"""
import os
import io
import json
import shutil
import zipfile
import asyncio
import subprocess
import sys
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Assicura che il path del progetto sia nel sys.path
_BACKEND_ROOT = Path(__file__).parent.parent.parent  # backend/
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.corpus_indexer import (
    CORPUS_PATH,
    CHROMA_PATH,
    PDF_MANUALI_PATH,
    EMBEDDING_MODEL,
    get_index_stats,
    index_document,
    index_all_corpus,
    _file_hash,
    get_collection,
)

app = FastAPI(title="RAG Local Indexer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── UI ───────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def ui():
    """Serve la pagina HTML della GUI."""
    html_path = Path(__file__).parent / "ui.html"
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


# ─── Status e lista file ──────────────────────────────────────────────────────

@app.get("/status")
async def status():
    """Statistiche corpus + lista file PDF con stato indicizzazione."""
    stats = get_index_stats()

    # Mappa hash → indicizzato
    indexed_hashes: set = set()
    collection = get_collection()
    if collection:
        try:
            all_meta = collection.get(include=["metadatas"])
            indexed_hashes = {m.get("file_hash", "") for m in (all_meta.get("metadatas") or [])}
        except Exception:
            pass

    # Scansiona corpus/raw/ + pdf manuali/ per trovare tutti i PDF disponibili
    pdf_files = []
    seen_filenames: set = set()

    def _add_pdf_dir(base_dir: str, label_prefix: str):
        if not os.path.exists(base_dir):
            return
        for root, _, files in os.walk(base_dir):
            for filename in files:
                if not filename.lower().endswith(".pdf"):
                    continue
                if filename in seen_filenames:
                    continue
                seen_filenames.add(filename)
                full_path = os.path.join(root, filename)
                rel_path = label_prefix + "/" + os.path.relpath(full_path, base_dir).replace("\\", "/")
                try:
                    fh = _file_hash(full_path)
                    is_indexed = fh in indexed_hashes
                except Exception:
                    fh = ""
                    is_indexed = False
                pdf_files.append({
                    "filename": filename,
                    "rel_path": rel_path,
                    "full_path": full_path,
                    "size_kb": round(os.path.getsize(full_path) / 1024, 1),
                    "indexed": is_indexed,
                    "file_hash": fh,
                })

    _add_pdf_dir(CORPUS_PATH, "corpus/raw")
    _add_pdf_dir(PDF_MANUALI_PATH, "pdf manuali")

    return {
        **stats,
        "corpus_path": CORPUS_PATH,
        "pdf_manuali_path": PDF_MANUALI_PATH,
        "chroma_path": CHROMA_PATH,
        "model": EMBEDDING_MODEL,
        "pdf_files": pdf_files,
    }


# ─── Indicizzazione ───────────────────────────────────────────────────────────

@app.post("/index-all")
async def index_all_sse():
    """
    Indicizza tutti i PDF con SSE progress stream.
    Il client riceve linee di testo una alla volta.
    """
    async def generate() -> AsyncGenerator[str, None]:
        messages = []

        def callback(msg: str):
            messages.append(msg)

        loop = asyncio.get_event_loop()

        yield f"data: {json.dumps({'type': 'start', 'msg': 'Avvio indicizzazione completa...'})}\n\n"

        # Esegui in thread per non bloccare l'event loop
        results = await loop.run_in_executor(
            None,
            lambda: index_all_corpus(progress_callback=callback)
        )

        # Invia i messaggi raccolti
        for msg in messages:
            yield f"data: {json.dumps({'type': 'progress', 'msg': msg})}\n\n"

        # Risultati
        for filename, result in results.items():
            if result.get("skipped"):
                status_msg = f"⏭ {filename}: saltato ({result.get('reason', '')})"
            else:
                status_msg = f"✅ {filename}: {result.get('chunks', 0)} chunk"
            yield f"data: {json.dumps({'type': 'result', 'msg': status_msg, 'file': filename, **result})}\n\n"

        # Stats finali
        final_stats = get_index_stats()
        yield f"data: {json.dumps({'type': 'done', 'msg': 'Indicizzazione completata!', 'stats': final_stats})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/index-file")
async def index_file(body: dict):
    """Indicizza un singolo file dal corpus."""
    filename = body.get("filename")
    if not filename:
        raise HTTPException(400, "filename richiesto")

    # Cerca il file in CORPUS_PATH
    found_path = None
    if os.path.exists(CORPUS_PATH):
        for root, _, files in os.walk(CORPUS_PATH):
            if filename in files:
                found_path = os.path.join(root, filename)
                break

    if not found_path:
        raise HTTPException(404, f"File non trovato in corpus: {filename}")

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: index_document(found_path))
    return {"file": filename, **result}


# ─── Upload PDF ───────────────────────────────────────────────────────────────

@app.post("/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    subfolder: str = "quaderni_inail",
):
    """
    Carica un PDF nel corpus locale e lo indicizza.
    subfolder: "quaderni_inail" | "normativa"
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Solo file PDF")

    dest_dir = os.path.join(CORPUS_PATH, subfolder)
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, file.filename)

    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: index_document(dest_path))
    return {"file": file.filename, "saved_to": dest_path, **result}


# ─── Export ChromaDB ZIP ──────────────────────────────────────────────────────

@app.get("/export-zip")
async def export_zip():
    """
    Genera e scarica un archivio ZIP del ChromaDB per upload su Render.
    Il file si chiama chroma_db.zip.
    """
    if not os.path.exists(CHROMA_PATH):
        raise HTTPException(404, "ChromaDB non trovato. Indicizza almeno un documento prima.")

    def generate_zip():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            chroma_dir = Path(CHROMA_PATH)
            for file_path in chroma_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(chroma_dir.parent).as_posix()
                    zf.write(file_path, arcname)
        buf.seek(0)
        return buf.read()

    loop = asyncio.get_event_loop()
    zip_bytes = await loop.run_in_executor(None, generate_zip)

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=chroma_db.zip"},
    )


# ─── Apertura cartella ────────────────────────────────────────────────────────

@app.post("/open-corpus-folder")
async def open_corpus_folder():
    """Apre la cartella corpus/raw/ in Explorer (Windows) o Finder (Mac)."""
    os.makedirs(CORPUS_PATH, exist_ok=True)
    if sys.platform == "win32":
        subprocess.Popen(["explorer", CORPUS_PATH])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", CORPUS_PATH])
    else:
        subprocess.Popen(["xdg-open", CORPUS_PATH])
    return {"opened": CORPUS_PATH}


# ─── Statistiche ─────────────────────────────────────────────────────────────

@app.get("/stats")
async def stats():
    return get_index_stats()
