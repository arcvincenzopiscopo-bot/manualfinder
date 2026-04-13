#!/usr/bin/env bash
# =============================================================================
# ManualFinder — Oracle Cloud VM Setup
# Esegui UNA SOLA VOLTA sulla VM Oracle appena creata:
#   bash setup.sh
#
# Prerequisiti:
#   - Ubuntu 22.04 ARM (Ampere A1, raccomandato: 4 OCPU 24GB RAM)
#   - File .env presente nella stessa cartella di questo script
#   - Variabile DOMAIN impostata (o lascia vuota per usare solo l'IP)
#
# Uso:
#   export DOMAIN="api.tuodominio.com"   # opzionale, per SSL automatico
#   bash setup.sh
# =============================================================================
set -euo pipefail

# ── Configurazione ────────────────────────────────────────────────────────────
APP_DIR="/opt/manualfinder"
APP_USER="ubuntu"
PYTHON="python3.12"
REPO_URL=""          # lascia vuoto se carichi il codice con push.sh invece di git
DOMAIN="${DOMAIN:-}"  # es. api.tuodominio.com  — vuoto = usa solo IP senza SSL
PORT_INTERNAL=8000

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERR]${NC}   $*"; exit 1; }

# ── Controllo .env ────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
    error ".env non trovato in $SCRIPT_DIR — copia .env.template in .env e compila le variabili"
fi

# ── 1. Aggiornamento sistema ──────────────────────────────────────────────────
info "1/9 Aggiornamento pacchetti di sistema..."
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -qq

# ── 2. Dipendenze di sistema ─────────────────────────────────────────────────
info "2/9 Installazione dipendenze di sistema..."
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    software-properties-common curl git unzip \
    nginx certbot python3-certbot-nginx \
    iptables-persistent netfilter-persistent \
    tesseract-ocr tesseract-ocr-ita tesseract-ocr-eng \
    libgl1 libglib2.0-0 \
    libzbar0 libzbar-dev \
    libdmtx-dev \
    build-essential cmake \
    python3-pip

# Python 3.12 via deadsnakes PPA (Ubuntu 22.04 ha solo 3.10 nativa)
if ! command -v python3.12 &>/dev/null; then
    info "  → Installazione Python 3.12..."
    sudo add-apt-repository ppa:deadsnakes/ppa -y
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        python3.12 python3.12-venv python3.12-dev
fi

info "  Python: $(python3.12 --version)"

# ── 3. Firewall (il passo insidioso di Oracle) ──────────────────────────────
info "3/9 Configurazione firewall Oracle (iptables)..."
# Oracle Ubuntu ha iptables DROP di default su INPUT — va aperto esplicitamente
sudo iptables -C INPUT -p tcp --dport 80  -j ACCEPT 2>/dev/null || sudo iptables -I INPUT -p tcp --dport 80  -j ACCEPT
sudo iptables -C INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -C INPUT -p tcp --dport 22  -j ACCEPT 2>/dev/null || sudo iptables -I INPUT -p tcp --dport 22  -j ACCEPT
sudo netfilter-persistent save
info "  Regole iptables salvate (persistent al reboot)"

# ── 4. Struttura directory ────────────────────────────────────────────────────
info "4/9 Struttura directory applicazione..."
sudo mkdir -p "$APP_DIR"
sudo chown "$APP_USER:$APP_USER" "$APP_DIR"

# Clona il repo se REPO_URL è impostato, altrimenti la struttura verrà copiata da push.sh
if [[ -n "$REPO_URL" ]]; then
    if [[ ! -d "$APP_DIR/.git" ]]; then
        git clone "$REPO_URL" "$APP_DIR"
    else
        git -C "$APP_DIR" pull
    fi
else
    warn "  REPO_URL non impostato — usa push.sh per copiare il codice"
    mkdir -p "$APP_DIR/backend"
    mkdir -p "$APP_DIR/frontend"
fi

# Directory dati persistenti (non sovrascritta dai deploy)
mkdir -p "$APP_DIR/backend/pdf manuali"
mkdir -p "$APP_DIR/backend/manuali_locali"
mkdir -p "$APP_DIR/backend/corpus"
mkdir -p "$APP_DIR/logs"

# ── 5. Variabili d'ambiente ───────────────────────────────────────────────────
info "5/9 Installazione file .env..."
cp "$SCRIPT_DIR/.env" "$APP_DIR/backend/.env"
chmod 600 "$APP_DIR/backend/.env"

# ── 6. Virtualenv e dipendenze Python ────────────────────────────────────────
info "6/9 Creazione virtualenv e installazione dipendenze Python..."
cd "$APP_DIR/backend"

if [[ ! -d ".venv" ]]; then
    $PYTHON -m venv .venv
fi

# Aggiorna pip silenziosamente, poi installa requirements
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q

info "  Dipendenze installate"

