"""
CLI per indicizzazione offline del corpus normativo.

Alternativa testuale alla GUI locale (app.local_indexer).
Utile per automazione o ambienti senza browser.

USO:
    cd backend
    python -m app.scripts.index_corpus              # indicizza tutto
    python -m app.scripts.index_corpus --file nome.pdf  # un solo file
    python -m app.scripts.index_corpus --stats      # solo statistiche

REQUISITI (solo in locale, non su Render):
    pip install -r requirements-local.txt

NOTE:
    - Usa lo stesso modello MiniLM di Render → zero mismatch embedding
    - Prima esecuzione: scarica il modello (~120MB), poi lo mette in cache
    - Tempo stimato: 5-15 min per 300 pagine totali
    - Gli embeddings vengono salvati in corpus/chroma_db/
    - Caricare corpus/chroma_db/ su Render dopo ogni aggiornamento
      tramite admin panel → tab Corpus → "Carica DB pre-indicizzato"
"""
import argparse
import sys
import os
import time
from pathlib import Path

# Assicura backend/ nel sys.path
_BACKEND_ROOT = Path(__file__).parent.parent.parent  # backend/
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def main():
    parser = argparse.ArgumentParser(
        description="Indicizzazione corpus normativo RAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--file", help="Indicizza un solo file (nome o path)")
    parser.add_argument("--stats", action="store_true", help="Mostra statistiche corpus")
    args = parser.parse_args()

    # Import dopo aver verificato sys.path
    try:
        from app.services.corpus_indexer import (
            index_all_corpus,
            index_document,
            get_index_stats,
            EMBEDDING_MODEL,
            CORPUS_PATH,
            CHROMA_PATH,
        )
    except ImportError as e:
        print(f"\n❌ Import fallito: {e}")
        print("\nVerifica che le dipendenze siano installate:")
        print("   pip install -r requirements-local.txt")
        sys.exit(1)

    print(f"\n{'═' * 50}")
    print(f"  RAG Corpus Indexer — CLI")
    print(f"{'═' * 50}")
    print(f"  Modello: {EMBEDDING_MODEL}")
    print(f"  Corpus:  {CORPUS_PATH}")
    print(f"  ChromaDB: {CHROMA_PATH}")
    print(f"{'═' * 50}\n")

    if args.stats:
        stats = get_index_stats()
        print(f"📊 Corpus indicizzato:")
        print(f"   Chunks totali: {stats['total_chunks']}")
        fonti = stats.get('fonti', [])
        if fonti:
            print(f"   Fonti ({len(fonti)}):")
            for f in fonti:
                print(f"     - {f['fonte']} ({f['tipo']})")
        else:
            print("   Fonti: nessuna")
        return

    def progress(msg: str):
        print(f"  {msg}")

    if args.file:
        # Cerca il file in CORPUS_PATH se non è un path assoluto
        path = None
        if os.path.isabs(args.file) and os.path.exists(args.file):
            path = args.file
        else:
            if os.path.exists(CORPUS_PATH):
                for root, _, files in os.walk(CORPUS_PATH):
                    if args.file in files:
                        path = os.path.join(root, args.file)
                        break

        if not path:
            print(f"❌ File non trovato: {args.file}")
            print(f"   Cercato in: {CORPUS_PATH}")
            sys.exit(1)

        print(f"📄 Indicizzazione: {args.file}")
        start = time.time()
        result = index_document(path, progress_callback=progress)
        elapsed = time.time() - start

        if result.get("skipped"):
            print(f"⏭  Saltato: {result.get('reason', 'già presente')}")
        else:
            print(f"✅ {result.get('chunks', 0)} chunk indicizzati in {elapsed:.1f}s")

    else:
        if not os.path.exists(CORPUS_PATH):
            print(f"❌ Cartella corpus non trovata: {CORPUS_PATH}")
            print(f"\nCrea la struttura:")
            print(f"   {CORPUS_PATH}/normativa/        ← Direttiva Macchine PDF")
            print(f"   {CORPUS_PATH}/quaderni_inail/   ← Schede INAIL PDF")
            sys.exit(1)

        print("🚀 Avvio indicizzazione completa...\n")
        start = time.time()
        results = index_all_corpus(progress_callback=progress)
        elapsed = time.time() - start

        total_chunks = 0
        skipped = 0
        for filename, result in results.items():
            if result.get("skipped"):
                print(f"⏭  {filename}: saltato ({result.get('reason', '')})")
                skipped += 1
            else:
                n = result.get("chunks", 0)
                print(f"✅ {filename}: {n} chunk")
                total_chunks += n

        print(f"\n{'─' * 50}")
        print(f"📊 Completato in {elapsed:.1f}s")
        print(f"   File processati: {len(results) - skipped}")
        print(f"   File saltati: {skipped}")
        print(f"   Chunk nuovi: {total_chunks}")

        stats = get_index_stats()
        print(f"   Chunk totali nel DB: {stats['total_chunks']}")

    print(f"\n💾 ChromaDB in: {CHROMA_PATH}")
    print("   → Esporta con la GUI locale (python -m app.local_indexer)")
    print("   → Oppure comprimi manualmente e carica nel pannello admin\n")


if __name__ == "__main__":
    main()
