# Deploy ManualFinder → Oracle Cloud

## Sequenza completa (prima volta)

### Step 1 — Oracle Cloud: crea la VM (10 min)

1. Vai su **cloud.oracle.com** → Compute → Instances → **Create Instance**
2. Nome: `manualfinder`
3. Shape: clicca **Change Shape** → Ampere → **VM.Standard.A1.Flex**
   - OCPU: **4**, RAM: **24 GB**
4. OS: **Ubuntu 22.04**
5. Networking: lascia default (VCN e subnet vengono creati automaticamente)
6. SSH Keys: **Generate a key pair** → scarica entrambi i file (`.key` e `.key.pub`)
7. **Create**

### Step 2 — Oracle Cloud: apri le porte nel firewall web (5 min)

Questo va fatto nella console Oracle **prima** di connettersi alla VM.

1. Vai su **Networking → Virtual Cloud Networks** → clicca sulla VCN creata
2. Clicca su **Security Lists** → la lista Default
3. **Add Ingress Rules** → aggiungi:
   | Source CIDR | Protocol | Port |
   |-------------|----------|------|
   | 0.0.0.0/0   | TCP      | 80   |
   | 0.0.0.0/0   | TCP      | 443  |
4. Salva

> La porta 22 (SSH) è già aperta di default.

### Step 3 — Locale: prepara .env (5 min)

```bash
cd deploy/
cp .env.template .env
# Apri .env e incolla i valori presi da Render → Environment Variables
```

### Step 4 — Locale: prima installazione (20-30 min)

Apri **Git Bash** (non PowerShell) nella root del progetto:

```bash
# Imposta le variabili della tua VM (usa IP pubblico dalla console Oracle)
export ORACLE_IP="150.230.XX.XX"
export ORACLE_KEY="C:/Users/ARCVI/Downloads/oracle_key.key"

# Opzionale: dominio personalizzato per SSL automatico
# export DOMAIN="api.tuodominio.com"

# Prima installazione completa
bash deploy/push.sh --setup
```

Lo script farà tutto: installa Python, nginx, certbot, configura il servizio, copia il codice e i PDF.

### Step 5 — Frontend su Vercel (10 min)

1. Vai su **vercel.com** → New Project → importa il repo GitHub
2. **Root Directory**: `frontend`
3. **Build Command**: `npm run build`
4. **Output Directory**: `dist`
5. Environment Variables:
   ```
   VITE_API_BASE_URL = http://150.230.XX.XX/api
   ```
   (o `https://api.tuodominio.com/api` se hai configurato il dominio)
6. Deploy

---

## Deploy aggiornamenti (deploy successivi)

Ogni volta che modifichi il codice:

```bash
export ORACLE_IP="150.230.XX.XX"
export ORACLE_KEY="C:/Users/ARCVI/Downloads/oracle_key.key"

bash deploy/push.sh
```

---

## Comandi utili sulla VM

```bash
# Connettiti
ssh -i oracle_key.key ubuntu@150.230.XX.XX

# Log in tempo reale
tail -f /opt/manualfinder/logs/app.log

# Stato servizio
sudo systemctl status manualfinder

# Riavvio manuale
sudo systemctl restart manualfinder

# Log systemd (errori di avvio)
journalctl -u manualfinder -n 50 --no-pager
```

---

## Troubleshooting

**La VM risponde a SSH ma non a HTTP**
→ Hai aperto le porte nella Security List Oracle (Step 2)?
→ Le regole iptables sono state salvate? Sulla VM: `sudo iptables -L INPUT | grep 80`

**Il servizio si avvia ma l'app risponde 502**
→ `journalctl -u manualfinder -n 50` — cerca errori di import o .env mancante

**SSL: certbot fallisce**
→ Il record DNS A deve puntare all'IP Oracle *prima* di eseguire certbot
→ Verifica: `nslookup api.tuodominio.com`

**ChromaDB crash all'avvio**
→ Il corpus è vuoto o i file non sono stati copiati
→ Normale: l'app funziona anche senza ChromaDB (RAG disabilitato)
