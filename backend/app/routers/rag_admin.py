"""
Router admin per la gestione del corpus RAG su Render.

Endpoint:
  GET  /rag/stats                → statistiche corpus
  POST /rag/upload-and-index     → upload PDF + indicizzazione immediata (MiniLM)
  POST /rag/upload-chroma        → upload ZIP del ChromaDB pre-indicizzato in locale
  DELETE /rag/document/{filename} → rimuove documento dal vettore store
  POST /rag/reindex/{filename}   → re-indicizza documento specifico
  POST /rag/index-all            → re-indicizza tutto il corpus su Render (MiniLM)

Auth: nessuna autenticazione (coerente con gli altri endpoint admin del progetto).
"""
import os
import shutil
import zipfile
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services import corpus_indexer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG Admin"])


@router.get("/stats")
def get_stats():
    """Statistiche corpus indicizzato: chunk totali, fonti presenti."""
    return corpus_indexer.get_index_stats()


@router.post("/upload-and-index")
async def upload_and_index(
    file: UploadFile = File(...),
    subfolder: str = "quaderni_inail",
):
    """
    Carica un PDF nel corpus e lo indicizza immediatamente con MiniLM.
    Usa per aggiornamenti rapidi. Per qualità ottimale: indicizza in locale
    con la GUI e carica il DB con /upload-chroma.

    subfolder: "quaderni_inail" | "normativa"
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Solo file PDF (.pdf)")

    dest_dir = os.path.join(corpus_indexer.CORPUS_PATH, subfolder)
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, file.filename)

    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    result = corpus_indexer.index_document(dest_path)
    return {"file": file.filename, "saved_to": dest_path, **result}


@router.post("/upload-chroma")
async def upload_chroma_db(file: UploadFile = File(...)):
    """
    Carica il ChromaDB pre-indicizzato in locale (ZIP).

    Il file ZIP deve contenere la cartella chroma_db/ con chroma.sqlite3
    e le sottocartelle degli indici HNSW.
    Sostituisce integralmente il DB esistente su Render.
    Invalida automaticamente la cache in memoria.

    Processo:
      1. Salva il ZIP in una directory temporanea
      2. Backup del DB esistente
      3. Estrae il ZIP sovrascrivendo il DB
      4. Ripristina il backup se qualcosa va storto
    """
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Il file deve essere uno ZIP (chroma_db.zip)")

    chroma_path = corpus_indexer.CHROMA_PATH
    backup_path = chroma_path + "_backup"
    tmp_zip = os.path.join(os.path.dirname(chroma_path), "_upload_tmp.zip")

    os.makedirs(os.path.dirname(chroma_path), exist_ok=True)

    content = await file.read()
    with open(tmp_zip, "wb") as f:
        f.write(content)

    # Backup del DB esistente
    if os.path.exists(chroma_path):
        try:
            if os.path.exists(backup_path):
                shutil.rmtree(backup_path)
            shutil.copytree(chroma_path, backup_path)
        except Exception as e:
            logger.warning("Backup ChromaDB fallito: %s", e)

    try:
        # Estrai ZIP
        with zipfile.ZipFile(tmp_zip, "r") as z:
            # Lo ZIP deve contenere chroma_db/ come directory root
            extract_to = os.path.dirname(chroma_path)
            z.extractall(extract_to)

        os.remove(tmp_zip)

        # Invalida cache in memoria
        try:
            from app.services import rag_service
            rag_service.invalidate_cache()
        except Exception:
            pass

        stats = corpus_indexer.get_index_stats()
        logger.info("ChromaDB caricato da ZIP: %d chunk, %d fonti",
                    stats.get("total_chunks", 0), len(stats.get("fonti", [])))
        return {"ok": True, "stats": stats}

    except Exception as e:
        logger.error("Errore upload ChromaDB: %s", e)
        # Ripristina backup
        if os.path.exists(backup_path):
            try:
                if os.path.exists(chroma_path):
                    shutil.rmtree(chroma_path)
                shutil.copytree(backup_path, chroma_path)
                logger.info("ChromaDB ripristinato dal backup")
            except Exception as restore_err:
                logger.error("Ripristino backup fallito: %s", restore_err)
        if os.path.exists(tmp_zip):
            os.remove(tmp_zip)
        raise HTTPException(500, f"Errore durante l'upload: {str(e)}")

    finally:
        if os.path.exists(backup_path):
            try:
                shutil.rmtree(backup_path)
            except Exception:
                pass


@router.delete("/document/{filename}")
def delete_document(filename: str):
    """Rimuove un documento dal vettore store ChromaDB."""
    collection = corpus_indexer.get_collection()
    if collection is None:
        raise HTTPException(503, "ChromaDB non disponibile")
    try:
        collection.delete(where={"filename": filename})
        # Invalida cache
        try:
            from app.services import rag_service
            rag_service.invalidate_cache()
        except Exception:
            pass
        return {"deleted": filename, "ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/reindex/{filename}")
def reindex_document(filename: str):
    """
    Re-indicizza un documento specifico del corpus.
    Prima cancella il documento esistente, poi lo re-indicizza.
    """
    collection = corpus_indexer.get_collection()
    if collection is None:
        raise HTTPException(503, "ChromaDB non disponibile")

    # Rimuovi versione esistente
    try:
        collection.delete(where={"filename": filename})
    except Exception:
        pass

    # Trova il file
    found_path = None
    if os.path.exists(corpus_indexer.CORPUS_PATH):
        for root, _, files in os.walk(corpus_indexer.CORPUS_PATH):
            if filename in files:
                found_path = os.path.join(root, filename)
                break

    if not found_path:
        raise HTTPException(404, f"File non trovato nel corpus: {filename}")

    result = corpus_indexer.index_document(found_path)

    # Invalida cache
    try:
        from app.services import rag_service
        rag_service.invalidate_cache()
    except Exception:
        pass

    return {"file": filename, **result}


@router.post("/cleanup-orphans")
def cleanup_orphans():
    """
    Rimuove da ChromaDB i chunk di PDF non più presenti su disco.
    Utile dopo aver eliminato file dal corpus manualmente.
    """
    result = corpus_indexer.cleanup_orphaned_documents()
    if result.get("error"):
        raise HTTPException(500, result["error"])
    return result


@router.post("/index-all")
def index_all():
    """
    Re-indicizza tutto il corpus su Render con MiniLM.
    Usa per sincronizzare dopo aver aggiunto nuovi PDF tramite upload-and-index.
    Per qualità ottimale: indicizza in locale con la GUI.
    """
    if not os.path.exists(corpus_indexer.CORPUS_PATH):
        raise HTTPException(404, f"Corpus path non trovato: {corpus_indexer.CORPUS_PATH}")

    results = corpus_indexer.index_all_corpus()

    # Invalida cache
    try:
        from app.services import rag_service
        rag_service.invalidate_cache()
    except Exception:
        pass

    total_new = sum(r.get("chunks", 0) for r in results.values() if not r.get("skipped"))
    total_skip = sum(1 for r in results.values() if r.get("skipped"))
    stats = corpus_indexer.get_index_stats()

    return {
        "results": results,
        "summary": {
            "files_processed": len(results) - total_skip,
            "files_skipped": total_skip,
            "new_chunks": total_new,
            "total_chunks": stats.get("total_chunks", 0),
        },
    }
