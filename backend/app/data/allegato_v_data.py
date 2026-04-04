"""
Database RES — Requisiti Essenziali di Sicurezza per macchine ante-CE.
Allegato V - D.Lgs. 81/08 (Art. 70 c.1).

Funzioni:
- Smart Selector: dato machine_type OCR → filtra i requisiti rilevanti per categoria
- Tabella comparativa: Allegato V vs Direttiva Macchine 2006/42/CE
"""
from typing import Optional

# ── Struttura dati ────────────────────────────────────────────────────────────
# requisiti: punti Allegato V rilevanti per la categoria
#   id      → riferimento normativo (es. "1.3", "3.2")
#   titolo  → nome sintetico
#   testo   → obbligazione di sicurezza (Allegato V)
#   criticita → "alta" | "media" | "bassa"
#   verifica → cosa controllare fisicamente in sopralluogo
#
# tabella_ce: confronto per aspetto chiave
#   aspetto     → tema
#   allegato_v  → requisito minimo Allegato V
#   dir_ce      → requisito Direttiva 2006/42/CE equivalente
#   gap         → differenza pratica rilevante

ALLEGATO_V_CATEGORIES: dict = {

    # ─────────────────────────────────────────────────────────────────────────
    "piattaforme_aeree": {
        "label": "Piattaforme di lavoro elevabili (PLE)",
        "keywords": [
            "piattaforma aerea", "ple", "cestello", "elevabile", "nacelle",
            "cherry picker", "boom lift", "scissor lift", "piattaforma semovente",
            "piattaforma autosollevante", "piattaforma telescopica",
        ],
        "sezioni_allegato_v": ["1", "2", "3"],
        "norma_di_riferimento": "EN 280 (PLE con braccio mobile), EN 1570 (piattaforme elevatrici)",
        "requisiti": [
            {
                "id": "1.1",
                "titolo": "Resistenza strutturale",
                "testo": "La struttura, compreso cestello, braccio e telaio, deve resistere ai carichi statici e dinamici previsti con adeguato coefficiente di sicurezza.",
                "criticita": "alta",
                "verifica": "Ispeziona visivamente saldature del braccio e del cestello per cricche, deformazioni permanenti o corrosione strutturale.",
            },
            {
                "id": "1.2",
                "titolo": "Organi di avviamento e arresto di emergenza",
                "testo": "Devono essere presenti organi di avviamento a comando volontario. Il movimento del cestello deve poter essere arrestato immediatamente in qualsiasi posizione.",
                "criticita": "alta",
                "verifica": "Verifica la presenza e il funzionamento del pulsante di arresto di emergenza (fungo rosso) sia sul cestello sia a terra.",
            },
            {
                "id": "1.3",
                "titolo": "Protezioni e parapetti cestello",
                "testo": "Il cestello deve essere dotato di parapetti su tutti i lati aperti (altezza min. 1 m) con tavola fermapiede. Le protezioni non devono essere rimovibili senza attrezzi.",
                "criticita": "alta",
                "verifica": "Misura l'altezza dei parapetti del cestello e verifica la presenza della tavola fermapiede. Controlla che le protezioni non siano state rimosse o danneggiate.",
            },
            {
                "id": "1.4",
                "titolo": "Stabilità e rischio ribaltamento",
                "testo": "La macchina deve mantenere la stabilità in tutte le configurazioni di lavoro, anche su terreno inclinato fino ai limiti dichiarati dal costruttore.",
                "criticita": "alta",
                "verifica": "Verifica la presenza e il funzionamento degli stabilizzatori/livellatori. Accertati che il terreno di appoggio sia entro le pendenze consentite dal costruttore.",
            },
            {
                "id": "2.1",
                "titolo": "Stabilità in movimento",
                "testo": "Durante la traslazione (con cestello alzato o abbassato) la macchina deve mantenere stabilità sufficiente per non ribaltarsi.",
                "criticita": "alta",
                "verifica": "Verifica che il blocco di traslazione con cestello sollevato sia attivo (se previsto). Controlla l'integrità dei pneumatici o dei cingoli.",
            },
            {
                "id": "2.2",
                "titolo": "Posto di lavoro e visibilità operatore",
                "testo": "Il posto di guida deve consentire la visibilità sufficiente per la manovra in sicurezza. L'operatore nel cestello deve avere il controllo dei movimenti.",
                "criticita": "media",
                "verifica": "Accertati che i comandi del cestello abbiano priorità sui comandi a terra. Verifica la presenza di specchi o telecamere ausiliarie se la visibilità è limitata.",
            },
            {
                "id": "2.5",
                "titolo": "Sistemi di ritenuta operatore",
                "testo": "Gli operatori nel cestello devono essere trattenuti con idoneo sistema (imbracatura + punto di ancoraggio) per evitare la caduta.",
                "criticita": "alta",
                "verifica": "Verifica la presenza del punto di ancoraggio omologato nel cestello e l'utilizzo dell'imbracatura da parte dell'operatore.",
            },
            {
                "id": "3.2",
                "titolo": "Portata massima marcata",
                "testo": "La portata massima del cestello deve essere indicata in modo visibile e permanente.",
                "criticita": "media",
                "verifica": "Controlla che la targa di portata massima sia presente, leggibile e non coperta sul cestello.",
            },
            {
                "id": "3.3",
                "titolo": "Limitatori di carico e di fine corsa",
                "testo": "Devono essere presenti dispositivi che impediscano il superamento della portata nominale e che arrestino i movimenti a fine corsa.",
                "criticita": "alta",
                "verifica": "Verifica il funzionamento dei fine corsa (testare il blocco al raggiungimento del limite di estensione). Verifica la presenza del limitatore di carico se applicabile al modello.",
            },
        ],
        "tabella_ce": [
            {
                "aspetto": "Progettazione strutturale",
                "allegato_v": "Resistenza adeguata verificata empiricamente o per calcolo",
                "dir_ce": "Analisi del rischio documentata + calcoli secondo EN 280 + fascicolo tecnico CE",
                "gap": "La CE esige un fascicolo tecnico completo; l'Allegato V richiede solo che la resistenza sia verificata",
            },
            {
                "aspetto": "Arresto di emergenza",
                "allegato_v": "Dispositivo di arresto immediato in qualsiasi posizione",
                "dir_ce": "Funzione di arresto di emergenza conforme EN ISO 13850 (categoria 0 o 1)",
                "gap": "La CE richiede la categoria di arresto (0=senza ritardo, 1=rallentato) e documentazione; l'Allegato V richiede solo la presenza",
            },
            {
                "aspetto": "Parapetti cestello",
                "allegato_v": "Parapetti h≥1 m su tutti i lati, tavola fermapiede",
                "dir_ce": "Parapetti conformi EN 13374 classe C per piattaforme elevabili, con calcolo strutturale",
                "gap": "La CE specifica la classe di resistenza del parapetto; l'Allegato V fissa solo l'altezza minima",
            },
            {
                "aspetto": "Stabilizzatori",
                "allegato_v": "Stabilità garantita entro i limiti d'uso",
                "dir_ce": "Interblocco tra stabilizzatori e movimenti del braccio; rilevatori di pendenza",
                "gap": "La CE esige interblocchi automatici; l'Allegato V non li richiede esplicitamente",
            },
            {
                "aspetto": "Dichiarazione di conformità",
                "allegato_v": "Non richiesta (macchina ante-CE)",
                "dir_ce": "Dichiarazione CE obbligatoria + marcatura CE",
                "gap": "Assenza totale di marcatura CE e dichiarazione di conformità — documentare l'adeguamento eseguito",
            },
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    "escavatori": {
        "label": "Escavatori e macchine movimento terra",
        "keywords": [
            "escavatore", "scavatrice", "ruspa", "bulldozer", "pala meccanica",
            "miniescavatore", "cingolato", "movimento terra", "earthmover",
            "terna", "apripista", "livellatrice", "grader", "dumper",
        ],
        "sezioni_allegato_v": ["1", "2"],
        "norma_di_riferimento": "EN ISO 6165 (classificazione macchine movimento terra), EN 474 (serie)",
        "requisiti": [
            {
                "id": "1.2",
                "titolo": "Organi di avviamento e arresto",
                "testo": "L'avviamento del motore deve essere possibile solo dall'interno della cabina o mediante procedura controllata. Devono essere presenti comandi di arresto del motore accessibili dall'operatore.",
                "criticita": "alta",
                "verifica": "Verifica che l'avviamento non sia possibile senza operatore in cabina. Controlla la presenza e funzionamento dell'interruttore batteria.",
            },
            {
                "id": "1.3",
                "titolo": "Protezioni organi in moto",
                "testo": "Tutti gli organi in moto (cinghie, giunti, ventola) devono essere protetti da carter fissi o rimovibili solo con attrezzo.",
                "criticita": "alta",
                "verifica": "Ispeziona i carter del vano motore. Verifica che siano tutti presenti e fissati. Controlla la presenza della protezione della ventola.",
            },
            {
                "id": "1.4",
                "titolo": "Stabilità e rischio ribaltamento",
                "testo": "La macchina deve essere stabile in tutte le condizioni di lavoro e durante la traslazione, incluse le pendenze massime consentite.",
                "criticita": "alta",
                "verifica": "Verifica l'efficienza del sistema di frenatura di stazionamento. Accertati che i limiti di pendenza siano indicati in cabina.",
            },
            {
                "id": "2.2",
                "titolo": "Protezione dell'operatore (ROPS/FOPS)",
                "testo": "Deve essere presente una struttura di protezione contro il ribaltamento (ROPS) e contro la caduta di oggetti (FOPS) idonea per la macchina.",
                "criticita": "alta",
                "verifica": "Verifica la presenza della cabina ROPS/FOPS o del roll-bar. Controlla che non siano presenti ammaccature strutturali o saldature non originali sulla struttura protettiva.",
            },
            {
                "id": "2.3",
                "titolo": "Dispositivi di frenatura",
                "testo": "Devono essere presenti freni di servizio e di stazionamento indipendenti, efficaci e mantenuti in buono stato.",
                "criticita": "alta",
                "verifica": "Verifica il funzionamento del freno di stazionamento su pendenza. Accertati che i freni di servizio arrestino la macchina entro le distanze previste.",
            },
            {
                "id": "2.4",
                "titolo": "Visibilità dal posto di guida",
                "testo": "L'operatore deve avere visibilità sufficiente in tutte le direzioni di lavoro, eventualmente con ausili (specchi, telecamere).",
                "criticita": "media",
                "verifica": "Verifica la presenza e integrità di tutti gli specchi retrovisori. Se prevista telecamera posteriore, verifica il funzionamento del monitor in cabina.",
            },
            {
                "id": "2.5",
                "titolo": "Cinture di sicurezza",
                "testo": "Il sedile dell'operatore deve essere dotato di cintura di sicurezza o sistema di ritenuta equivalente.",
                "criticita": "alta",
                "verifica": "Verifica la presenza e il funzionamento della cintura di sicurezza dell'operatore. Controlla che il meccanismo di blocco sia integro.",
            },
            {
                "id": "1.8",
                "titolo": "Segnaletica e pittogrammi",
                "testo": "La macchina deve riportare le indicazioni indispensabili per la sicurezza: portata, divieti, avvertenze, pittogrammi di pericolo.",
                "criticita": "bassa",
                "verifica": "Verifica la leggibilità di tutti i pittogrammi di sicurezza. Controlla che la targa di identificazione sia presente e leggibile.",
            },
        ],
        "tabella_ce": [
            {
                "aspetto": "ROPS (protezione ribaltamento)",
                "allegato_v": "Struttura ROPS idonea per la macchina",
                "dir_ce": "ROPS certificata secondo EN ISO 3471 con test di carico e fascicolo tecnico",
                "gap": "La CE richiede test distruttivi su prototipo e certificazione; l'Allegato V richiede solo l'idoneità",
            },
            {
                "aspetto": "FOPS (protezione caduta oggetti)",
                "allegato_v": "Protezione contro caduta oggetti idonea",
                "dir_ce": "FOPS certificata secondo EN ISO 3449 (Livello I o II a seconda del rischio)",
                "gap": "La CE classifica FOPS per livello di protezione specifico; l'Allegato V non distingue i livelli",
            },
            {
                "aspetto": "Freni",
                "allegato_v": "Freni di servizio e stazionamento indipendenti e efficaci",
                "dir_ce": "Freni conformi a EN ISO 11169 con distanze di arresto calcolate e documentate",
                "gap": "La CE richiede distanze di arresto misurate e documentate nel fascicolo tecnico",
            },
            {
                "aspetto": "Emissioni rumore",
                "allegato_v": "Riduzione al minimo possibile",
                "dir_ce": "Livello di potenza acustica garantito marcato + Direttiva 2000/14/CE",
                "gap": "La CE obbliga la marcatura del livello sonoro garantito; l'Allegato V non fissa valori limite",
            },
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    "gru_mobili": {
        "label": "Gru mobili e autogrù",
        "keywords": [
            "gru mobile", "autogrù", "autogru", "gru su autocarro", "gru cingolata",
            "crane", "gru semovente", "gru a torre", "gru telescopica", "sollevamento",
            "braccio telescopico", "carroponte mobile",
        ],
        "sezioni_allegato_v": ["1", "2", "3"],
        "norma_di_riferimento": "EN 13000 (gru mobili), EN 12999 (gru idrauliche su veicolo)",
        "requisiti": [
            {
                "id": "1.1",
                "titolo": "Resistenza strutturale",
                "testo": "La struttura portante (braccio, torretta, contrappeso) deve resistere ai carichi massimi con coefficiente di sicurezza adeguato.",
                "criticita": "alta",
                "verifica": "Ispeziona visivamente le saldature principali del braccio e della torretta per cricche o deformazioni. Controlla i perni di articolazione per usura eccessiva.",
            },
            {
                "id": "1.2",
                "titolo": "Comandi e arresto di emergenza",
                "testo": "I comandi di sollevamento e rotazione devono tornare in posizione neutra al rilascio. Deve essere presente un arresto di emergenza accessibile dall'operatore.",
                "criticita": "alta",
                "verifica": "Verifica che i joystick/leve tornino in neutro al rilascio. Controlla il funzionamento dell'arresto di emergenza.",
            },
            {
                "id": "1.4",
                "titolo": "Stabilità — stabilizzatori",
                "testo": "La gru deve essere portata in assetto di lavoro con stabilizzatori completamente estesi e in appoggio su terreno idoneo prima di qualsiasi sollevamento.",
                "criticita": "alta",
                "verifica": "Verifica l'estensione completa degli stabilizzatori e l'appoggio su basette di ripartizione del carico. Controlla i sensori di livello (se presenti).",
            },
            {
                "id": "3.1",
                "titolo": "Resistenza strutturale per sollevamento",
                "testo": "I componenti strutturali e i dispositivi di sollevamento (funi, ganci, bozzelli) devono avere la resistenza necessaria con i coefficienti di sicurezza previsti.",
                "criticita": "alta",
                "verifica": "Verifica lo stato della fune: deformazioni permanenti, fili rotti (scartare se >10% del totale per passo), corrosione. Controlla il gancio per deformazioni e il dispositivo anti-sgancio.",
            },
            {
                "id": "3.2",
                "titolo": "Portata massima — diagramma di carico",
                "testo": "Il diagramma di carico (portata in funzione del raggio e della configurazione) deve essere presente in cabina, leggibile e riferito alla macchina specifica.",
                "criticita": "alta",
                "verifica": "Controlla la presenza del diagramma di carico in cabina. Verifica che sia leggibile e specifico per la configurazione della gru (braccio esteso, angolo di lavoro).",
            },
            {
                "id": "3.3",
                "titolo": "Limitatore di carico (LMI)",
                "testo": "Deve essere presente un dispositivo limitatore del momento di carico (LMI) che arresti il sollevamento al raggiungimento del 100% della portata ammessa.",
                "criticita": "alta",
                "verifica": "Verifica la presenza e il funzionamento del LMI (Rated Capacity Limiter). Accertati che l'indicatore di carico sia visibile dall'operatore.",
            },
            {
                "id": "3.4",
                "titolo": "Dispositivi anti-caduta del carico",
                "testo": "Il sistema di frenatura del verricello deve mantenere il carico sospeso in caso di mancanza di potenza.",
                "criticita": "alta",
                "verifica": "Verifica che il freno del verricello mantenga il carico fermo a motore spento. Controlla il dispositivo anti-sgancio del gancio (ribaltina di sicurezza).",
            },
            {
                "id": "2.1",
                "titolo": "Stabilità durante la traslazione",
                "testo": "Durante la traslazione il braccio deve essere in posizione di trasporto. Devono essere presenti interblocchi che impediscano la traslazione con carico sollevato (se non previsto dal costruttore).",
                "criticita": "alta",
                "verifica": "Verifica il fissaggio del braccio in posizione di trasporto. Controlla che il carico non venga trasportato a quota elevata.",
            },
        ],
        "tabella_ce": [
            {
                "aspetto": "Limitatore di carico (LMI)",
                "allegato_v": "Presente e funzionante",
                "dir_ce": "LMI conforme EN 12077-2 con indicazione percentuale in tempo reale + allarme acustico+visivo al 90%",
                "gap": "La CE richiede l'allarme al 90% e la visualizzazione in percentuale; l'Allegato V richiede solo il blocco al 100%",
            },
            {
                "aspetto": "Verifica periodica fune",
                "allegato_v": "Scarto se >10% fili rotti per passo",
                "dir_ce": "Criteri di scarto secondo EN ISO 4309 (più dettagliati per tipo di fune e applicazione)",
                "gap": "La EN ISO 4309 CE distingue per tipo di fune e applicazione; l'Allegato V ha criteri generali",
            },
            {
                "aspetto": "Stabilizzatori — interblocchi",
                "allegato_v": "Stabilità garantita con stabilizzatori estesi",
                "dir_ce": "Interblocco che impedisce sollevamento con stabilizzatori non completamente estesi e a terra",
                "gap": "La CE esige l'interblocco automatico; l'Allegato V affida la responsabilità all'operatore",
            },
            {
                "aspetto": "Piano di lavoro sicuro",
                "allegato_v": "Non previsto esplicitamente",
                "dir_ce": "Piano di lavoro sicuro (Safe Working Load plan) documentato per ogni sollevamento",
                "gap": "La CE introduce il concetto di pianificazione del sollevamento; non presente nell'Allegato V",
            },
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    "carrelli_elevatori": {
        "label": "Carrelli elevatori (muletti)",
        "keywords": [
            "carrello elevatore", "muletto", "forklift", "transpallet",
            "reach truck", "carrello retrattile", "carrello controbilanciato",
            "stackers", "elevatore a forche",
        ],
        "sezioni_allegato_v": ["1", "2", "3"],
        "norma_di_riferimento": "EN ISO 3691 (carrelli industriali), EN 1755 (atmosfere esplosive)",
        "requisiti": [
            {
                "id": "1.3",
                "titolo": "Protezione operatore (ROPS/gabbia)",
                "testo": "Il posto di guida deve essere protetto contro la caduta di materiale e il ribaltamento con struttura idonea (ROPS o tettuccio di protezione).",
                "criticita": "alta",
                "verifica": "Verifica la presenza e l'integrità del tettuccio di protezione (overhead guard). Controlla che non siano presenti deformazioni strutturali o giunzioni non originali.",
            },
            {
                "id": "1.2",
                "titolo": "Comandi — posizione di neutralità",
                "testo": "I comandi di sollevamento e traslazione devono tornare in posizione neutra al rilascio e non devono consentire movimenti involontari.",
                "criticita": "alta",
                "verifica": "Verifica che il sedile con interruttore di presenza blocchi i movimenti se l'operatore si alza. Controlla che le leve tornino in neutro.",
            },
            {
                "id": "2.3",
                "titolo": "Frenatura e stabilità",
                "testo": "Devono essere presenti freni di servizio, di stazionamento e, per i carrelli elettrici, un freno di emergenza. Il carrello non deve muoversi su pendenza con il freno di stazionamento inserito.",
                "criticita": "alta",
                "verifica": "Verifica il funzionamento del freno di stazionamento su rampa. Controlla l'efficienza dei freni di servizio.",
            },
            {
                "id": "3.2",
                "titolo": "Targa portata e diagramma di carico",
                "testo": "La portata massima (in funzione del baricentro del carico e dell'altezza di sollevamento) deve essere indicata in modo visibile sul carrello.",
                "criticita": "alta",
                "verifica": "Verifica che la targa di portata (con diagramma baricentro-altezza) sia presente, leggibile e fissata al montante o alla cabina.",
            },
            {
                "id": "3.3",
                "titolo": "Limitatore di fine corsa sollevamento",
                "testo": "Deve essere presente un fine corsa che arresti il sollevamento del montante al limite massimo previsto.",
                "criticita": "media",
                "verifica": "Verifica il funzionamento del fine corsa di sollevamento. Controlla che il catena/cilindro non arrivi a fine corsa meccanico prima del blocco elettrico.",
            },
            {
                "id": "2.4",
                "titolo": "Visibilità e segnalazione acustica",
                "testo": "Il carrello deve essere dotato di segnalazione acustica azionabile dall'operatore. In aree con visibilità limitata devono essere presenti segnali luminosi di avvertimento.",
                "criticita": "media",
                "verifica": "Verifica il funzionamento del clacson. Controlla la presenza del lampeggiante arancione se il carrello opera in aree miste pedoni/veicoli.",
            },
        ],
        "tabella_ce": [
            {
                "aspetto": "Interruttore di presenza operatore",
                "allegato_v": "Non richiesto esplicitamente",
                "dir_ce": "Sensore di presenza sul sedile che blocca i movimenti di lavoro se l'operatore non è a bordo (EN ISO 3691-1)",
                "gap": "Componente di sicurezza aggiuntivo richiesto dalla CE ma non dall'Allegato V",
            },
            {
                "aspetto": "Stabilità — test di ribaltamento",
                "allegato_v": "Stabilità garantita entro i limiti d'uso",
                "dir_ce": "Test di stabilità documentati secondo EN ISO 3691-1 (angolo di ribaltamento verificato)",
                "gap": "La CE richiede test documentati su prototipo; l'Allegato V non prescrive test specifici",
            },
            {
                "aspetto": "Tettuccio (overhead guard)",
                "allegato_v": "Protezione idonea contro caduta materiale",
                "dir_ce": "Tettuccio testato secondo EN 13755 con carico statico definito",
                "gap": "La CE certifica il tettuccio con test normalizzato; l'Allegato V richiede solo l'idoneità",
            },
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    "compressori": {
        "label": "Compressori d'aria",
        "keywords": [
            "compressore", "compressor", "aria compressa", "compressore a vite",
            "compressore a pistone", "compressore mobile", "gruppo compressore",
        ],
        "sezioni_allegato_v": ["1"],
        "norma_di_riferimento": "EN 1012-1 (compressori), PED 2014/68/UE (recipienti in pressione)",
        "requisiti": [
            {
                "id": "1.1",
                "titolo": "Resistenza del serbatoio e circuito in pressione",
                "testo": "Il serbatoio, le tubazioni e i raccordi devono resistere alla pressione massima di esercizio con adeguato coefficiente di sicurezza.",
                "criticita": "alta",
                "verifica": "Verifica la presenza del certificato di omologazione del serbatoio (ISPESL/INAIL) con data ultima verifica. Controlla visivamente il serbatoio per corrosione o ammaccature.",
            },
            {
                "id": "1.2",
                "titolo": "Valvola di sicurezza e pressostato",
                "testo": "Deve essere presente una valvola di sicurezza tarata alla pressione massima ammissibile (PS). Il pressostato deve interrompere il compressore al raggiungimento della pressione massima.",
                "criticita": "alta",
                "verifica": "Verifica la presenza, la taratura (PS marcata) e la funzionalità della valvola di sicurezza. Controlla che il pressostato interrompa il motore al set point.",
            },
            {
                "id": "1.3",
                "titolo": "Protezioni organi in moto (cinghie/accoppiamenti)",
                "testo": "Le cinghie di trasmissione, l'accoppiamento e la ventola di raffreddamento devono essere protetti da carter fissi.",
                "criticita": "alta",
                "verifica": "Verifica la presenza e il fissaggio di tutti i carter di protezione cinghie e accoppiamento.",
            },
            {
                "id": "1.7",
                "titolo": "Manutenzione in sicurezza",
                "testo": "Il serbatoio deve poter essere svuotato (purga della condensa) in sicurezza. Le operazioni di manutenzione devono essere possibili con macchina ferma e scarica.",
                "criticita": "media",
                "verifica": "Verifica la presenza e il funzionamento del rubinetto di scarico condensa. Controlla che la procedura di scarico pressione sia indicata sulla macchina.",
            },
            {
                "id": "1.8",
                "titolo": "Marcatura e segnaletica",
                "testo": "Il serbatoio deve riportare: PS (pressione massima), V (volume), data di fabbricazione, numero di matrice, marchio del fabbricante.",
                "criticita": "media",
                "verifica": "Verifica la leggibilità della targhetta sul serbatoio con PS, volume e dati costruttore. Controlla la presenza del libretto di omologazione.",
            },
        ],
        "tabella_ce": [
            {
                "aspetto": "Serbatoio in pressione",
                "allegato_v": "Omologazione ISPESL/INAIL + verifica periodica biennale (Art. 71 D.Lgs. 81/08)",
                "dir_ce": "Conformità PED 2014/68/UE + marcatura CE serbatoio + verifica biennale (D.Lgs. 81/08 rimane)",
                "gap": "La CE aggiunge la conformità PED e la marcatura CE al serbatoio; la verifica periodica rimane obbligatoria in entrambi i casi",
            },
            {
                "aspetto": "Valvola di sicurezza",
                "allegato_v": "Presente e tarata a PS",
                "dir_ce": "Valvola SIL-rated con certificazione e taratura documentata da organismo notificato",
                "gap": "La CE può richiedere una valvola con livello SIL certificato per applicazioni specifiche",
            },
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    "betoniere": {
        "label": "Betoniere e mescolatori",
        "keywords": [
            "betoniera", "mescolatore", "mixer", "calcestruzzo", "cemento",
            "impastatrice", "drum mixer", "betoniere a gravità",
        ],
        "sezioni_allegato_v": ["1"],
        "norma_di_riferimento": "EN 12151 (betoniere), EN 12001 (pompe calcestruzzo)",
        "requisiti": [
            {
                "id": "1.2",
                "titolo": "Dispositivo di arresto rapido",
                "testo": "Deve essere presente un dispositivo di arresto rapido del tamburo accessibile all'operatore, anche in posizione di carico/scarico.",
                "criticita": "alta",
                "verifica": "Verifica la presenza e il funzionamento del dispositivo di arresto rapido. Controlla che sia raggiungibile dall'operatore in posizione di scarico.",
            },
            {
                "id": "1.3",
                "titolo": "Protezione apertura tamburo",
                "testo": "L'apertura del tamburo deve essere protetta per impedire l'accesso inavvertito alle parti in movimento durante la rotazione.",
                "criticita": "alta",
                "verifica": "Verifica la presenza della protezione/griglia sull'apertura di carico. Controlla che non sia stata rimossa o neutralizzata.",
            },
            {
                "id": "1.3b",
                "titolo": "Protezione corona dentata e catena di trasmissione",
                "testo": "La corona dentata di rotazione del tamburo e la catena/cinghia di trasmissione devono essere completamente protette.",
                "criticita": "alta",
                "verifica": "Verifica la presenza e l'integrità del carter della corona dentata. Controlla la protezione della catena di trasmissione.",
            },
            {
                "id": "1.4",
                "titolo": "Stabilità durante lo scarico",
                "testo": "Durante l'inclinazione del tamburo per lo scarico la macchina deve rimanere stabile. Il carrello e il telaio devono essere in buone condizioni.",
                "criticita": "media",
                "verifica": "Verifica l'integrità del meccanismo di inclinazione e dei freni delle ruote durante lo scarico.",
            },
            {
                "id": "1.8",
                "titolo": "Segnaletica di pericolo",
                "testo": "Devono essere presenti pittogrammi che avvertano del pericolo di intrappolamento nella corona dentata e nell'apertura del tamburo.",
                "criticita": "bassa",
                "verifica": "Verifica la presenza e leggibilità dei pittogrammi di pericolo (mano intrappolata, divieto di introdurre oggetti).",
            },
        ],
        "tabella_ce": [
            {
                "aspetto": "Protezione apertura tamburo",
                "allegato_v": "Protezione che impedisce l'accesso durante la rotazione",
                "dir_ce": "Riparo mobile con interblocco che blocca la rotazione all'apertura (EN 12151)",
                "gap": "La CE richiede l'interblocco automatico; l'Allegato V si accontenta della protezione fisica",
            },
            {
                "aspetto": "Rumore",
                "allegato_v": "Riduzione al minimo possibile",
                "dir_ce": "Livello LpA misurato e marcato + dichiarazione di conformità Direttiva Macchine",
                "gap": "La CE obbliga la marcatura del livello di rumore garantito",
            },
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    "generatori": {
        "label": "Generatori elettrici e gruppi elettrogeni",
        "keywords": [
            "generatore", "generator", "gruppo elettrogeno", "alternatore",
            "genset", "centrale mobile", "generatore diesel", "generatore a benzina",
        ],
        "sezioni_allegato_v": ["1"],
        "norma_di_riferimento": "EN 12601 (gruppi elettrogeni), IEC 60034 (macchine rotanti)",
        "requisiti": [
            {
                "id": "1.2",
                "titolo": "Interruttore generale e protezione sovraccarico",
                "testo": "Deve essere presente un interruttore generale accessibile per il distacco rapido dell'alimentazione. Devono essere presenti protezioni contro il sovraccarico e il cortocircuito.",
                "criticita": "alta",
                "verifica": "Verifica la presenza e il funzionamento dell'interruttore generale (differenziale + magnetotermico). Controlla le tarature degli interruttori di protezione.",
            },
            {
                "id": "1.3",
                "titolo": "Protezioni organi in moto e scarico",
                "testo": "Le parti rotanti (accoppiamento motore-alternatore, ventola) devono essere protette. Il tubo di scarico deve essere isolato termicamente e diretto lontano dall'operatore.",
                "criticita": "alta",
                "verifica": "Verifica i carter di protezione dell'accoppiamento. Controlla l'isolamento termico del silenziatore e la direzione del gas di scarico.",
            },
            {
                "id": "1.5",
                "titolo": "Messa a terra e protezione elettrica",
                "testo": "Il telaio del generatore deve essere collegato a terra. Le prese di corrente devono essere protette contro l'accesso accidentale ai contatti.",
                "criticita": "alta",
                "verifica": "Verifica il collegamento di terra del telaio metallico. Controlla che le prese siano con protezione IP adeguata e non danneggiate.",
            },
            {
                "id": "1.7",
                "titolo": "Rifornimento carburante in sicurezza",
                "testo": "Il rifornimento deve avvenire a motore fermo. Il serbatoio deve essere dotato di tappo ermetico e sfiato.",
                "criticita": "media",
                "verifica": "Verifica l'integrità del tappo del serbatoio carburante. Controlla la presenza di avvisi 'rifornire a motore freddo'.",
            },
            {
                "id": "1.8",
                "titolo": "Segnaletica — tensione disponibile",
                "testo": "La tensione e la frequenza disponibili devono essere indicate in modo visibile sul pannello prese.",
                "criticita": "bassa",
                "verifica": "Verifica che la tensione (230V/400V) e la frequenza (50Hz) siano indicate sul pannello prese.",
            },
        ],
        "tabella_ce": [
            {
                "aspetto": "Protezione elettrica",
                "allegato_v": "Messa a terra + interruttore generale",
                "dir_ce": "Conformità Direttiva Bassa Tensione 2014/35/UE + eventuali requisiti IEC 60034",
                "gap": "La CE aggiunge requisiti specifici per la compatibilità elettromagnetica (EMC) e la sicurezza elettrica certificata",
            },
            {
                "aspetto": "Emissioni di scarico",
                "allegato_v": "Non regolamentate nell'Allegato V",
                "dir_ce": "Regolamento (UE) 2016/1628 — Stage V per macchine mobili non stradali",
                "gap": "Generatori ante-96 non soggetti ai limiti Stage; verificare compatibilità ambientale per uso in spazi chiusi",
            },
        ],
    },
}

# ── Fallback generico ─────────────────────────────────────────────────────────
_GENERIC_CATEGORY = {
    "label": "Attrezzatura di lavoro generica",
    "keywords": [],
    "sezioni_allegato_v": ["1"],
    "norma_di_riferimento": "D.Lgs. 81/08 Allegato V — Requisiti generali",
    "requisiti": [
        {
            "id": "1.1",
            "titolo": "Resistenza strutturale",
            "testo": "L'attrezzatura deve essere costruita con materiali e dimensioni adeguati alle sollecitazioni previste durante l'uso.",
            "criticita": "alta",
            "verifica": "Ispeziona la struttura portante per cricche, deformazioni permanenti, corrosione o giunzioni non originali.",
        },
        {
            "id": "1.2",
            "titolo": "Organi di avviamento e arresto",
            "testo": "L'avviamento deve essere possibile solo mediante azione volontaria su un organo di comando. Deve essere presente un dispositivo di arresto accessibile.",
            "criticita": "alta",
            "verifica": "Verifica il funzionamento dell'arresto di emergenza. Controlla che l'avviamento non sia possibile involontariamente.",
        },
        {
            "id": "1.3",
            "titolo": "Protezioni organi in moto",
            "testo": "Gli elementi mobili devono essere protetti da carter fissi o dispositivi di interblocco.",
            "criticita": "alta",
            "verifica": "Verifica la presenza e l'integrità di tutti i carter di protezione. Controlla che non siano stati rimossi o bypassati.",
        },
        {
            "id": "1.7",
            "titolo": "Manutenzione in sicurezza",
            "testo": "L'attrezzatura deve poter essere portata in una posizione sicura per le operazioni di manutenzione.",
            "criticita": "media",
            "verifica": "Verifica la possibilità di isolare l'attrezzatura (blocco energia, LOTO) prima della manutenzione.",
        },
        {
            "id": "1.8",
            "titolo": "Segnaletica e marcatura",
            "testo": "L'attrezzatura deve riportare le avvertenze e i contrassegni indispensabili per la sicurezza.",
            "criticita": "bassa",
            "verifica": "Verifica la leggibilità di tutti i pittogrammi di sicurezza e della targa di identificazione.",
        },
    ],
    "tabella_ce": [
        {
            "aspetto": "Analisi del rischio",
            "allegato_v": "Non richiesta esplicitamente",
            "dir_ce": "Analisi del rischio documentata obbligatoria (Allegato I Dir. 2006/42/CE)",
            "gap": "La CE introduce l'obbligo di analisi del rischio scritta; l'Allegato V fissa solo i requisiti minimi",
        },
        {
            "aspetto": "Fascicolo tecnico",
            "allegato_v": "Non richiesto",
            "dir_ce": "Fascicolo tecnico CE obbligatorio (disegni, calcoli, test, analisi rischio)",
            "gap": "Assenza totale del fascicolo tecnico CE — documentare l'adeguamento Allegato V eseguito",
        },
    ],
}


# ── API pubblica ──────────────────────────────────────────────────────────────

def get_machine_category(machine_type: Optional[str]) -> tuple[str, dict]:
    """
    Dato un tipo macchina OCR, restituisce (category_key, category_data).
    Usa corrispondenza fuzzy sui keywords.
    Se nessun match: restituisce ('generico', _GENERIC_CATEGORY).
    """
    if not machine_type:
        return ("generico", _GENERIC_CATEGORY)

    query = machine_type.lower().strip()

    best_key = None
    best_score = 0

    for key, data in ALLEGATO_V_CATEGORIES.items():
        for kw in data["keywords"]:
            if kw in query:
                # Match esatto sulla keyword composta → punteggio = lunghezza (più lungo = più specifico)
                score = len(kw)
                if score > best_score:
                    best_score = score
                    best_key = key
            else:
                # Match parziale: solo parole >= 5 caratteri (evita falsi positivi su parole corte)
                for word in kw.split():
                    if len(word) >= 5 and word in query:
                        score = len(word)  # Punteggio = lunghezza parola matchata
                        if score > best_score:
                            best_score = score
                            best_key = key

    if best_key:
        return (best_key, ALLEGATO_V_CATEGORIES[best_key])
    return ("generico", _GENERIC_CATEGORY)


def format_requisiti_for_prompt(category_data: dict) -> str:
    """Formatta i requisiti Allegato V per l'inserimento nel prompt AI."""
    lines = [
        f"CATEGORIA: {category_data['label']}",
        f"Norma di riferimento: {category_data.get('norma_di_riferimento', 'N/D')}",
        "",
        "REQUISITI MINIMI ALLEGATO V D.Lgs. 81/08 da verificare:",
    ]
    for r in category_data["requisiti"]:
        criticita_icon = {"alta": "🔴", "media": "🟡", "bassa": "🟢"}.get(r["criticita"], "⚪")
        lines.append(f"  {criticita_icon} [{r['id']}] {r['titolo']}: {r['testo']}")
        lines.append(f"     → Verifica: {r['verifica']}")
    return "\n".join(lines)
