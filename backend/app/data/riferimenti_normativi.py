"""
Dizionario hardcoded degli articoli D.Lgs 81/08 rilevanti per le macchine.
Zero RAG, zero embedding — testo esatto degli articoli, zero rischio allucinazioni.

Usato da hybrid_retriever.py come prima fonte normativa (la più affidabile).
"""

RIFERIMENTI: dict = {

    "idoneita_attrezzatura": {
        "norma": "D.Lgs 81/08 Art. 70",
        "titolo": "Requisiti di sicurezza",
        "testo": (
            "Le attrezzature di lavoro messe a disposizione dei lavoratori "
            "devono essere conformi alle disposizioni legislative e "
            "regolamentari di recepimento delle direttive comunitarie di "
            "prodotto applicabili."
        ),
        "keywords": ["conformità", "marcatura CE", "dichiarazione", "direttiva", "CE", "marchio"],
        "tipo_macchina": ["*"],
    },

    "verifiche_periodiche": {
        "norma": "D.Lgs 81/08 Art. 71 c.11 + All. VII",
        "titolo": "Verifiche periodiche obbligatorie",
        "testo": (
            "Il datore di lavoro sottopone le attrezzature di lavoro "
            "riportate in allegato VII a verifiche periodiche volte a "
            "valutarne l'effettivo stato di conservazione e di efficienza "
            "ai fini di sicurezza, con la frequenza indicata nel medesimo "
            "allegato. La prima verifica è effettuata dall'INAIL che vi "
            "provvede anche tramite le ASL e le ARPA."
        ),
        "keywords": ["verifica periodica", "INAIL", "ASL", "libretto",
                     "scadenza", "frequenza", "allegato VII", "verifica"],
        "tipo_macchina": ["*"],
    },

    "formazione_operatori": {
        "norma": "D.Lgs 81/08 Art. 73",
        "titolo": "Informazione e formazione",
        "testo": (
            "Nell'ambito degli obblighi di informazione e formazione il "
            "datore di lavoro provvede affinché per ogni attrezzatura di "
            "lavoro messa a disposizione i lavoratori incaricati dell'uso "
            "dispongano di ogni necessaria informazione e istruzione e "
            "ricevano una formazione adeguata in rapporto alla sicurezza "
            "relativamente alle condizioni di impiego delle attrezzature."
        ),
        "keywords": ["formazione", "addestramento", "patentino",
                     "abilitazione", "istruzione", "corso", "informazione"],
        "tipo_macchina": ["*"],
    },

    "ripari_organi_trasmissione": {
        "norma": "D.Lgs 81/08 All. V punto 6.1",
        "titolo": "Protezione organi di trasmissione",
        "testo": (
            "Gli organi di trasmissione del moto (cinghie, catene, "
            "ingranaggi, alberi) devono essere protetti con ripari fissi "
            "o mobili interbloccati idonei a impedire il contatto "
            "accidentale."
        ),
        "keywords": ["organi trasmissione", "cinghie", "ingranaggi",
                     "riparo", "protezione meccanica", "carter", "catena"],
        "tipo_macchina": ["*"],
    },

    "dispositivi_arresto_emergenza": {
        "norma": "D.Lgs 81/08 All. V punto 3.1",
        "titolo": "Dispositivi di arresto di emergenza",
        "testo": (
            "Le attrezzature di lavoro devono essere munite di dispositivi "
            "chiaramente identificabili per isolarle da ciascuna delle loro "
            "fonti di energia. Il ripristino dell'alimentazione non deve "
            "comportare rischi per i lavoratori. I comandi di avviamento "
            "devono essere tali da richiedere un'azione intenzionale."
        ),
        "keywords": ["arresto emergenza", "fungo rosso", "stop",
                     "pulsante emergenza", "isolamento energia", "arresto"],
        "tipo_macchina": ["*"],
    },

    "stabilita_macchina": {
        "norma": "D.Lgs 81/08 All. V punto 1.1",
        "titolo": "Stabilità e rischio ribaltamento",
        "testo": (
            "Le attrezzature di lavoro mobili devono essere dotate di "
            "dispositivi idonei a prevenire il rischio di ribaltamento. "
            "Per le macchine che movimentano carichi o persone sono "
            "obbligatori sistemi ROPS (Roll-Over Protective Structure) "
            "e/o FOPS (Falling Object Protective Structure) ove applicabili "
            "secondo le norme armonizzate EN 13510 e ISO 3449."
        ),
        "keywords": ["ribaltamento", "stabilità", "ROPS", "FOPS",
                     "capovolgimento", "stabilizzatori", "tipping"],
        "tipo_macchina": ["*"],
    },

    "patentino_accordo_stato_regioni": {
        "norma": "Accordo Stato-Regioni 22/02/2012 (G.U. n.60 del 12/03/2012)",
        "titolo": "Abilitazione operatori — patentino",
        "testo": (
            "L'accordo definisce le attrezzature per cui è necessaria "
            "abilitazione specifica: gru su autocarro, gru mobile, gru "
            "a torre, carrelli elevatori semoventi (frontali, laterali, "
            "retrattili, trilaterali, bidirezionali, a braccio telescopico), "
            "escavatori idraulici, escavatori a fune, pale caricatrici "
            "frontali, terne, piattaforme di lavoro elevabili (PLE), "
            "trattori agricoli e forestali, pompe per calcestruzzo, "
            "autoribaltabili a cingoli."
        ),
        "keywords": ["patentino", "abilitazione", "accordo stato regioni",
                     "formazione specifica", "attestato", "abilitazione specifica"],
        "tipo_macchina": ["escavatore", "escavatore idraulico",
                          "carrello elevatore", "gru", "gru mobile",
                          "piattaforma elevabile", "piattaforma aerea",
                          "trattore", "terna",
                          "pala caricatrice", "pala caricatrice frontale",
                          "pompa calcestruzzo", "autoribaltabile"],
    },

    "segnaletica_sicurezza": {
        "norma": "D.Lgs 81/08 All. V punto 11.3",
        "titolo": "Segnalatori acustici e luminosi",
        "testo": (
            "Le attrezzature di lavoro devono essere munite di segnalatori "
            "acustici e luminosi quando necessario per la sicurezza dei "
            "lavoratori e dei terzi presenti nell'area di lavoro. "
            "I segnalatori devono essere udibili e visibili nelle condizioni "
            "di utilizzo previste."
        ),
        "keywords": ["segnalatori", "lampeggiante", "cicalino",
                     "avvisatore acustico", "segnaletica", "beacon",
                     "allarme sonoro"],
        "tipo_macchina": ["*"],
    },

    "manuale_uso_italiano": {
        "norma": "D.Lgs 81/08 Art. 71 c.4 + All. V punto 1",
        "titolo": "Manuale d'uso in lingua italiana",
        "testo": (
            "Il datore di lavoro deve mettere a disposizione dei lavoratori "
            "il manuale d'uso e manutenzione nella lingua italiana. "
            "Il manuale deve essere conservato presso la macchina o "
            "in luogo accessibile agli operatori. Per le macchine CE "
            "l'obbligo discende dalla Direttiva Macchine recepita con "
            "D.Lgs. 17/2010."
        ),
        "keywords": ["manuale", "istruzioni", "lingua italiana",
                     "documentazione", "libretto", "uso e manutenzione"],
        "tipo_macchina": ["*"],
    },

    "dichiarazione_conformita_CE": {
        "norma": "D.Lgs 81/08 Art. 70 + Dir. 2006/42/CE Art. 15",
        "titolo": "Dichiarazione CE di conformità",
        "testo": (
            "Ogni macchina immessa sul mercato o messa in servizio deve "
            "essere accompagnata da dichiarazione CE di conformità firmata "
            "dal fabbricante o dal suo mandatario. La dichiarazione deve "
            "indicare le direttive applicate, le norme armonizzate e "
            "il numero della macchina. Deve essere conservata per 10 anni."
        ),
        "keywords": ["dichiarazione conformità", "CE", "marcatura",
                     "fabbricante", "targa", "dichiarazione di conformità"],
        "tipo_macchina": ["*"],
    },

    "registro_manutenzione": {
        "norma": "D.Lgs 81/08 Art. 71 c.4",
        "titolo": "Registro di manutenzione e controlli",
        "testo": (
            "Il datore di lavoro deve tenere un registro delle manutenzioni "
            "e dei controlli periodici effettuati sull'attrezzatura. "
            "Il registro deve essere disponibile per i controlli ispettivi "
            "ed è obbligatorio per le attrezzature soggette ad Allegato VII."
        ),
        "keywords": ["registro", "manutenzione", "controlli periodici",
                     "storico", "log", "libretto verifiche"],
        "tipo_macchina": ["*"],
    },

    "obblighi_datore_lavoro": {
        "norma": "D.Lgs 81/08 Art. 71 c.1-3",
        "titolo": "Obblighi del datore di lavoro",
        "testo": (
            "Il datore di lavoro mette a disposizione dei lavoratori "
            "attrezzature conformi ai requisiti di cui all'art. 70, idonee "
            "ai fini della salute e sicurezza e adeguate al lavoro da "
            "svolgere. In caso di rischi residui il datore di lavoro adotta "
            "le misure adeguate per ridurli al minimo."
        ),
        "keywords": ["datore di lavoro", "obblighi", "responsabilità",
                     "idoneità", "adeguatezza", "rischio residuo"],
        "tipo_macchina": ["*"],
    },

    "protezione_organi_lavoratori": {
        "norma": "D.Lgs 81/08 All. V punto 6",
        "titolo": "Protezione da organi mobili pericolosi",
        "testo": (
            "Le parti di macchine che possono causare infortuni devono "
            "essere protette o schermati. I ripari e i dispositivi di "
            "protezione devono essere di robusta costruzione, non devono "
            "essere facilmente resi inefficaci o elusi, devono essere "
            "situati a sufficiente distanza dalla zona pericolosa."
        ),
        "keywords": ["organi mobili", "protezione", "schermatura", "riparo",
                     "zona pericolosa", "guardia", "scherma"],
        "tipo_macchina": ["*"],
    },

    "macchine_soggette_verifiche_periodiche": {
        "norma": "D.Lgs 81/08 All. VII",
        "titolo": "Macchine soggette a verifiche periodiche (Allegato VII)",
        "testo": (
            "Sono soggette a verifiche periodiche le seguenti attrezzature: "
            "apparecchi di sollevamento materiali non azionati a mano con "
            "portata > 200 kg (cadenza biennale), apparecchi di sollevamento "
            "persone (cadenza annuale), PLE (piattaforme di lavoro elevabili, "
            "cadenza annuale), ascensori da cantiere (cadenza semestrale), "
            "ponteggi e opere provvisionali. "
            "Prima verifica: INAIL. Successive: ASL o organismo notificato."
        ),
        "keywords": ["allegato VII", "soggette verifiche", "apparecchi sollevamento",
                     "portata 200 kg", "cadenza", "biennale", "annuale",
                     "INAIL prima verifica", "organismo notificato"],
        "tipo_macchina": ["gru", "gru a torre", "gru su autocarro",
                          "piattaforma aerea", "carrello elevatore",
                          "ascensore da cantiere", "terna"],
    },

    "uso_corretto_attrezzature": {
        "norma": "D.Lgs 81/08 Art. 72",
        "titolo": "Obblighi dei noleggiatori e dei concedenti in uso",
        "testo": (
            "Chiunque venda, noleggi o conceda in uso attrezzature di "
            "lavoro deve attestare, sotto la propria responsabilità, "
            "che le stesse sono conformi ai requisiti di sicurezza. "
            "Chi noleggia o concede in uso senza operatore deve attestare "
            "il buono stato di conservazione, efficienza e sicurezza."
        ),
        "keywords": ["noleggio", "uso", "concedente", "attestazione",
                     "buono stato", "efficienza", "conformità noleggio"],
        "tipo_macchina": ["*"],
    },

    "dpi_obbligatori": {
        "norma": "D.Lgs 81/08 Art. 74-79 + All. VIII",
        "titolo": "Dispositivi di Protezione Individuale obbligatori",
        "testo": (
            "Il datore di lavoro analizza e valuta i rischi che non possono "
            "essere evitati con altri mezzi e individua i DPI idonei. "
            "I DPI devono essere certificati EN, conformi alle norme "
            "armonizzate, adeguati ai rischi specifici senza comportare "
            "di per sé un rischio maggiore."
        ),
        "keywords": ["DPI", "dispositivi protezione individuale", "elmetto",
                     "imbracatura", "guanti", "occhiali", "scarpe", "casco"],
        "tipo_macchina": ["*"],
    },

    "vibrazioni_meccaniche": {
        "norma": "D.Lgs 81/08 Art. 202-209 (Titolo VIII Capo III)",
        "titolo": "Rischio vibrazioni — HAV e WBV",
        "testo": (
            "Il datore di lavoro valuta il rischio di esposizione a "
            "vibrazioni meccaniche trasmesse al sistema mano-braccio (HAV) "
            "e al corpo intero (WBV). Valori limite di esposizione giornaliera: "
            "HAV = 5 m/s², WBV = 1,15 m/s². Valori d'azione: "
            "HAV = 2,5 m/s², WBV = 0,5 m/s²."
        ),
        "keywords": ["vibrazioni", "HAV", "WBV", "mano-braccio",
                     "corpo intero", "m/s²", "vibrazioni meccaniche"],
        "tipo_macchina": ["*"],
    },

    "rumore_ambienti_lavoro": {
        "norma": "D.Lgs 81/08 Art. 190-198 (Titolo VIII Capo II)",
        "titolo": "Rischio rumore — valori limite",
        "testo": (
            "Valori limite di esposizione: LEX,8h = 87 dB(A), ppeak = 200 Pa. "
            "Valori superiori di azione: LEX,8h = 85 dB(A), ppeak = 140 Pa. "
            "Valori inferiori di azione: LEX,8h = 80 dB(A), ppeak = 112 Pa. "
            "Oltre 85 dB(A) l'uso di protezioni auricolari è obbligatorio."
        ),
        "keywords": ["rumore", "dB(A)", "LEX", "decibel", "protezione auricolare",
                     "otoprotettore", "rumore", "esposizione sonora"],
        "tipo_macchina": ["*"],
    },

    "rischio_elettrico_generale": {
        "norma": "D.Lgs 81/08 Art. 80-86 (Titolo III Capo III)",
        "titolo": "Rischio elettrico — obblighi del datore di lavoro",
        "testo": (
            "NOTA — Criterio di specialità: nei cantieri temporanei o mobili "
            "gli Art. 116-118 (Titolo IV) costituiscono norme speciali e si "
            "applicano in luogo degli Art. 82-83 del presente Titolo. "
            "Negli altri luoghi di lavoro: il datore di lavoro prende le "
            "misure necessarie affinché i lavoratori siano salvaguardati "
            "dai rischi di natura elettrica connessi all'uso delle attrezzature. "
            "Individua e attua misure tecniche e organizzative idonee a "
            "eliminare o ridurre al minimo i rischi. Le macchine devono "
            "essere progettate e costruite in modo da proteggere i lavoratori "
            "dai pericoli elettrici ai sensi della norma CEI EN 60204-1."
        ),
        "keywords": ["rischio elettrico", "elettricità", "corrente",
                     "folgorazione", "scarica", "protezione elettrica",
                     "quadro elettrico", "cavo", "impianto elettrico"],
        "tipo_macchina": ["*"],
    },

    "contatto_linee_elettriche_luoghi_lavoro": {
        "norma": "D.Lgs 81/08 Art. 83 + CEI 11-27",
        "titolo": "Lavori in prossimità di parti attive (luoghi di lavoro non cantiere)",
        "testo": (
            "NOTA — Criterio di specialità: nei cantieri temporanei o mobili "
            "si applica l'Art. 117 (Titolo IV) in luogo del presente articolo. "
            "Negli altri luoghi di lavoro: non possono essere eseguiti lavori "
            "in prossimità di linee elettriche o impianti con parti attive "
            "non protette a distanza inferiore ai limiti dell'Allegato IX. "
            "Distanze minime: 3 m per tensioni ≤ 1 kV, 5 m per tensioni > 1 kV "
            "fino a 132 kV, 7 m per tensioni superiori. "
            "Il responsabile deve verificare preventivamente la presenza "
            "di parti attive nell'area di lavoro (CEI 11-27)."
        ),
        "keywords": ["linea elettrica", "linee aeree", "alta tensione",
                     "elettrodotto", "distanza sicurezza", "contatto elettrico",
                     "pericolo linee", "cavi aerei", "folgorazione", "allegato IX"],
        "tipo_macchina": ["*"],
    },

    "contatto_linee_elettriche_cantiere": {
        "norma": "D.Lgs 81/08 Art. 117 (Titolo IV) + CEI 11-27",
        "titolo": "Lavori in prossimità di parti attive — cantieri (lex specialis Art. 83)",
        "testo": (
            "Nei cantieri temporanei o mobili (Titolo IV) si applica l'Art. 117 "
            "quale norma speciale rispetto all'Art. 83. "
            "Prima dell'inizio dei lavori il datore di lavoro verifica la "
            "presenza di linee elettriche aeree o interrate nell'area di cantiere "
            "e ne richiede la messa fuori tensione o la protezione. "
            "Non è consentito avvicinarsi con macchine o attrezzature a distanza "
            "inferiore a quella indicata nell'Allegato IX: 3 m per BT (≤ 1 kV), "
            "5 m per MT e AT. Il PSC (Piano di Sicurezza e Coordinamento) "
            "deve individuare e segnalare le linee presenti nell'area. "
            "In caso di contatto accidentale: spegnere la macchina, non scendere, "
            "allertare i soccorsi, allontanarsi solo a piccoli passi (passo d'oca)."
        ),
        "keywords": ["linea elettrica", "linee aeree", "alta tensione", "cantiere",
                     "elettrodotto", "distanza sicurezza", "art 117", "titolo IV",
                     "pericolo linee", "cavi aerei", "folgorazione", "PSC",
                     "passo d'oca", "messa fuori tensione"],
        "tipo_macchina": ["escavatore", "escavatore idraulico",
                          "gru", "gru a torre", "gru su autocarro", "gru mobile",
                          "piattaforma aerea", "piattaforma elevabile",
                          "pala caricatrice frontale", "sollevatore telescopico",
                          "autogrù", "terna", "dumper", "macchina movimento terra",
                          "pala gommata", "rullo compattatore"],
    },

    "impianti_elettrici_cantiere": {
        "norma": "D.Lgs 81/08 Art. 118 (Titolo IV) + CEI 64-8/7",
        "titolo": "Impianti elettrici di cantiere — installazioni temporanee",
        "testo": (
            "Gli impianti elettrici nei cantieri temporanei o mobili sono "
            "regolati dall'Art. 118 (Titolo IV, lex specialis) e dalla "
            "norma CEI 64-8 Parte 7 (installazioni in luoghi particolari). "
            "I quadri elettrici di cantiere devono avere grado di protezione "
            "minimo IP44, essere conformi alla norma CEI EN 60439-4 e dotati "
            "di interruttori differenziali (Id ≤ 30 mA per prese a spina). "
            "I cavi devono essere protetti da danneggiamenti meccanici. "
            "L'impianto deve essere verificato prima della messa in servizio "
            "da tecnico abilitato e periodicamente durante i lavori."
        ),
        "keywords": ["impianto elettrico cantiere", "quadro cantiere", "CEI 64-8",
                     "IP44", "differenziale", "presa spina", "installazione temporanea",
                     "CEI EN 60439", "cavo cantiere", "art 118"],
        "tipo_macchina": ["escavatore", "escavatore idraulico", "gru", "gru a torre",
                          "piattaforma aerea", "piattaforma elevabile", "terna",
                          "pala caricatrice frontale", "betoniera", "pompa calcestruzzo",
                          "compressore", "generatore", "sega da cantiere"],
    },

    "psc_piano_sicurezza_cantiere": {
        "norma": "D.Lgs 81/08 Art. 100 + All. XV (Titolo IV)",
        "titolo": "Piano di Sicurezza e Coordinamento (PSC) — cantieri",
        "testo": (
            "Nei cantieri in cui è prevista la presenza di più imprese "
            "esecutive il committente designa il Coordinatore per la Sicurezza "
            "in fase di Progettazione (CSP) e il Coordinatore per la Sicurezza "
            "in fase di Esecuzione (CSE). Il PSC individua le misure di "
            "prevenzione e protezione per le lavorazioni interferenti, "
            "compresi i rischi derivanti dall'uso delle macchine. "
            "Ogni impresa esecutrice redige il Piano Operativo di Sicurezza "
            "(POS) con le specifiche macchine utilizzate, le relative schede "
            "di sicurezza e i DPI previsti."
        ),
        "keywords": ["PSC", "POS", "coordinatore sicurezza", "CSP", "CSE",
                     "piano sicurezza", "cantiere", "interferenze", "committente",
                     "imprese esecutrici", "lavorazioni interferenti"],
        "tipo_macchina": ["escavatore", "escavatore idraulico",
                          "gru", "gru a torre", "gru su autocarro",
                          "piattaforma aerea", "piattaforma elevabile",
                          "pala caricatrice frontale", "terna", "dumper",
                          "pompa calcestruzzo", "autogrù", "rullo compattatore",
                          "finitrice", "macchina movimento terra"],
    },

    "protezione_scariche_atmosferiche": {
        "norma": "D.Lgs 81/08 Art. 84-85 + CEI EN 62305",
        "titolo": "Protezione dai fulmini e scariche atmosferiche",
        "testo": (
            "Il datore di lavoro provvede affinché gli edifici, gli "
            "impianti, le strutture e le attrezzature siano protetti "
            "dagli effetti dei fulmini secondo le norme tecniche vigenti "
            "(CEI EN 62305). Le macchine da cantiere con sviluppo verticale "
            "significativo (gru a torre, piattaforme elevabili) devono "
            "essere messe in sicurezza o abbassate in caso di pericolo "
            "di temporale imminente. L'operatore deve abbandonare la cabina."
        ),
        "keywords": ["fulmine", "scarica atmosferica", "temporale",
                     "protezione fulmini", "messa a terra", "LPS",
                     "scariche", "parafulmine"],
        "tipo_macchina": ["gru a torre", "gru su autocarro", "gru mobile",
                          "piattaforma aerea", "piattaforma elevabile",
                          "sollevatore telescopico", "autogrù"],
    },

    "messa_a_terra_macchine": {
        "norma": "D.Lgs 81/08 All. V punto 5 + CEI EN 60204-1",
        "titolo": "Equipaggiamento elettrico delle macchine — messa a terra",
        "testo": (
            "L'equipaggiamento elettrico delle macchine deve essere conforme "
            "alla norma CEI EN 60204-1. Le masse metalliche delle macchine "
            "devono essere collegate a terra. I circuiti di protezione "
            "devono garantire la continuità della messa a terra anche "
            "durante le operazioni di manutenzione. Il grado di protezione "
            "dell'involucro elettrico deve essere adeguato alle condizioni "
            "di utilizzo (minimo IP54 per macchine da cantiere). "
            "La verifica dell'impianto elettrico della macchina deve essere "
            "eseguita da personale qualificato (PES/PAV)."
        ),
        "keywords": ["messa a terra", "terra", "CEI EN 60204", "IP54",
                     "protezione involucro", "PES", "PAV", "equipaggiamento elettrico",
                     "dispersore", "continuità terra", "isolamento"],
        "tipo_macchina": ["*"],
    },

    "rischio_termico_macchine": {
        "norma": "D.Lgs 81/08 All. V punto 8",
        "titolo": "Rischio termico — superfici calde, liquidi e vapori",
        "testo": (
            "Le attrezzature di lavoro che producono o trasmettono calore, "
            "freddo, vapori o gas devono essere dotate di sistemi di "
            "coibentazione, schermatura o segnalazione idonei a prevenire "
            "ustioni da contatto o inalazione. Le tubazioni e i serbatoi "
            "contenenti fluidi caldi (olio idraulico, acqua di raffreddamento, "
            "gas di scarico) devono essere isolati o protetti nelle zone "
            "accessibili all'operatore. La temperatura delle superfici "
            "accessibili non deve superare i 43°C (norma EN 563)."
        ),
        "keywords": ["termico", "calore", "ustione", "superfici calde",
                     "olio caldo", "vapore", "temperatura", "scottatura",
                     "coibentazione", "schermatura termica", "EN 563"],
        "tipo_macchina": ["*"],
    },

    "loto_consignazione_energetica": {
        "norma": "D.Lgs 81/08 All. V punto 4 + CEI EN 60204-1 par. 5.4",
        "titolo": "Isolamento e consignazione energetica (LOTO)",
        "testo": (
            "Prima di qualsiasi intervento di manutenzione, regolazione o "
            "riparazione le attrezzature devono essere fermate e isolate da "
            "tutte le fonti di energia (elettrica, pneumatica, idraulica, "
            "meccanica). Le procedure di Lock-Out/Tag-Out (LOTO) devono "
            "essere documentate e il personale deve essere formato. "
            "I dispositivi di isolamento devono essere bloccabili in "
            "posizione di sicurezza (lucchettabili). L'energia residua "
            "(pressione idraulica, gravità, condensatori) deve essere "
            "dissipata prima dell'intervento."
        ),
        "keywords": ["LOTO", "lock out", "tag out", "consignazione",
                     "isolamento energetico", "manutenzione sicura",
                     "sezionatore", "pressione residua", "energia residua",
                     "lucchetto sicurezza", "messa in sicurezza"],
        "tipo_macchina": ["*"],
    },

    "ergonomia_posto_operatore": {
        "norma": "D.Lgs 81/08 All. V punto 1.6 + EN ISO 9355",
        "titolo": "Ergonomia del posto di lavoro — cabina e comandi",
        "testo": (
            "Il posto di lavoro e la posizione dei comandi devono rispettare "
            "i principi ergonomici per ridurre l'affaticamento e prevenire "
            "disturbi muscolo-scheletrici. I comandi devono essere "
            "identificabili, raggiungibili senza posture incongrue e "
            "protetti dall'azionamento accidentale. La visibilità dal posto "
            "di guida deve coprire le zone pericolose. I sedili delle "
            "macchine mobili devono essere regolabili e dotati di "
            "ammortizzazione (ISO 7096). L'accesso alla cabina deve "
            "essere sicuro (gradini, corrimano, EN ISO 2867)."
        ),
        "keywords": ["ergonomia", "cabina", "sedile", "postura", "comandi",
                     "visibilità", "ammortizzazione", "muscolo-scheletrico",
                     "corrimano", "gradini", "accesso cabina", "ISO 7096"],
        "tipo_macchina": ["*"],
    },

    "rischio_schiacciamento_cesoiamento": {
        "norma": "D.Lgs 81/08 All. V punto 3.2 + EN ISO 13857",
        "titolo": "Rischio schiacciamento, cesoiamento e intrappolamento",
        "testo": (
            "Le parti della macchina che possono causare schiacciamento, "
            "cesoiamento, taglio o intrappolamento devono essere protette "
            "con ripari fissi, mobili interbloccati o dispositivi di "
            "protezione (barriere fotoelettriche, tappeti sensibili). "
            "Le distanze di sicurezza dagli organi in movimento devono "
            "rispettare la norma EN ISO 13857. I punti di pericolo devono "
            "essere segnalati con pittogrammi e colorazione di avvertimento "
            "(giallo/nero). Le zone di schiacciamento tra parti mobili "
            "della macchina devono avere uno spazio minimo di 500 mm "
            "o essere segregate."
        ),
        "keywords": ["schiacciamento", "cesoiamento", "intrappolamento",
                     "taglio", "riparo", "barriera", "fotoelettrica",
                     "tappeto sensibile", "EN ISO 13857", "punto pericoloso",
                     "distanza sicurezza", "interbloccato"],
        "tipo_macchina": ["*"],
    },

    "rischio_agenti_chimici_macchine": {
        "norma": "D.Lgs 81/08 Art. 221-232 (Titolo IX Capo I)",
        "titolo": "Rischio agenti chimici — oli, lubrificanti, gas di scarico",
        "testo": (
            "Il datore di lavoro valuta i rischi derivanti da agenti chimici "
            "presenti nelle macchine: oli minerali (cancerogeni classificati), "
            "fluidi idraulici, lubrificanti, refrigeranti, gas di scarico "
            "(CO, NOx, particolato). Deve essere redatta la valutazione del "
            "rischio chimico con schede di sicurezza (SDS) aggiornate. "
            "In ambienti chiusi o scarsamente ventilati le macchine con "
            "motore a combustione interna richiedono sistemi di aspirazione "
            "o l'uso di versioni elettriche. I fluidi di raffreddamento e "
            "idraulici devono essere smaltiti come rifiuti speciali."
        ),
        "keywords": ["agenti chimici", "olio minerale", "lubrificante",
                     "gas di scarico", "CO", "monossido", "SDS",
                     "scheda sicurezza", "fluido idraulico", "refrigerante",
                     "ventilazione", "cancerogeno", "smaltimento"],
        "tipo_macchina": ["*"],
    },

    "rischio_esplosione_atex": {
        "norma": "D.Lgs 81/08 Art. 287-296 (Titolo XI) + Dir. ATEX 2014/34/UE",
        "titolo": "Rischio esplosione — atmosfere esplosive (ATEX)",
        "testo": (
            "In presenza di atmosfere potenzialmente esplosive (polveri, "
            "gas, vapori infiammabili) le macchine devono essere conformi "
            "alla Direttiva ATEX 2014/34/UE e classificate per la zona "
            "di utilizzo. Il datore di lavoro predispone il Documento sulla "
            "Protezione contro le Esplosioni (DPCE). Le macchine standard "
            "non possono essere utilizzate in zone ATEX 0, 1, 2 (gas) o "
            "20, 21, 22 (polveri) senza specifica certificazione Ex. "
            "Sono a rischio: silos, impianti chimici, verniciatura, "
            "stazioni carburante, miniere."
        ),
        "keywords": ["ATEX", "esplosione", "atmosfera esplosiva", "Ex",
                     "zona 0", "zona 1", "zona 2", "polveri esplosive",
                     "gas infiammabile", "DPCE", "antideflagrante"],
        "tipo_macchina": ["*"],
    },

    "rischio_investimento_macchine_semoventi": {
        "norma": "D.Lgs 81/08 All. V punto 1.3 + All. VI",
        "titolo": "Rischio investimento — macchine semoventi",
        "testo": (
            "Le macchine semoventi devono essere dotate di dispositivi "
            "per prevenire l'investimento dei lavoratori a terra: "
            "segnalatori acustici (avvisatori di retromarcia), specchi "
            "retrovisori o telecamere, illuminazione adeguata. "
            "La velocità deve essere limitata in funzione delle condizioni "
            "operative. L'operatore deve verificare l'area circostante "
            "prima di ogni manovra. In cantiere devono essere predisposte "
            "vie di circolazione separate per macchine e pedoni. "
            "Il datore di lavoro deve adottare misure organizzative per "
            "impedire la presenza di lavoratori nelle zone di azione "
            "delle macchine (All. VI D.Lgs 81/08)."
        ),
        "keywords": ["investimento", "retromarcia", "avvisatore",
                     "pedone", "macchina semovente", "manovra",
                     "specchio", "telecamera retromarcia", "zona di azione",
                     "separazione pedoni", "circolazione"],
        "tipo_macchina": ["*"],
    },

    "requisiti_essenziali_direttiva_macchine": {
        "norma": "Dir. 2006/42/CE All. I — recepita con D.Lgs. 17/2010",
        "titolo": "Requisiti essenziali di sicurezza — Direttiva Macchine",
        "testo": (
            "Le macchine immesse sul mercato UE devono soddisfare i "
            "Requisiti Essenziali di Sicurezza e di Tutela della Salute "
            "(RESS) dell'Allegato I della Direttiva Macchine. I principali "
            "riguardano: principi di integrazione della sicurezza in fase "
            "progettuale, materiali e prodotti idonei, illuminazione "
            "incorporata, manutenzione sicura, informazioni e avvertenze, "
            "marcatura CE con numero di serie e anno di costruzione, "
            "fascicolo tecnico conservato per 10 anni. Le norme armonizzate "
            "EN ISO 12100 (principi generali) e le norme di tipo B e C "
            "specifiche per categoria costituiscono presunzione di conformità."
        ),
        "keywords": ["direttiva macchine", "RESS", "requisiti essenziali",
                     "D.Lgs 17/2010", "EN ISO 12100", "fascicolo tecnico",
                     "presunzione conformità", "norme armonizzate",
                     "tipo B", "tipo C", "progettazione sicurezza"],
        "tipo_macchina": ["*"],
    },

    "segnaletica_cantiere": {
        "norma": "D.Lgs 81/08 All. V punto 11.1-11.2",
        "titolo": "Segnaletica e pittogrammi obbligatori",
        "testo": (
            "Le attrezzature devono essere identificate con targhette "
            "indicanti dati costruttivi, portata massima e altri limiti "
            "operativi. I pittogrammi di pericolo devono essere mantenuti "
            "leggibili. La targa del costruttore deve riportare: nome/indirizzo "
            "fabbricante, anno di costruzione, numero di serie, marcatura CE."
        ),
        "keywords": ["targa", "pittogramma", "etichetta", "segnaletica",
                     "marcatura", "numero serie", "portata targa"],
        "tipo_macchina": ["*"],
    },

}


