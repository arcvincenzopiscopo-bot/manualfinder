# Guida Amministratore — Catalogo Tipi Macchina

## Accesso al pannello

Naviga a `/#admin` nell'URL dell'applicazione (es. `https://tua-app.com/#admin`).  
Per tornare all'app utente, clicca **← App** in alto a destra o rimuovi `#admin` dall'URL.

---

## Panoramica

Il pannello admin gestisce il **catalogo canonico dei tipi macchina**: l'elenco verificato usato dal sistema per classificare le macchine durante l'OCR e per applicare correttamente i requisiti normativi (patentino, verifiche INAIL) nella scheda di sicurezza.

Il pannello è organizzato in 4 tab:

| Tab | Scopo |
|-----|-------|
| 📊 Statistiche | Monitoraggio utilizzi e proposte in arretrato |
| ⏳ Proposte | Revisione delle macchine nuove segnalate dagli utenti |
| 🔗 Alias | Gestione sinonimi e varianti di ogni tipo |
| ⚖️ Flags normativi | Modifica obblighi normativi per tipo |

---

## Tab 1 — Statistiche

Mostra una fotografia dello stato del catalogo.

### KPI in evidenza

- **Tipi canonici** — quanti tipi macchina verificati sono nel catalogo
- **Alias totali** — quante varianti/sinonimi sono mappati
- **Proposte in attesa** — quante proposte utente non ancora revisionate (arancione se > 0)

### Top 10 tipi per utilizzo

Tabella dei tipi più confermati dagli ispettori. Per ogni tipo mostra:
- Nome canonico
- Numero di conferme (`usage_count`, incrementato solo a feedback "confermato" o "corretto")
- Se richiede patentino e/o verifiche periodiche

### Proposte in arretrato (avviso giallo)

Se esistono proposte vecchie di più di 7 giorni appare un avviso con i nomi proposti. Usa il link suggerito per spostarti sulla tab Proposte.

### Aggiorna

Il pulsante **↺ Aggiorna** ricarica i dati dal DB (la pagina non si aggiorna automaticamente).

---

## Tab 2 — Proposte

Elenca le macchine segnalate dagli utenti tramite il link "Non trovi la tua macchina?" nell'app.

Ogni proposta mostra:
- **Nome proposto** dall'utente
- **Sessione** dell'utente che ha segnalato (se disponibile)
- **Data** della proposta (bordo arancione se più vecchia di 7 giorni)
- **Suggerimento AI** — se il sistema ha trovato un tipo simile nel catalogo, lo mostra con il punteggio di somiglianza

### Azioni disponibili per ogni proposta

#### 🔗 Salva come alias
Usa questa opzione quando il nome proposto è semplicemente una variante di un tipo già esistente.

**Procedura:**
1. Clicca **🔗 Salva come alias**
2. Scegli dal menu il tipo canonico esistente a cui associare la proposta
3. Clicca **Conferma alias**

> **Esempio:** l'utente ha proposto "muletto". Scegli "carrello elevatore" come tipo di destinazione. D'ora in poi "muletto" sarà riconosciuto automaticamente dall'OCR.

#### ✅ Nuovo tipo canonico
Usa questa opzione quando il nome proposto rappresenta una categoria di macchine non ancora presente nel catalogo.

**Procedura:**
1. Clicca **✅ Nuovo tipo canonico**
2. Modifica il nome canonico se necessario (standardizzalo in italiano, minuscolo, come gli altri)
3. Spunta i flag normativi:
   - **Richiede patentino / abilitazione** — abilitazione obbligatoria Accordo Stato-Regioni 22/02/2012
   - **Richiede verifiche periodiche** — verifica INAIL obbligatoria art. 71 D.Lgs. 81/08
4. Clicca **Crea tipo canonico**

> **Attenzione:** in caso di dubbio, imposta entrambi i flag su **attivo** (comportamento conservativo). Puoi correggerli successivamente dalla tab Flags normativi.

#### 🗑 Rifiuta
Usa questa opzione per proposta chiaramente errate, spam, o per macchine fuori scope (es. elettrodomestici).

**Procedura:**
1. Clicca **🗑 Rifiuta**
2. Conferma con **Sì, rifiuta**

> La proposta viene marcata come "rejected" e scompare dalla lista. L'operazione non è reversibile dall'interfaccia.

---

## Tab 3 — Alias

Permette di gestire manualmente i sinonimi di ogni tipo macchina.  
Gli alias determinano se l'OCR riconosce automaticamente una macchina senza passare per l'AI.

### Come funziona il matching

1. Il testo OCR viene confrontato con tutti gli alias tramite similarità fuzzy
2. Score ≥ 82% → riconoscimento diretto (nessuna chiamata AI)
3. Score 65–81% → l'AI sceglie tra i candidati
4. Score < 65% → campo libero, badge grigio nell'app

### Aggiungere un alias

