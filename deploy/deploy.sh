#!/usr/bin/env bash
# =============================================================================
# ManualFinder — Deploy aggiornamento
# Esegui sulla VM Oracle ogni volta che aggiorni il codice:
#   bash deploy.sh
#
# Assume che setup.sh sia già stato eseguito.
# =============================================================================
set -euo pipefail

APP_DIR="/opt/manualfinder"
PYTHON="python3.12"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERR]${NC}   $*"; exit 1; }

[[ -d "$APP_DIR" ]] || error "APP_DIR $APP_DIR non esiste — esegui prima setup.sh"

cd "$APP_DIR/backend"

# ── 1. Aggiorna dipendenze Python (solo se requirements.txt cambiato) ─────────
info "1/4 Aggiornamento dipendenze Python..."
.venv/bin/pip install -r requirements.txt -q
info "  OK"

# ── 2. Rigenera ChromaDB se il corpus è cambiato ─────────────────────────────
CORPUS_HASH_FILE="$APP_DIR/.corpus_hash"
CORPUS_HASH_NOW=$(find corpus/ -type f -name "*.txt" -o -name "*.pdf" 2>/dev/null | sort | xargs md5sum 2>/dev/null | md5sum | cut -d' ' -f1 || echo "empty")
CORPUS_HASH_OLD=$(cat "$CORPUS_HASH_FILE" 2>/dev/null || echo "")

if [[ "$CORPUS_HASH_NOW" != "$CORPUS_HASH_OLD" ]]; then
    info "2/4 Corpus cambiato — rigenero indice ChromaDB..."
    .venv/bin/python -c "
import sys; sys.path.insert(0, '.')
try:
    from app.services.corpus_indexer import index_all_corpus
    results = index_all_corpus()
    total = sum(r.get('chunks', 0) for r in results.values() if not r.get('skipped'))
    print(f'ChromaDB: {total} chunk indicizzati')
except Exception as e:
    print(f'ChromaDB saltato: {e}')
"
    echo "$CORPUS_HASH_NOW" > "$CORPUS_HASH_FILE"
else
    info "2/4 Corpus invariato — ChromaDB non rigenerato"
fi

# ── 3. Riavvio servizio ───────────────────────────────────────────────────────
info "3/4 Riavvio servizio manualfinder..."
sudo systemctl restart manualfinder
sleep 3

if sudo systemctl is-active --quiet manualfinder; then
    info "  Servizio attivo"
else
    error "  Servizio non avviato — controlla: journalctl -u manualfinder -n 50"
fi

# ── 4. Reload nginx (configurazione potrebbe essere cambiata) ─────────────────
info "4/4 Reload nginx..."
sudo nginx -t && sudo systemctl reload nginx
info "  OK"

echo ""
echo -e "${GREEN}Deploy completato.${NC}"
echo -e "  Log live: tail -f /opt/manualfinder/logs/app.log"
