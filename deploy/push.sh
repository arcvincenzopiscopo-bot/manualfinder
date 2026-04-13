#!/usr/bin/env bash
# =============================================================================
# ManualFinder — Push locale → Oracle VM
# Esegui dalla tua macchina Windows (Git Bash / WSL):
#
#   Prima volta:
#     export ORACLE_IP="<IP_PUBBLICO_VM>"
#     export ORACLE_KEY="C:/Users/ARCVI/.ssh/oracle_key.pem"
#     bash deploy/push.sh --setup
#
#   Deploy successivi (solo codice):
#     bash deploy/push.sh
#
#   Copia solo i PDF INAIL locali:
#     bash deploy/push.sh --pdfs
# =============================================================================
set -euo pipefail

# ── Configurazione — modifica questi valori ───────────────────────────────────
ORACLE_IP="${ORACLE_IP:-}"
ORACLE_USER="ubuntu"
ORACLE_KEY="${ORACLE_KEY:-}"           # percorso al file .pem scaricato da Oracle
ORACLE_APP_DIR="/opt/manualfinder"
LOCAL_PDF_DIR="backend/pdf manuali"   # directory PDF locali INAIL (con spazio)
LOCAL_UPLOADS_DIR="backend/manuali_locali"
DOMAIN="${DOMAIN:-}"                   # es. api.tuodominio.com
# ─────────────────────────────────────────────────────────────────────────────

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERR]${NC}   $*"; exit 1; }

# Validazione
[[ -n "$ORACLE_IP" ]]  || error "Imposta ORACLE_IP: export ORACLE_IP=\"<IP>\""
[[ -n "$ORACLE_KEY" ]] || error "Imposta ORACLE_KEY: export ORACLE_KEY=\"/path/to/key.pem\""
[[ -f "$ORACLE_KEY" ]] || error "File chiave non trovato: $ORACLE_KEY"

# Permessi chiave (richiesti da ssh)
chmod 600 "$ORACLE_KEY"

SSH="ssh -i $ORACLE_KEY -o StrictHostKeyChecking=accept-new $ORACLE_USER@$ORACLE_IP"
SCP="scp -i $ORACLE_KEY -o StrictHostKeyChecking=accept-new"
RSYNC="rsync -avz --progress -e \"ssh -i $ORACLE_KEY -o StrictHostKeyChecking=accept-new\""

MODE="${1:-}"

# ── Modalità --pdfs: solo i PDF INAIL locali ─────────────────────────────────
if [[ "$MODE" == "--pdfs" ]]; then
    info "Copia PDF locali INAIL → Oracle VM..."
    if [[ -d "$LOCAL_PDF_DIR" ]]; then
        PDF_COUNT=$(find "$LOCAL_PDF_DIR" -name "*.pdf" | wc -l)
        info "  $PDF_COUNT PDF trovati in '$LOCAL_PDF_DIR'"
        rsync -avz --progress \
            -e "ssh -i $ORACLE_KEY -o StrictHostKeyChecking=accept-new" \
            "$LOCAL_PDF_DIR/" \
            "$ORACLE_USER@$ORACLE_IP:$ORACLE_APP_DIR/backend/pdf manuali/"
        info "  PDF copiati"
    else
        warn "  Directory '$LOCAL_PDF_DIR' non trovata — skip"
    fi
    if [[ -d "$LOCAL_UPLOADS_DIR" ]]; then
        rsync -avz --progress \
            -e "ssh -i $ORACLE_KEY -o StrictHostKeyChecking=accept-new" \
            "$LOCAL_UPLOADS_DIR/" \
            "$ORACLE_USER@$ORACLE_IP:$ORACLE_APP_DIR/backend/manuali_locali/"
        info "  Manuali caricati copiati"
    fi
    exit 0
fi

# ── Validazione .env ──────────────────────────────────────────────────────────
[[ -f "deploy/.env" ]] || error "deploy/.env non trovato — copia deploy/.env.template in deploy/.env e compila le variabili"

# ── 1. Sincronizza codice backend ─────────────────────────────────────────────
info "1/5 Sincronizzazione codice backend..."
rsync -avz --progress \
    -e "ssh -i $ORACLE_KEY -o StrictHostKeyChecking=accept-new" \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='pdf manuali/' \
    --exclude='manuali_locali/' \
    --exclude='chroma_db/' \
    --exclude='*.log' \
    --exclude='.pytest_cache' \
    backend/ \
    "$ORACLE_USER@$ORACLE_IP:$ORACLE_APP_DIR/backend/"
info "  Backend sincronizzato"

# ── 2. Sincronizza corpus normativo ───────────────────────────────────────────
info "2/5 Sincronizzazione corpus normativo..."
if [[ -d "backend/corpus" ]]; then
    rsync -avz --progress \
        -e "ssh -i $ORACLE_KEY -o StrictHostKeyChecking=accept-new" \
        backend/corpus/ \
        "$ORACLE_USER@$ORACLE_IP:$ORACLE_APP_DIR/backend/corpus/"
fi

# ── 3. Copia .env ─────────────────────────────────────────────────────────────
info "3/5 Copia .env..."
$SCP deploy/.env "$ORACLE_USER@$ORACLE_IP:$ORACLE_APP_DIR/backend/.env"
$SSH "chmod 600 $ORACLE_APP_DIR/backend/.env"

# ── 4. Prima esecuzione: setup completo ──────────────────────────────────────
if [[ "$MODE" == "--setup" ]]; then
    info "4/5 Prima installazione — copia e avvio setup.sh..."
    $SCP deploy/setup.sh "$ORACLE_USER@$ORACLE_IP:/tmp/setup.sh"
    $SSH "chmod +x /tmp/setup.sh"

    if [[ -n "$DOMAIN" ]]; then
        $SSH "export DOMAIN='$DOMAIN'; bash /tmp/setup.sh"
    else
        $SSH "bash /tmp/setup.sh"
    fi

    info "5/5 Setup completato. Copia PDF INAIL locali..."
    bash deploy/push.sh --pdfs

    echo ""
    echo -e "${GREEN}Prima installazione completata!${NC}"
    echo -e "  Testa: curl http://$ORACLE_IP/api/machine-types"
    exit 0
fi

# ── 5. Deploy aggiornamento ───────────────────────────────────────────────────
info "4/5 Avvio deploy aggiornamento sulla VM..."
$SCP deploy/deploy.sh "$ORACLE_USER@$ORACLE_IP:/tmp/deploy.sh"
$SSH "chmod +x /tmp/deploy.sh && bash /tmp/deploy.sh"
info "5/5 Deploy completato"

echo ""
echo -e "${GREEN}Aggiornamento completato.${NC}"
echo -e "  Log: ssh -i $ORACLE_KEY $ORACLE_USER@$ORACLE_IP 'tail -f /opt/manualfinder/logs/app.log'"
