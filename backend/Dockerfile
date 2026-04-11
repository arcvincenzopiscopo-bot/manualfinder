FROM python:3.12-slim

WORKDIR /app

# Dipendenze di sistema:
# - tesseract-ocr + lingue: OCR fallback (Livello 3) quando Claude/Gemini non sono disponibili
# - libgl1: richiesta da Pillow per alcune operazioni di image processing
# - libglib2.0-0: dipendenza runtime di Pillow
# Non serve libmupdf-dev: PyMuPDF >= 1.24 usa wheels binari con MuPDF incorporato
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-ita \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# build-essential + cmake necessari per compilare chroma-hnswlib (dipendenza C++ di chromadb).
# Vengono rimossi dopo pip install per mantenere l'immagine leggera.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

COPY . .

# Genera il ChromaDB su Linux direttamente durante la build.
# Motivo: i file binari HNSW di chroma-hnswlib non sono portabili tra Windows e Linux —
# se committassimo i .bin generati su Windows, Render li rifiuterebbe e vedrebbe 0 chunk.
# Soluzione: ignoriamo corpus/chroma_db/ in git e lo ricostruiamo qui su Linux,
# indicizzando i PDF di "pdf manuali/" (git-tracked, le 22 schede INAIL).
# Il modello ONNX viene scaricato al primo uso e rimane nell'immagine.
RUN cd /app/backend && python -c "\
import sys; sys.path.insert(0, '/app/backend'); \
from app.services.corpus_indexer import index_all_corpus; \
results = index_all_corpus(); \
total = sum(r.get('chunks', 0) for r in results.values() if not r.get('skipped')); \
skipped = sum(1 for r in results.values() if r.get('skipped')); \
print(f'ChromaDB build: {len(results)-skipped} file, {total} chunk ({skipped} saltati)') \
"

# Render fornisce $PORT automaticamente (default 10000)
# uvicorn legge la porta dalla variabile d'ambiente
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