# ── 7. Pre-build ChromaDB ─────────────────────────────────────────────────────
info "7/9 Pre-build indice ChromaDB RAG (richiede qualche minuto)..."
# Necessario perché i binari HNSW non sono portabili da Windows a Linux
cd "$APP_DIR/backend"
.venv/bin/python -c "
import sys; sys.path.insert(0, '.')
try:
    from app.services.corpus_indexer import index_all_corpus
    results = index_all_corpus()
    total = sum(r.get('chunks', 0) for r in results.values() if not r.get('skipped'))
    skipped = sum(1 for r in results.values() if r.get('skipped'))
    print(f'ChromaDB: {len(results)-skipped} file indicizzati, {total} chunk ({skipped} saltati)')
except Exception as e:
    print(f'ChromaDB build saltato (corpus vuoto o errore): {e}')
"

# ── 8. Systemd service ────────────────────────────────────────────────────────
info "8/9 Configurazione servizio systemd..."
sudo tee /etc/systemd/system/manualfinder.service > /dev/null <<EOF
[Unit]
Description=ManualFinder API (FastAPI/uvicorn)
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR/backend
EnvironmentFile=$APP_DIR/backend/.env
ExecStart=$APP_DIR/backend/.venv/bin/uvicorn app.main:app \\
    --host 127.0.0.1 \\
    --port $PORT_INTERNAL \\
    --workers 2 \\
    --log-level info \\
    --access-log \\
    --log-config /dev/null
StandardOutput=append:$APP_DIR/logs/app.log
StandardError=append:$APP_DIR/logs/app.log
Restart=always
RestartSec=5
KillMode=mixed
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable manualfinder
sudo systemctl start manualfinder
sleep 3

if sudo systemctl is-active --quiet manualfinder; then
    info "  Servizio manualfinder attivo"
else
    error "  Servizio manualfinder non si è avviato — controlla: journalctl -u manualfinder -n 50"
fi

# ── 9. Nginx ──────────────────────────────────────────────────────────────────
info "9/9 Configurazione nginx..."

# Determina server_name: dominio o IP pubblico
if [[ -n "$DOMAIN" ]]; then
    SERVER_NAME="$DOMAIN"
else
    # Recupera IP pubblico automaticamente
    PUBLIC_IP=$(curl -s https://api.ipify.org || curl -s https://ifconfig.me || echo "_")
    SERVER_NAME="$PUBLIC_IP"
    warn "  Nessun dominio impostato — nginx risponderà su IP: $PUBLIC_IP (no SSL)"
fi

sudo tee /etc/nginx/sites-available/manualfinder > /dev/null <<EOF
server {
    listen 80;
    server_name $SERVER_NAME;

    # ── Backend API ──
    location /api/ {
        proxy_pass         http://127.0.0.1:$PORT_INTERNAL;
        proxy_http_version 1.1;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;

        # Critico per SSE (Server-Sent Events)
        proxy_buffering         off;
        proxy_cache             off;
        proxy_read_timeout      180s;
        proxy_connect_timeout   10s;
        chunked_transfer_encoding on;

        # CORS (opzionale se il frontend è su dominio diverso)
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, DELETE, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'Content-Type, X-Admin-Token' always;
        if (\$request_method = 'OPTIONS') {
            return 204;
        }
    }

    # ── File statici PDF (INAIL locali) ──
    location /manuals/local/ {
        alias "$APP_DIR/backend/pdf manuali/";
        add_header Content-Disposition 'inline';
        add_header X-Content-Type-Options nosniff;
    }

    # ── Health check ──
    location /health {
        proxy_pass http://127.0.0.1:$PORT_INTERNAL/health;
        access_log off;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/manualfinder /etc/nginx/sites-enabled/manualfinder
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx

# SSL automatico con certbot (solo se dominio fornito)
if [[ -n "$DOMAIN" ]]; then
    info "  Configurazione SSL per $DOMAIN..."
    warn "  Assicurati che il record DNS A di $DOMAIN punti già a questo IP prima di continuare."
    read -rp "  DNS configurato? Premi INVIO per continuare o Ctrl+C per saltare SSL... "
    sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
        --email "admin@$DOMAIN" --redirect
    info "  SSL configurato — rinnovo automatico attivo"
fi

# ── Riepilogo finale ──────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo -e "${GREEN} ManualFinder installato con successo!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo ""
if [[ -n "$DOMAIN" ]]; then
    echo -e "  API:      https://$DOMAIN/api"
    echo -e "  Health:   https://$DOMAIN/health"
else
    PUBLIC_IP=$(curl -s https://api.ipify.org 2>/dev/null || echo "<IP>")
    echo -e "  API:      http://$PUBLIC_IP/api"
    echo -e "  Health:   http://$PUBLIC_IP/health"
fi
echo ""
echo -e "  Log app:  tail -f $APP_DIR/logs/app.log"
echo -e "  Systemd:  sudo systemctl status manualfinder"
echo -e "  Nginx:    sudo systemctl status nginx"
echo ""
echo -e "  Prossimo step: copia i PDF locali INAIL con push.sh"
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
