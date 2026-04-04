# Avvio in sviluppo locale

## 1. Backend (Python/FastAPI)

```bash
cd backend

# Crea e attiva l'ambiente virtuale
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

# Installa dipendenze
pip install -r requirements.txt

# Configura le variabili d'ambiente
copy ..\\.env.example .env
# Apri .env e inserisci almeno ANTHROPIC_API_KEY o GEMINI_API_KEY

# Avvia il server
uvicorn app.main:app --reload --port 8000
```

Il backend sarà disponibile su http://localhost:8000  
Documentazione API interattiva: http://localhost:8000/docs

---

## 2. Frontend (React/Vite)

```bash
cd frontend

# Installa dipendenze
npm install

# Avvia il dev server
npm run dev
```

L'app sarà disponibile su http://localhost:5173

Il proxy Vite reindirizza automaticamente `/api/*` → `http://localhost:8000/*`

---

## 3. Test rapido dell'integrazione

1. Apri http://localhost:5173 sul browser
2. Fotografa o carica l'immagine di una targa
3. Premi "Analizza"
4. Verifica che i 5 step progrediscano in tempo reale
5. Controlla la scheda di sicurezza generata

---

## Provider disponibili

| Funzione | Senza API key | Con GEMINI_API_KEY | Con ANTHROPIC_API_KEY |
|---|---|---|---|
| OCR targa | Tesseract (locale, scarso) | Gemini Flash (buono) | Claude (ottimo) |
| Ricerca | DuckDuckGo (instabile) | Brave/CSE | Perplexity |
| Analisi PDF | Non disponibile | Gemini Flash | Claude |

**Consiglio minimo**: inserisci almeno `GEMINI_API_KEY` per avere un'esperienza funzionale gratuitamente.

---

## Deploy in produzione

**Backend su Railway:**
1. Crea account su railway.app
2. "New Project" → "Deploy from GitHub repo" → seleziona `backend/`
3. Aggiungi le variabili d'ambiente dal pannello Railway
4. Railway usa automaticamente `railway.toml` per la configurazione

**Frontend su Vercel:**
1. Crea account su vercel.com
2. "Add New Project" → importa da GitHub → seleziona `frontend/`
3. Imposta `VITE_API_BASE_URL` nelle env vars di Vercel con l'URL del backend Railway
4. Vercel usa automaticamente `vercel.json` per il routing PWA