def get_riferimenti_per_tipo(machine_type: str) -> list[dict]:
    """
    Restituisce tutti i riferimenti applicabili a un tipo macchina.
    Include sempre quelli con tipo_macchina=["*"] più quelli
    specifici per il tipo richiesto (match parziale case-insensitive).
    """
    if not machine_type:
        return [ref for ref in RIFERIMENTI.values() if "*" in ref["tipo_macchina"]]

    machine_lower = machine_type.lower()
    result = []
    for ref in RIFERIMENTI.values():
        tipi = ref["tipo_macchina"]
        if "*" in tipi:
            result.append(ref)
        elif any(t.lower() in machine_lower or machine_lower in t.lower() for t in tipi):
            result.append(ref)
    return result


def get_riferimento_by_keywords(keywords: list[str]) -> list[dict]:
    """
    Cerca riferimenti per keyword match.
    Usato quando l'AI identifica un rischio e cerca la norma corretta.
    """
    kw_lower = [k.lower() for k in keywords]
    result = []
    seen = set()
    for key, ref in RIFERIMENTI.items():
        if key in seen:
            continue
        ref_kw = [k.lower() for k in ref["keywords"]]
        if any(k in ref_kw for k in kw_lower):
            result.append(ref)
            seen.add(key)
    return result


def format_for_prompt(riferimenti: list[dict]) -> str:
    """
    Formatta i riferimenti come blocco testo per il prompt AI.
    Ritorna stringa vuota se non ci sono riferimenti.
    """
    if not riferimenti:
        return ""
    lines = ["## RIFERIMENTI NORMATIVI D.Lgs 81/08 APPLICABILI\n"]
    for ref in riferimenti:
        lines.append(f"**{ref['norma']} — {ref['titolo']}**")
        lines.append(ref["testo"])
        lines.append("")
    lines.append(
        "ISTRUZIONE VINCOLANTE: Usa SOLO questi riferimenti per le prescrizioni "
        "D.Lgs 81/08. Non citare articoli non presenti in questo elenco. "
        "Se un rischio non trova copertura negli articoli qui elencati, "
        "lascia prescrizione_precompilata='' invece di inventare un articolo."
    )
    return "\n".join(lines)
