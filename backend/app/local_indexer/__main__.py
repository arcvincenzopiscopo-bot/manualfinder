"""
Entry point GUI locale per indicizzazione corpus RAG.

Uso:
    cd backend
    python -m app.local_indexer

Apre automaticamente http://localhost:7777 nel browser di sistema.
Gira SOLO in locale — non viene mai deployato su Render.

Requisiti (installare con):
    pip install -r requirements-local.txt
"""
import sys
import os
import time
import threading
import webbrowser
from pathlib import Path

# Assicura backend/ nel sys.path
_BACKEND_ROOT = Path(__file__).parent.parent.parent  # backend/
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def _check_deps():
    """Verifica che le dipendenze necessarie siano installate."""
    missing = []
    for pkg in ["chromadb", "sentence_transformers", "fitz", "fastapi", "uvicorn"]:
        try:
            __import__(pkg)
        except ImportError:
            friendly = {
                "fitz": "PyMuPDF",
                "sentence_transformers": "sentence-transformers",
            }.get(pkg, pkg)
            missing.append(friendly)

    if missing:
        print("\n❌ Dipendenze mancanti:")
        for dep in missing:
            print(f"   - {dep}")
        print("\nInstalla con:")
        print("   pip install -r requirements-local.txt")
        print("\nSe requirements-local.txt non esiste:")
        reqs = " ".join([
            "chromadb==0.5.0",
            "sentence-transformers==3.0.0",
            "langchain-text-splitters==0.2.0",
            "fastapi",
            "uvicorn[standard]",
        ])
        print(f"   pip install {reqs}")
        sys.exit(1)


def _open_browser(url: str, delay: float = 1.5):
    """Apre il browser dopo un breve ritardo (attende che il server sia pronto)."""
    def _open():
        time.sleep(delay)
        webbrowser.open(url)
    t = threading.Thread(target=_open, daemon=True)
    t.start()


def main():
    _check_deps()

    import uvicorn
    from app.local_indexer.server import app

    HOST = "127.0.0.1"
    PORT = 7777
    URL = f"http://{HOST}:{PORT}"

    print("\n" + "═" * 55)
    print("  RAG Local Indexer — ManualFinder")
    print("═" * 55)
    print(f"  Server: {URL}")
    print("  Premi Ctrl+C per fermare")
    print("═" * 55 + "\n")

    _open_browser(URL)

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="warning",  # silenzioso — l'output è nella UI
    )


if __name__ == "__main__":
    main()