1. Scegli il tipo dal menu **Seleziona tipo macchina**
2. Nel campo di testo digita il nuovo alias (es. `telehandler`, `awp`, `backhoe`)
3. Premi **+ Aggiungi** o `Invio`

> Gli alias vengono normalizzati internamente (minuscolo, spazi multipli rimossi). Non è necessario inserirli in minuscolo tu stesso.

> Se l'alias è già presente nel catalogo riceverai un avviso "Alias già esistente" senza errore.

### Eliminare un alias

Clicca il pulsante 🗑 a destra dell'alias che vuoi rimuovere. La conferma avviene tramite dialog del browser.

> **Attenzione:** eliminare un alias significa che l'OCR non riconoscerà più automaticamente quella variante. Valuta prima se è un alias usato frequentemente (guarda i log o le statistiche).

### Badge sorgente

Ogni alias mostra un badge che indica chi lo ha creato:
- `admin` — aggiunto manualmente da qui
- `ocr` — appreso automaticamente da un matching fuzzy di alta qualità
- `user` — derivato da una proposta utente promossa ad alias

---

## Tab 4 — Flags normativi

Permette di correggere i requisiti legali associati a ogni tipo macchina.  
I flags determinano cosa appare nella scheda di sicurezza dell'ispettore.

### Flag disponibili

| Flag | Effetto sulla scheda di sicurezza | Normativa |
|------|----------------------------------|-----------|
| **Patentino / abilitazione** | Mostra il riquadro "Abilitazione operatore obbligatoria" | Accordo Stato-Regioni 22/02/2012 |
| **Verifiche periodiche INAIL** | Mostra il riquadro "Verifiche periodiche obbligatorie" | Art. 71 c.11 D.Lgs. 81/08, Allegato VII |

### Hint ricerca INAIL

Campo opzionale. Parole chiave usate internamente nelle query di ricerca sul portale INAIL per trovare la documentazione specifica di quel tipo. Usa termini tecnici precisi (es. `PLE piattaforma lavoro elevabile`).

### Procedura modifica

1. Cerca il tipo nel campo filtro o scorri la lista a sinistra
2. Clicca sul tipo da modificare (si evidenzia in blu)
3. Modifica i flag e l'hint INAIL nel pannello a destra
4. Clicca **💾 Salva modifiche**

La lista a sinistra si aggiorna immediatamente con i nuovi badge.

### Principio di cautela

> Se hai dubbi su un tipo, mantieni entrambi i flag **attivi**. Un falso positivo (obbligo segnalato anche se non necessario) è preferibile a un falso negativo (obbligo omesso).

---

## Valori predefiniti del catalogo

Il catalogo viene inizializzato automaticamente al primo avvio con 39 tipi verificati:

| Tipo | Patentino | Verifiche |
|------|-----------|-----------|
| Piattaforma aerea | ✓ | ✓ |
| Carrello elevatore | ✓ | ✓ |
| Carrello portacontainer | ✓ | ✓ |
| Piattaforma a forbice | ✓ | ✓ |
| Sollevatore telescopico | ✓ | ✓ |
| Gru mobile | ✓ | ✓ |
| Gru a torre | ✓ | ✓ |
| Carrello retrattile | ✓ | ✓ |
| Escavatore | — | ✓ |
| Pala caricatrice | — | ✓ |
| Terna | — | ✓ |
| Minipala | — | ✓ |
| Rullo compattatore | — | ✓ |
| Finitrice stradale | — | ✓ |
| Dumper | — | ✓ |
| Bulldozer | — | ✓ |
| Pompa calcestruzzo | — | ✓ |
| Trattore agricolo | — | ✓ |
| Elevatore a colonna | — | ✓ |
| Piattaforma verticale | — | ✓ |
| Gru a bandiera | — | ✓ |
| Paranco elettrico | — | ✓ |
| Argano | — | ✓ |
| Livellatrice | — | — |
| Betoniera | — | — |
| Generatore | — | — |
| Compressore | — | — |
| Saldatrice | — | — |
| Transpallet elettrico | — | — |
| Accessorio/attrezzatura | — | — |

---

## FAQ

**Il pannello non si carica / errore HTTP 500**  
Il backend potrebbe non aver ancora inizializzato le tabelle del catalogo. Attendi qualche secondo e ricarica. Se il problema persiste verifica i log del backend.

**Ho creato un tipo per errore**  
Non è possibile eliminare un tipo dall'interfaccia admin (per sicurezza). Usa direttamente il database (Supabase dashboard) con `UPDATE machine_types SET is_verified = false WHERE id = X` oppure contatta l'amministratore del DB.

**Un alias genera riconoscimenti sbagliati**  
Elimina l'alias dalla tab Alias. Il riconoscimento tornerà a dipendere dall'AI per quella variante.

**Come faccio a sapere se un tipo è usato?**  
Guarda la colonna "Utilizzi" nella tab Statistiche → Top 10. Per i tipi fuori dalla top 10 puoi fare una query SQL su `SELECT name, usage_count FROM machine_types ORDER BY usage_count DESC`.
