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

# Render fornisce $PORT automaticamente (default 10000)
# uvicorn legge la porta dalla variabile d'ambiente
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
