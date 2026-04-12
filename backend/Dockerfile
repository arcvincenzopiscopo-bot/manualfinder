# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# Dipendenze di sistema:
# - tesseract-ocr + lingue: OCR fallback quando Claude/Gemini non sono disponibili
# - libgl1 + libglib2.0-0: richieste da Pillow per image processing
# - build-essential + cmake: necessari per compilare chroma-hnswlib (dipendenza C++ di chromadb)
#   Vengono rimossi dopo pip install per mantenere l'immagine leggera.
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

# Cache pip tra build successivi (BuildKit) — evita re-download se requirements.txt non cambia.
# Dopo l'install, rimuove build-essential e cmake per ridurre la dimensione dell'immagine.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

COPY . .

# NOTA: il ChromaDB index (corpus/chroma_db/) NON viene costruito qui.
# Viene costruito al primo avvio del server (on_startup) se non presente.
# Motivo: i binari HNSW non sono portabili tra Windows e Linux — se committati da Windows
# verrebbero rifiutati su Render. Costruire a startup è più veloce del build e non blocca il deploy.

# Render fornisce $PORT automaticamente (default 10000)
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
