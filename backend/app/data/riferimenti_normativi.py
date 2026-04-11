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
        "tipo_macchina": ["escavatore", "escavatore idraulico",
                          "carrello elevatore", "dumper", "terna",
                          "pala meccanica", "pala gommata",
                          "pala caricatrice frontale", "macchina movimento terra",
                          "rullo compattatore", "finitrice"],
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
                          "ascensore di cantiere", "terna"],
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
        "tipo_macchina": ["escavatore", "escavatore idraulico",
                          "rullo compattatore", "piastra vibrante",
                          "martello demolitore", "compattatore",
                          "pala caricatrice frontale", "finitrice",
                          "macchina movimento terra"],
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
