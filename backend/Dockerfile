# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# Dipendenze di sistema:
# - tesseract-ocr + lingue: OCR fallback quando Claude/Gemini non sono disponibili
# - libgl1 + libglib2.0-0: richieste da Pillow per image processing
# - build-essential + cmake: necessari per compilare chroma-hnswlib (dipendenza C++ di chromadb)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-ita \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Cache pip tra build successivi (BuildKit) — evita re-download/re-compilazione
# di chroma-hnswlib se requirements.txt non cambia.
# Dopo l'install rimuove build-essential e cmake per ridurre la dimensione dell'immagine.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

COPY . .

# Genera il ChromaDB su Linux durante la build (non a runtime).
# Motivo: i binari HNSW di chroma-hnswlib non sono portabili tra Windows e Linux.
#         A runtime non si può rigenerare (OOM sul piano free da 512MB).
# Il modello ONNX (all-MiniLM-L6-v2, ~30MB) viene scaricato qui e rimane nell'immagine.
RUN RENDER=1 python -c "\
import sys; sys.path.insert(0, '/app'); \
from app.services.corpus_indexer import index_all_corpus; \
results = index_all_corpus(); \
total = sum(r.get('chunks', 0) for r in results.values() if not r.get('skipped')); \
skipped = sum(1 for r in results.values() if r.get('skipped')); \
print(f'ChromaDB build: {len(results)-skipped} file, {total} chunk ({skipped} saltati)') \
"

# Render fornisce $PORT automaticamente (default 10000)
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
