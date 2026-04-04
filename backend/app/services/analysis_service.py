"""
Generazione della scheda di sicurezza dal manuale del macchinario.
Usa Claude (L1) o Gemini (L2) per analizzare PDF e produrre JSON strutturato.
Strategia dual-source: INAIL (normativa) + produttore (raccomandazioni specifiche).
"""
import json
import re
from typing import Optional
from app.config import settings
from app.models.responses import SafetyCard
from app.services import pdf_service
from app.data.allegato_v_data import get_machine_category, format_requisiti_for_prompt


SYSTEM_PROMPT = """Sei un esperto di sicurezza sul lavoro specializzato nell'analisi di manuali tecnici di macchinari industriali e da cantiere, con profonda conoscenza di:
- D.Lgs. 81/2008 (Testo Unico sulla Sicurezza sul Lavoro) e relativi Allegati
- Direttive Macchine 89/392/CEE, 98/37/CE e 2006/42/CE
- Accordi Stato-Regioni (es. 22/02/2012 per abilitazioni operatori)
- Norme armonizzate EN, UNI EN, ISO applicabili ai macchinari

Il tuo compito è analizzare la documentazione fornita (manuali ufficiali, schede INAIL, normative) e produrre una scheda di sicurezza strutturata che un ISPETTORE DEL LAVORO possa utilizzare DIRETTAMENTE durante un accesso ispettivo in un cantiere o stabilimento industriale italiano.

PRINCIPI FONDAMENTALI — applicali sempre:
1. FEDELTÀ ALLA FONTE: Estrai SOLO ciò che è effettivamente scritto nel documento fornito. Non integrare con conoscenze generali quando hai un manuale reale tra le mani. Se un'informazione non è presente nel documento, non inventarla — lascia il campo vuoto o indica "non specificato nel documento".
2. SPECIFICITÀ ISPETTIVA: Le voci della checklist e delle verifiche devono descrivere azioni fisicamente eseguibili sul posto (cosa guardare, toccare, misurare, aprire, richiedere). Evita voci generiche come "Verifica la sicurezza" — ogni voce deve rispondere a: COSA verificare, DOVE trovarlo sulla macchina, COME stabilire se è conforme.
3. ORDINE PER GRAVITÀ: Ordina i rischi dalla criticità più alta (rischio di morte/invalidità permanente) alla più bassa. Usa il tag [ALTA/MEDIA/BASSA] inline nel testo.
4. LINGUAGGIO NORMATIVO: Usa la terminologia precisa del D.Lgs. 81/2008 e delle norme armonizzate. Per citare obblighi usa il formato: [Art. X D.Lgs. 81/08] o [EN 280 sez. Y].
5. VALORI NUMERICI: Includi SOLO valori (pressioni, portate, pendenze, temperature) che sono esplicitamente riportati nel documento analizzato. NON generare valori plausibili non presenti nel testo.

LINGUA DI RISPOSTA: Rispondi ESCLUSIVAMENTE in italiano, indipendentemente dalla lingua del manuale. Traduci tutti i termini tecnici, le avvertenze e le procedure in italiano corretto e preciso. Non lasciare mai parole straniere nel JSON."""


def _detect_language(text: str) -> str:
    """
    Rileva la lingua del testo estratto dal PDF.
    Ritorna: 'it', 'de', 'fr', 'en', 'unknown'.
    """
    if not text or len(text.strip()) < 100:
        return "unknown"
    sample = " " + text[:4000].lower() + " "
    scores = {
        "it": sum(1 for w in [
            " della ", " dello ", " degli ", " delle ", " sono ", " questo ",
            " sicurezza ", " pericolo ", " attenzione ", " avvertenza ",
            " operatore ", " macchina ", " verificare ", " dispositivo ",
        ] if w in sample),
        "de": sum(1 for w in [
            " die ", " der ", " das ", " und ", " nicht ", " sicherheit ",
            " gefahr ", " achtung ", " warnung ", " betrieb ", " maschine ",
            " hinweis ", " bedienung ", " anlage ",
        ] if w in sample),
        "fr": sum(1 for w in [
            " les ", " des ", " est ", " pas ", " pour ", " avec ",
            " sécurité ", " danger ", " attention ", " avertissement ",
            " opérateur ", " machine ", " utilisation ", " consigne ",
        ] if w in sample),
        "en": sum(1 for w in [
            " the ", " and ", " for ", " this ", " safety ", " warning ",
            " danger ", " caution ", " operator ", " machine ", " equipment ",
            " instruction ", " manual ", " notice ",
        ] if w in sample),
    }
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] >= 3 else "unknown"


def _translation_note(lang: str) -> str:
    """Restituisce una nota di traduzione rinforzata per lingue non italiane."""
    labels = {
        "de": "TEDESCO",
        "fr": "FRANCESE",
        "en": "INGLESE",
    }
    if lang not in labels:
        return ""
    return (
        f"\n\n⚠ ATTENZIONE: Il manuale è in {labels[lang]}. "
        "DEVI tradurre TUTTO in italiano: nomi di componenti, avvertenze, procedure, unità di misura. "
        "Non lasciare nessuna parola in lingua straniera nel JSON di risposta. "
        "Usa la terminologia tecnica italiana normalizzata (D.Lgs. 81/2008)."
    )


def _build_inail_prompt() -> str:
    """
    Prompt per analisi scheda INAIL: estrae rischi normativi, DPI, dispositivi di sicurezza,
    abilitazioni operatore, documenti da richiedere, verifiche periodiche, checklist sopralluogo.
    """
    return """Analizza questa scheda INAIL o documento normativo ed estrai le informazioni di sicurezza nel seguente formato JSON:

{
  "rischi_principali": [
    "[ALTA/MEDIA/BASSA] descrizione rischio specifico per questa categoria di macchina [Art. XX D.Lgs. 81/08 o norma applicabile]"
  ],
  "dispositivi_protezione": [
    "DPI individuale (es. 'Elmetto EN 397', 'Imbracatura anticaduta EN 361 cat. C') OPPURE protezione collettiva (es. 'Parapetto perimetrale h≥1m') richiesta dalla normativa"
  ],
  "rischi_residui": [
    "rischio che persiste anche con tutte le protezioni attive — specifica PERCHÉ non è eliminabile (es. 'Rumore residuo >85 dB(A) nonostante insonorizzazione: uso obbligatorio di protezioni uditive EN 352')"
  ],
  "dispositivi_sicurezza": [
    {
      "nome": "Nome esatto del dispositivo come indicato nella normativa (es. 'Riparo fisso organi di trasmissione del moto')",
      "tipo": "interblocco | sensore | riparo | arresto_emergenza | segnalazione | limitatore",
      "descrizione": "Funzione del dispositivo e dove deve essere installato fisicamente sulla macchina",
      "verifica_ispezione": "Verifica/Controlla/Accertati [DOVE trovarlo fisicamente] — [COME verificare che funzioni o sia presente] [rif. normativo se applicabile]"
    }
  ],
  "abilitazione_operatore": "Formazione e/o patentino obbligatorio per l'operatore secondo normativa italiana. Esempio: 'Abilitazione obbligatoria Accordo Stato-Regioni 22/02/2012 — corso teorico-pratico specifico per PLE (minimo 10h teoriche + addestramento pratico)'. Null se non previsto per questa categoria.",
  "documenti_da_richiedere": [
    "Documento che l'ispettore deve richiedere al datore di lavoro, con riferimento normativo che ne impone la tenuta (es. 'Dichiarazione di conformità CE [Dir. 2006/42/CE Art. 7]', 'Registro verifiche periodiche [Art. 71 c.11 D.Lgs. 81/08]', 'Attestato formazione operatore [Art. 37 D.Lgs. 81/08 + Accordo S-R 22/02/2012]')"
  ],
  "verifiche_periodiche": "Obblighi di verifica periodica previsti dalla normativa: cadenza, soggetto abilitato, riferimento normativo. Esempio: 'Verifica annuale da soggetto abilitato INAIL/ASL ex Art. 71 c.11 D.Lgs. 81/08 + Allegato VII — per apparecchi di sollevamento con portata >200 kg'. Null se non previsti per questa categoria.",
  "checklist": [
    "Verifica [componente/elemento specifico] — [dove trovarlo fisicamente sulla macchina] — [criterio di conformità: cosa rende la verifica positiva o negativa] [Art. X D.Lgs. 81/08 o Allegato Y punto Z]"
  ],
  "note": "requisiti normativi aggiuntivi, riferimenti specifici D.Lgs. 81/08, norme armonizzate applicabili, registri obbligatori"
}

VINCOLI:
- rischi_principali: 3-8 rischi, ORDINATI dalla gravità più ALTA alla più BASSA. Per ogni rischio includi il tag [ALTA/MEDIA/BASSA] e il riferimento normativo dove applicabile.
- dispositivi_protezione: distingui tra DPI (cosa INDOSSA l'operatore) e protezioni collettive (dispositivi sulla macchina o nell'area). 3-8 elementi SPECIFICI per questa categoria.
- dispositivi_sicurezza: 2-5 dispositivi di sicurezza richiesti dalla normativa per questa categoria di macchina.
- checklist: 4-6 voci azionabili IMMEDIATAMENTE in sopralluogo. Ogni voce DEVE rispondere a tre domande: COSA verificare, DOVE trovarlo, COME stabilire la conformità. Includi il riferimento normativo tra parentesi quadre.
- documenti_da_richiedere: 3-6 documenti con il riferimento normativo che ne impone la tenuta/esibizione. ESSENZIALE per l'attività ispettiva.
- abilitazione_operatore: se prevista dall'Accordo Stato-Regioni 22/02/2012 o da normativa specifica, descrivila in dettaglio (tipo corso, durata minima, ente formatore).
- FEDELTÀ ALLA FONTE: Estrai SOLO ciò che è scritto in questo documento. Non integrare con conoscenze generali.
- Usa terminologia precisa del D.Lgs. 81/2008.
- Rispondi SOLO con il JSON valido."""


def _build_producer_prompt(brand: str, model: str) -> str:
    """
    Prompt per analisi manuale produttore: estrae raccomandazioni operative specifiche,
    limiti operativi con valori numerici, procedure di emergenza, pittogrammi, checklist preuso.
    """
    return f"""Analizza il manuale del macchinario {brand} {model} ed estrai le informazioni di sicurezza specifiche del costruttore nel seguente formato JSON:

{{
  "raccomandazioni_produttore": [
    "prescrizione o istruzione operativa SPECIFICA del costruttore {brand} per il modello {model} — NON generiche [sezione o pag. manuale dove trovata]"
  ],
  "verifiche_sicurezza": [
    "controllo prescritto dal costruttore prima/durante/dopo l'uso — specifica QUANDO eseguirlo e CON QUALE FREQUENZA [rif. sezione manuale]"
  ],
  "rischi_specifici_modello": [
    "rischio specifico di questo modello {model} non coperto dalla normativa generale — con spiegazione tecnica"
  ],
  "dispositivi_sicurezza": [
    {{
      "nome": "Nome esatto del dispositivo come indicato nel manuale {brand} {model} (es. 'Sensore pressione circuito frenante', 'Limitatore di carico elettronico')",
      "tipo": "interblocco | sensore | riparo | arresto_emergenza | segnalazione | limitatore",
      "descrizione": "Funzione del dispositivo e POSIZIONE FISICA sulla macchina {model} (es. 'Posizionato sul circuito frenante posteriore, accessibile dal vano motore lato destro')",
      "verifica_ispezione": "Verifica/Controlla/Accertati [dove trovarlo fisicamente su questa macchina] — [come verificare che funzioni] [sezione manuale di riferimento]"
    }}
  ],
  "limiti_operativi": [
    "limite con VALORE NUMERICO e unità di misura come indicato nel manuale (es. 'Portata massima: 3.500 kg [Sez. 2.4]', 'Pendenza massima operativa: 30% [pag. 18]', 'Pressione idraulica max: 350 bar [Sez. 5.1]')"
  ],
  "procedure_emergenza": [
    "Procedura specifica per {brand} {model}: Passo 1 — [azione]. Passo 2 — [azione]. Passo 3 — [azione]. [Sez. manuale]"
  ],
  "pittogrammi_sicurezza": [
    "pittogramma o avvertenza obbligatoria che deve essere presente e leggibile sulla macchina — specifica posizione (es. 'Pittogramma PERICOLO SCHIACCIAMENTO — pannello laterale sinistro cabina [pag. 12 manuale]')"
  ],
  "checklist": [
    "Verifica [componente fisico specifico di {brand} {model}] — [dove trovarlo sulla macchina] — [criterio di conformità] [Sez. X.X o pag. YY manuale]"
  ],
  "note": "avvertenze particolari del costruttore, condizioni d'uso, limitazioni ambientali o operative"
}}

VINCOLI:
- raccomandazioni_produttore: 3-8 elementi SPECIFICI per {brand} {model}, NON generici per la categoria. Per ogni voce indica la sezione o pagina del manuale tra parentesi quadre.
- dispositivi_sicurezza: 3-6 dispositivi di sicurezza FISICAMENTE INSTALLATI su {brand} {model} dal costruttore (interblocchi, sensori, ripari fissi/mobili, pulsanti emergenza, limitatori, valvole). Sii specifico sulla posizione fisica.
- limiti_operativi: includi SOLO valori ESPLICITAMENTE riportati nel manuale. NON generare valori ipotetici anche se plausibili per la categoria. Se non presenti, lascia la lista vuota [].
- procedure_emergenza: passi numerati specifici per {brand} {model}. Se il manuale descrive più procedure di emergenza (incendio, ribaltamento, cedimento idraulico), includile tutte.
- pittogrammi_sicurezza: segnala SOLO i pittogrammi esplicitamente citati nel manuale con la loro posizione sulla macchina.
- checklist: 5-8 voci azionabili in sopralluogo SPECIFICHE per {brand} {model}. Ogni voce: verbo imperativo + cosa guardare/toccare + dove + criterio di conformità + riferimento sezione/pagina manuale.
- FEDELTÀ ALLA FONTE: Estrai SOLO ciò che è scritto in questo manuale. Per elementi non presenti, lascia la lista vuota — NON integrare con conoscenze generali sul tipo di macchina.
- Se il manuale è in altra lingua: TRADUCI tutto in italiano. Non lasciare termini stranieri.
- Rispondi SOLO con il JSON valido."""


def _build_analysis_prompt(brand: str, model: str) -> str:
    """Prompt generico per analisi singola fonte — combina aspetti normativi e raccomandazioni costruttore."""
    return f"""Analizza questo documento relativo al macchinario {brand} {model} ed estrai le informazioni di sicurezza nel seguente formato JSON:

{{
  "rischi_principali": [
    "[ALTA/MEDIA/BASSA] descrizione rischio specifico e concreto per {brand} {model} [riferimento normativo o sezione documento se applicabile]"
  ],
  "dispositivi_protezione": [
    "DPI (cosa indossa l'operatore) OPPURE protezione collettiva — specifica e concreta per questo macchinario"
  ],
  "raccomandazioni_produttore": [
    "prescrizione o istruzione diretta del costruttore {brand} per {model} [sezione documento]"
  ],
  "rischi_residui": [
    "rischio che persiste anche con tutte le protezioni attive — spiega PERCHÉ non eliminabile"
  ],
  "dispositivi_sicurezza": [
    {{
      "nome": "Nome esatto del dispositivo installato su {brand} {model} (es. 'Pulsante di emergenza a fungo rosso')",
      "tipo": "interblocco | sensore | riparo | arresto_emergenza | segnalazione | limitatore",
      "descrizione": "Funzione del dispositivo e posizione fisica sulla macchina",
      "verifica_ispezione": "Verifica/Controlla/Accertati [dove trovarlo fisicamente] — [come verificare il funzionamento] [rif. sezione documento]"
    }}
  ],
  "abilitazione_operatore": "Formazione obbligatoria richiesta dalla normativa italiana per questo tipo di macchina (Accordo Stato-Regioni 22/02/2012 o normativa specifica). Null se non obbligatoria.",
  "documenti_da_richiedere": [
    "documento che l'ispettore deve richiedere al datore di lavoro [riferimento normativo che lo impone]"
  ],
  "verifiche_periodiche": "Obblighi di verifica periodica con cadenza e soggetto abilitato [Art. 71 c.11 D.Lgs. 81/08 o normativa specifica]. Null se non previsti.",
  "limiti_operativi": [
    "limite con VALORE NUMERICO e unità di misura esplicitamente riportato nel documento (es. 'Portata massima: 3.500 kg')"
  ],
  "procedure_emergenza": [
    "Procedura emergenza specifica: Passo 1 — [azione]. Passo 2 — [azione]. [rif. sezione documento]"
  ],
  "pittogrammi_sicurezza": [
    "pittogramma o avvertenza che deve essere presente e leggibile sulla macchina — con posizione [rif. documento]"
  ],
  "checklist": [
    "Verifica [elemento concreto fisico] — [dove trovarlo sulla macchina] — [come stabilire se conforme] [rif. normativo o sezione documento]"
  ],
  "note": "osservazioni aggiuntive di sicurezza, limiti d'uso, condizioni ambientali"
}}

VINCOLI:
- rischi_principali: 3-8 rischi, ORDINATI da ALTA a BASSA gravità. Includi tag [ALTA/MEDIA/BASSA] e riferimento normativo/documentale.
- dispositivi_sicurezza: 3-6 dispositivi di sicurezza FISICAMENTE INSTALLATI sulla macchina dal costruttore (interblocchi, sensori, ripari, pulsanti emergenza, limitatori, valvole di sicurezza). Sii specifico sulla posizione fisica.
- checklist: 5-10 voci azionabili IMMEDIATAMENTE in sopralluogo. Ogni voce deve rispondere a: COSA verificare, DOVE trovarlo, COME stabilire la conformità. Includi riferimento sezione o articolo normativo tra parentesi quadre.
- limiti_operativi: includi SOLO valori ESPLICITAMENTE presenti nel documento — NON generare valori ipotetici.
- documenti_da_richiedere: 3-5 documenti essenziali per l'accesso ispettivo con riferimento normativo che ne impone la tenuta.
- FEDELTÀ ALLA FONTE: Estrai SOLO ciò che è scritto nel documento fornito.
- Se il documento è in altra lingua: TRADUCI tutto in italiano. NON lasciare termini stranieri.
- Usa terminologia del D.Lgs. 81/2008 e delle norme armonizzate dove appropriato.
- Rispondi SOLO con il JSON valido."""


FALLBACK_PROMPT_TEMPLATE = """Non è disponibile il manuale ufficiale del macchinario {brand} {model}.

STRATEGIA DI ANALISI (applica nell'ordine, sii ONESTO sulla certezza):
1. Se conosci questo modello esatto ({brand} {model}): usa quella conoscenza diretta → confidence_ai = "high"
2. Se conosci modelli simili della stessa marca (versioni precedenti/adiacenti): basa l'analisi su quelli, indicalo nelle note → confidence_ai = "medium"
3. Se conosci solo la categoria generica: usa D.Lgs. 81/2008 e conoscenza della categoria → confidence_ai = "low"

IMPORTANTE: Sii conservativo. È preferibile una scheda parziale ma affidabile piuttosto che una completa ma con dati inventati. Per i limiti operativi (portate, pressioni) NON generare valori ipotetici — lascia la lista vuota se non sei certo.

Genera una scheda di sicurezza INDICATIVA:

{{
  "rischi_principali": [
    "[ALTA/MEDIA/BASSA] rischio specifico per {brand} {model} ordinato per gravità [riferimento normativo D.Lgs. 81/08 dove applicabile]"
  ],
  "dispositivi_protezione": [
    "DPI o protezione collettiva richiesta per questa categoria di macchina"
  ],
  "raccomandazioni_produttore": [
    "raccomandazione basata sulla conoscenza di {brand} {model} o di modelli simili"
  ],
  "rischi_residui": [
    "rischio residuo tipico di questa categoria con spiegazione del perché non eliminabile"
  ],
  "dispositivi_sicurezza": [
    {{
      "nome": "Nome del dispositivo di sicurezza tipico per {brand} {model}",
      "tipo": "interblocco | sensore | riparo | arresto_emergenza | segnalazione | limitatore",
      "descrizione": "Funzione del dispositivo e posizione tipica sulla macchina",
      "verifica_ispezione": "Verifica/Controlla/Accertati [dove trovarlo] — [come verificarlo]"
    }}
  ],
  "abilitazione_operatore": "Formazione obbligatoria prevista dalla normativa italiana per questa categoria di macchina (Accordo Stato-Regioni 22/02/2012 se applicabile). Null se non prevista.",
  "documenti_da_richiedere": [
    "documento essenziale per l'ispettore con riferimento normativo che ne impone la tenuta"
  ],
  "verifiche_periodiche": "Obblighi di verifica periodica per questa categoria [Art. 71 c.11 D.Lgs. 81/08 o norma specifica]. Null se non previsti.",
  "limiti_operativi": [],
  "procedure_emergenza": [
    "Procedura di emergenza tipica per questa categoria: Passo 1 — [azione]. Passo 2 — [azione]."
  ],
  "pittogrammi_sicurezza": [
    "pittogramma di avvertenza tipicamente presente su questa categoria di macchina"
  ],
  "checklist": [
    "Verifica [elemento concreto fisico] — [dove trovarlo] — [come valutare la conformità] [Art. X D.Lgs. 81/08]"
  ],
  "confidence_ai": "high | medium | low",
  "note": "ATTENZIONE: Scheda generata da AI senza consultazione della documentazione ufficiale del costruttore. Non utilizzare come unica fonte di riferimento per prescrizioni ispettive."
}}

VINCOLI:
- rischi_principali: 3-8 rischi ORDINATI da ALTA a BASSA gravità con tag [ALTA/MEDIA/BASSA]
- dispositivi_sicurezza: 2-5 dispositivi tipici per questa categoria — specifica posizione fisica sulla macchina
- checklist: 5-8 voci azionabili in sopralluogo con verbo imperativo + COSA + DOVE + COME
- documenti_da_richiedere: 3-5 documenti essenziali con riferimento normativo
- limiti_operativi: lascia SEMPRE [] — NON inventare valori numerici senza documentazione ufficiale
- confidence_ai: scegli onestamente (high/medium/low) in base alla strategia usata
- note: inizia SEMPRE con "ATTENZIONE: Scheda generata da AI senza...". Se hai usato modelli simili per l'analisi, aggiungilo DOPO il disclaimer.
- Rispondi SOLO con il JSON valido"""

ALLEGATO_V_EXTRA_FIELDS = """
Poiché la macchina è ANTE-1996 (Allegato V D.Lgs. 81/08), aggiungi nel JSON anche:

  "gap_ce_ante": "2-4 frasi che spiegano cosa mancherebbe a questa macchina rispetto alla Direttiva Macchine 2006/42/CE se fosse costruita oggi: requisiti strutturali, sistemi di sicurezza attivi, certificazioni. Tono tecnico-ispettivo.",
  "bozze_prescrizioni": [
    {{
      "req_id": "1.x",
      "titolo": "Nome del requisito",
      "criticita": "alta | media | bassa",
      "prescrizione": "Si prescrive al datore di lavoro, ai sensi dell'Art. 70 c.1 D.Lgs. 81/08 e del punto X.X Allegato V, di: [azione specifica e verificabile]. Termine: [30 giorni / immediato / da concordare con l'organo di vigilanza]."
    }}
  ]

VINCOLI prescrizioni:
- Genera SOLO le prescrizioni per i requisiti con criticità ALTA (non generare per media/bassa)
- Cita sempre Art. 70 c.1 D.Lgs. 81/08 e il punto specifico dell'Allegato V
- Il termine deve essere proporzionato alla gravità: "immediatamente" (rischio grave immediato), "entro 30 giorni" (rischio alto), "entro 90 giorni" (adeguamento strutturale)
- Usa il formato legale italiano formale in terza persona
- Le prescrizioni devono descrivere l'AZIONE RICHIESTA, non il problema
"""

REDUCE_PROMPT = """Hai ricevuto {n} analisi parziali di sezioni diverse dello stesso manuale.
Sintetizzale in un'unica scheda di sicurezza consolidata, eliminando duplicati e mantenendo le informazioni più rilevanti.

Analisi parziali:
{partial_analyses}

Restituisci UN SOLO JSON con la struttura completa:
{{
  "rischi_principali": [
    "descrizione rischio [ALTA/MEDIA/BASSA] — con riferimento normativo se presente"
  ],
  "dispositivi_protezione": ["DPI o protezione collettiva richiesta"],
  "raccomandazioni_produttore": ["prescrizione specifica del costruttore"],
  "rischi_residui": ["rischio residuo con spiegazione del perché non eliminabile"],
  "dispositivi_sicurezza": [
    {{
      "nome": "nome dispositivo",
      "tipo": "interblocco | sensore | riparo | arresto_emergenza | segnalazione | limitatore",
      "descrizione": "funzione e posizione fisica sulla macchina",
      "verifica_ispezione": "Verifica/Controlla/Accertati — dove trovarlo — come verificarlo"
    }}
  ],
  "abilitazione_operatore": "formazione o patentino obbligatorio per legge, null se non previsto",
  "documenti_da_richiedere": ["documento con riferimento normativo"],
  "verifiche_periodiche": "obbligo di verifica periodica con cadenza e soggetto abilitato, null se non previsto",
  "limiti_operativi": ["limite con valore numerico e unità di misura"],
  "procedure_emergenza": ["Passo 1: ... — Passo 2: ..."],
  "pittogrammi_sicurezza": ["avvertenza/pittogramma obbligatorio sulla macchina"],
  "checklist": [
    "Verifica [elemento fisico] — [dove trovarlo] — [criterio di conformità] [rif. normativo o sezione manuale]"
  ],
  "note": "avvertenze residue importanti"
}}

ISTRUZIONI DI CONSOLIDAMENTO:
- rischi_principali: ordina da ALTA a BASSA gravità; deduplica per contenuto semantico
- dispositivi_sicurezza: deduplica per nome (case-insensitive); mantieni la descrizione più completa tra i duplicati
- checklist: unisci tutte le voci, rimuovi i duplicati semantici, mantieni 5-10 voci ordinate per priorità ispettiva
- limiti_operativi: includi SOLO valori esplicitamente presenti nel manuale — non generare valori ipotetici
- Per ogni sezione lista: 3-8 elementi totali, preferendo i più specifici e verificabili
- Rispondi SOLO con il JSON valido."""


async def generate_safety_card(
    brand: str,
    model: str,
    # Nuova firma dual-source
    inail_bytes: Optional[bytes] = None,
    inail_url: Optional[str] = None,
    producer_bytes: Optional[bytes] = None,
    producer_url: Optional[str] = None,
    producer_page_count: int = 0,
    # Compatibilità legacy (singolo PDF)
    pdf_bytes: Optional[bytes] = None,
    pdf_url: Optional[str] = None,
    page_count: int = 0,
    # Contesto macchina
    machine_year: Optional[str] = None,
    machine_type: Optional[str] = None,
    is_ante_ce: bool = False,
    is_allegato_v: bool = False,
    norme: Optional[list] = None,
    # Label fonte del manuale produttore (es. "Produttore (Brand)" o "Manuale categoria simile")
    producer_source_label: Optional[str] = None,
) -> SafetyCard:
    """
    Genera la scheda di sicurezza combinando INAIL (normativa) + produttore (raccomandazioni).
    Se disponibile una sola fonte, usa quella. Senza fonti: fallback AI.
    """
    provider = settings.get_analysis_provider()

    # Compatibilità legacy: se arriva pdf_bytes dalla vecchia firma
    if pdf_bytes and not inail_bytes and not producer_bytes:
        inail_bytes = pdf_bytes
        inail_url = pdf_url
        producer_page_count = page_count

    has_inail = inail_bytes is not None
    has_producer = producer_bytes is not None

    # Smart Selector: determina categoria Allegato V dalla tipologia macchina OCR
    av_category_key, av_category_data = get_machine_category(machine_type)
    allegato_v_context = format_requisiti_for_prompt(av_category_data) if is_allegato_v else None

    if is_allegato_v:
        # Ante-1996: macchina costruita prima della prima Direttiva Macchine (89/392/CEE)
        # Nessuna marcatura CE, nessuna dichiarazione di conformità obbligatoria
        # Deve essere adeguata ai requisiti minimi dell'Allegato V D.Lgs. 81/08
        ante_ce_note = (
            f"🚨 Macchina ante-1996 (anno {machine_year}) — costruita prima della Direttiva Macchine 89/392/CEE. "
            "Non soggetta a marcatura CE. "
            "Deve essere adeguata ai REQUISITI MINIMI di sicurezza dell'Allegato V D.Lgs. 81/08 "
            "(Art. 70 c.1 D.Lgs. 81/08). "
            "Verificare: protezioni organi in moto, dispositivi di arresto, stabilità, illuminazione, "
            "avvertenze, messa a terra. Allegato V disponibile su: normattiva.it"
        )
    elif is_ante_ce:
        ante_ce_note = (
            f"⚠ Macchina ante-Direttiva Macchine 2006/42/CE (anno {machine_year}). "
            "Potrebbe non avere marcatura CE o averla secondo la direttiva precedente (98/37/CE). "
            "Normativa applicabile: D.Lgs. 626/1994 e s.m.i. "
            "Verificare la presenza della dichiarazione di conformità."
        )
    else:
        ante_ce_note = None

    effective_producer_label = producer_source_label or f"Produttore ({brand})"

    if not has_inail and not has_producer:
        card = await _generate_fallback(
            brand, model, provider, norme=norme or [],
            allegato_v_context=allegato_v_context,
        )
        if ante_ce_note:
            card.note = f"{ante_ce_note} | {card.note}" if card.note else ante_ce_note
    elif has_inail and has_producer:
        card = await _analyze_dual_source(
            brand, model, inail_bytes, inail_url, producer_bytes, producer_url, producer_page_count, provider,
            allegato_v_context=allegato_v_context,
            producer_source_label=effective_producer_label,
        )
        if ante_ce_note:
            card.note = f"{ante_ce_note} | {card.note}" if card.note else ante_ce_note
    elif has_inail:
        card = await _analyze_pdf_direct(
            brand, model, inail_bytes, inail_url, provider,
            allegato_v_context=allegato_v_context,
        )
        if ante_ce_note:
            card.note = f"{ante_ce_note} | {card.note}" if card.note else ante_ce_note
    elif producer_page_count <= 100:
        card = await _analyze_pdf_direct(
            brand, model, producer_bytes, producer_url, provider,
            allegato_v_context=allegato_v_context,
        )
        if ante_ce_note:
            card.note = f"{ante_ce_note} | {card.note}" if card.note else ante_ce_note
    else:
        card = await _analyze_pdf_map_reduce(brand, model, producer_bytes, producer_url, provider)
        if ante_ce_note:
            card.note = f"{ante_ce_note} | {card.note}" if card.note else ante_ce_note

    # Popola i campi Allegato V nella scheda
    if is_allegato_v:
        card.is_allegato_v = True
        card.machine_year = machine_year
        card.machine_type = machine_type
        card.allegato_v_category = av_category_key
        card.allegato_v_label = av_category_data["label"]
        card.allegato_v_requisiti = av_category_data["requisiti"]
        card.tabella_ce_ante = av_category_data["tabella_ce"]

    return card


async def _analyze_dual_source(
    brand: str, model: str,
    inail_bytes: bytes, inail_url: Optional[str],
    producer_bytes: bytes, producer_url: Optional[str],
    producer_pages: int,
    provider: str,
    allegato_v_context: Optional[str] = None,
    producer_source_label: Optional[str] = None,
) -> SafetyCard:
    """
    Analisi combinata: INAIL → rischi/DPI/residui; produttore → raccomandazioni specifiche.
    Le due analisi vengono eseguite in parallelo, poi fuse.
    """
    import asyncio

    inail_prompt = _build_inail_prompt()
    producer_prompt = _build_producer_prompt(brand, model)
    if allegato_v_context:
        inail_prompt += f"\n\nCONTESTO ALLEGATO V (macchina ante-1996):\n{allegato_v_context}\n{ALLEGATO_V_EXTRA_FIELDS}"

    inail_text = pdf_service.extract_full_text(inail_bytes)
    producer_text = (
        pdf_service.extract_full_text(producer_bytes)
        if producer_pages <= 100
        else pdf_service.extract_safety_relevant_text(producer_bytes, max_pages=50)
    )

    # Analisi in parallelo
    inail_task = _call_ai_with_text(inail_text, inail_prompt, provider)
    producer_task = _call_ai_with_text(producer_text, producer_prompt, provider)
    inail_json, producer_json = await asyncio.gather(inail_task, producer_task, return_exceptions=True)

    # Se una delle due fallisce, degrada gracefully
    if isinstance(inail_json, Exception):
        inail_json = {}
    if isinstance(producer_json, Exception):
        producer_json = {}

    inail_label = "INAIL"
    producer_label = producer_source_label or f"Produttore ({brand})"

    def _tag_items(items: list, fonte: str) -> list:
        """Converte una lista di stringhe in lista di {testo, fonte}."""
        return [{"testo": str(item), "fonte": fonte} for item in items if item]

    def _tag_devices(devices: list, fonte: str) -> list:
        """Aggiunge il campo fonte a ogni dispositivo di sicurezza."""
        result = []
        for d in devices:
            if isinstance(d, dict) and d.get("nome"):
                result.append({**d, "fonte": fonte})
        return result

    # Merge: INAIL fornisce rischi/DPI/residui; produttore fornisce raccomandazioni
    rischi = _tag_items(inail_json.get("rischi_principali") or [], inail_label)
    dpi = _tag_items(inail_json.get("dispositivi_protezione") or [], inail_label)
    racc = _tag_items(
        (producer_json.get("raccomandazioni_produttore") or []) +
        (producer_json.get("verifiche_sicurezza") or []),
        producer_label,
    )
    residui = _tag_items(inail_json.get("rischi_residui") or [], inail_label)

    # Arricchisci con rischi specifici del modello se il produttore ne ha trovati
    rischi_specifici = producer_json.get("rischi_specifici_modello") or []
    if rischi_specifici:
        existing_testi = {item["testo"].lower() for item in rischi}
        for r in rischi_specifici:
            if r.lower() not in existing_testi:
                rischi.append({"testo": str(r), "fonte": producer_label})

    # Dispositivi di sicurezza: produttore prima (più specifico), poi INAIL, deduplicati per nome
    disp_prod = _tag_devices(producer_json.get("dispositivi_sicurezza") or [], producer_label)
    disp_inail = _tag_devices(inail_json.get("dispositivi_sicurezza") or [], inail_label)
    seen_device_names: set[str] = set()
    dispositivi_merged = []
    for d in disp_prod + disp_inail:
        key = d.get("nome", "").lower().strip()
        if key and key not in seen_device_names:
            seen_device_names.add(key)
            dispositivi_merged.append(d)

    # Checklist: merge INAIL + produttore, deduplicata
    checklist_inail = inail_json.get("checklist") or []
    checklist_prod = producer_json.get("checklist") or []
    seen_cl: set[str] = set()
    checklist_merged = []
    for item in checklist_inail + checklist_prod:
        if not isinstance(item, str):
            continue
        key = item.lower().strip()
        if key not in seen_cl:
            seen_cl.add(key)
            checklist_merged.append(item)

    # Nuovi campi ispettivi da fonti distinte
    procedure_emergenza = _tag_items(
        producer_json.get("procedure_emergenza") or [],
        producer_label,
    )
    limiti_operativi = _tag_items(
        producer_json.get("limiti_operativi") or [],
        producer_label,
    )
    pittogrammi_sicurezza = producer_json.get("pittogrammi_sicurezza") or []
    abilitazione_operatore = _nullable_str(inail_json.get("abilitazione_operatore"))
    documenti_da_richiedere = inail_json.get("documenti_da_richiedere") or []
    verifiche_periodiche = _nullable_str(inail_json.get("verifiche_periodiche"))

    # Nota combinata
    notes = []
    if inail_json.get("note"):
        notes.append(f"[INAIL] {inail_json['note']}")
    if producer_json.get("note"):
        notes.append(f"[{brand}] {producer_json['note']}")
    combined_note = " | ".join(notes) if notes else None

    # Se il manuale produttore è di categoria simile (non del brand esatto), avvisa nella nota
    if producer_source_label and "categoria simile" in producer_source_label:
        avviso = (
            f"⚠ Manuale produttore non trovato per {brand} {model}. "
            f"Le raccomandazioni sono tratte da un manuale della stessa categoria ({producer_source_label}). "
            "Verificare con la documentazione originale del costruttore."
        )
        combined_note = f"{avviso} | {combined_note}" if combined_note else avviso

    return SafetyCard(
        brand=brand, model=model,
        rischi_principali=rischi,
        dispositivi_protezione=dpi,
        raccomandazioni_produttore=racc,
        rischi_residui=residui,
        dispositivi_sicurezza=dispositivi_merged,
        checklist=checklist_merged,
        # Nuovi campi ispettivi
        procedure_emergenza=procedure_emergenza,
        limiti_operativi=limiti_operativi,
        pittogrammi_sicurezza=pittogrammi_sicurezza,
        abilitazione_operatore=abilitazione_operatore,
        documenti_da_richiedere=documenti_da_richiedere,
        verifiche_periodiche=verifiche_periodiche,
        fonte_manuale=producer_url,
        fonte_inail=inail_url,
        fonte_tipo="inail+produttore" if "categoria" not in producer_label else "inail+categoria",
        note=combined_note,
        fonte_rischi=inail_label if inail_json.get("rischi_principali") else producer_label,
        fonte_protezione=inail_label if inail_json.get("dispositivi_protezione") else "AI",
        fonte_raccomandazioni=producer_label if producer_json.get("raccomandazioni_produttore") else "AI",
        fonte_residui=inail_label if inail_json.get("rischi_residui") else "AI",
        gap_ce_ante=inail_json.get("gap_ce_ante"),
        bozze_prescrizioni=inail_json.get("bozze_prescrizioni") or [],
    )


async def _analyze_pdf_direct(
    brand: str, model: str, pdf_bytes: bytes, pdf_url: Optional[str], provider: str,
    allegato_v_context: Optional[str] = None,
) -> SafetyCard:
    """Analisi diretta del PDF (≤100 pagine) — inviato come documento nativo."""
    pdf_b64 = pdf_service.pdf_to_base64(pdf_bytes)
    prompt = _build_analysis_prompt(brand, model)
    if allegato_v_context:
        prompt += f"\n\nCONTESTO ALLEGATO V (macchina ante-1996):\n{allegato_v_context}\n{ALLEGATO_V_EXTRA_FIELDS}"

    # Rileva lingua dal testo estratto e rafforza istruzione traduzione
    text = pdf_service.extract_full_text(pdf_bytes)
    lang = _detect_language(text)
    prompt += _translation_note(lang)

    if provider == "anthropic":
        result_json = await _call_claude_with_pdf(pdf_b64, prompt)
    else:
        result_json = await _call_ai_with_text(text, prompt, provider)

    card = _build_safety_card(brand, model, result_json, pdf_url, "pdf")
    card.gap_ce_ante = result_json.get("gap_ce_ante")
    card.bozze_prescrizioni = result_json.get("bozze_prescrizioni") or []
    return card


async def _analyze_pdf_map_reduce(
    brand: str, model: str, pdf_bytes: bytes, pdf_url: Optional[str], provider: str
) -> SafetyCard:
    """Analisi map-reduce per PDF grandi (>100 pagine)."""
    text = pdf_service.extract_safety_relevant_text(pdf_bytes, max_pages=50)
    chunks = pdf_service.chunk_text(text, max_chars=80000)
    prompt = _build_analysis_prompt(brand, model)

    # MAP: analizza ogni chunk
    partial = []
    for chunk in chunks[:5]:  # Max 5 chunk per contenere i costi
        try:
            partial_json = await _call_ai_with_text(chunk, prompt, provider)
            partial.append(json.dumps(partial_json, ensure_ascii=False))
        except Exception:
            continue

    if not partial:
        return await _generate_fallback(brand, model, provider)

    if len(partial) == 1:
        return _build_safety_card(brand, model, json.loads(partial[0]), pdf_url, "pdf")

    # REDUCE: sintetizza i risultati parziali
    reduce_prompt = REDUCE_PROMPT.format(
        n=len(partial),
        partial_analyses="\n\n---\n\n".join(partial),
    )
    result_json = await _call_ai_with_text("", reduce_prompt, provider, is_reduce=True)
    return _build_safety_card(brand, model, result_json, pdf_url, "pdf")


async def _generate_fallback(
    brand: str, model: str, provider: str,
    norme: list = [],
    allegato_v_context: Optional[str] = None,
) -> SafetyCard:
    """Genera scheda di sicurezza dalla conoscenza AI senza manuale."""
    norme_context = ""
    if norme:
        norme_str = ", ".join(norme)
        norme_context = (
            f"\n\nNORME ARMONIZZATE RILEVATE SULLA TARGA: {norme_str}\n"
            "Usa queste norme per identificare i requisiti minimi di sicurezza applicabili a questa macchina. "
            "Includile nelle raccomandazioni dove pertinente."
        )
    av_context = ""
    if allegato_v_context:
        av_context = f"\n\nCONTESTO ALLEGATO V (macchina ante-1996):\n{allegato_v_context}\n{ALLEGATO_V_EXTRA_FIELDS}"
    # Sanitizza brand/model da caratteri che rompono .format() (es. '{', '}' da OCR errato)
    safe_brand = brand.replace("{", "{{").replace("}", "}}")
    safe_model = model.replace("{", "{{").replace("}", "}}")
    prompt = FALLBACK_PROMPT_TEMPLATE.format(brand=safe_brand, model=safe_model) + norme_context + av_context
    result_json = await _call_ai_with_text("", prompt, provider, is_fallback=True)
    card = _build_safety_card(brand, model, result_json, None, "fallback_ai")
    card.gap_ce_ante = result_json.get("gap_ce_ante")
    card.bozze_prescrizioni = result_json.get("bozze_prescrizioni") or []
    return card


async def _call_claude_with_pdf(pdf_b64: str, prompt: str) -> dict:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_b64,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    )
    return _parse_json_response(response.content[0].text)


async def _call_ai_with_text(
    text: str, prompt: str, provider: str,
    is_fallback: bool = False, is_reduce: bool = False
) -> dict:
    # Rileva lingua e rafforza istruzione traduzione se non italiano
    if text and not is_fallback and not is_reduce:
        lang = _detect_language(text)
        prompt = prompt + _translation_note(lang)
    full_prompt = prompt if (is_fallback or is_reduce) else f"{prompt}\n\nTESTO DEL MANUALE:\n{text}"

    if provider == "anthropic":
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": full_prompt}],
        )
        return _parse_json_response(response.content[0].text)

    elif provider == "gemini":
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=settings.gemini_api_key)
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=full_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=8192,
            ),
        )
        return _parse_json_response(response.text)

    else:
        # Nessun provider disponibile
        raise RuntimeError("Nessun provider AI configurato per l'analisi")


def _parse_json_response(text: str) -> dict:
    """Estrae il JSON dalla risposta AI, robusto ai markdown code block."""
    import logging
    logger = logging.getLogger(__name__)

    # Strategia 1: estrai il blocco JSON tra prima { e ultima }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError as e:
            logger.error("JSON parse error (strategia 1): %s | pos=%d | excerpt=%r",
                         e, e.pos, text[max(0, start + e.pos - 40): start + e.pos + 40])

    # Strategia 2: strip manuale dei markdown fences
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        pass

    # Strategia 3: recupero parziale — costruisce dict dai campi trovati
    result: dict = {}
    list_fields = [
        "rischi_principali", "dispositivi_protezione", "raccomandazioni_produttore", "rischi_residui",
        "checklist", "bozze_prescrizioni", "dispositivi_sicurezza",
        "documenti_da_richiedere", "limiti_operativi", "procedure_emergenza", "pittogrammi_sicurezza",
    ]
    for field in list_fields:
        m = re.search(rf'"{field}"\s*:\s*(\[[^\]]*\])', text, re.DOTALL)
        if m:
            try:
                result[field] = json.loads(m.group(1))
            except Exception:
                pass
    # Campi stringa singola
    for str_field in ["gap_ce_ante", "abilitazione_operatore", "verifiche_periodiche", "confidence_ai"]:
        m_str = re.search(rf'"{str_field}"\s*:\s*"([^"]+)"', text)
        if m_str:
            result[str_field] = _nullable_str(m_str.group(1))
    if result:
        result.setdefault("rischi_principali", [])
        result.setdefault("dispositivi_protezione", [])
        result.setdefault("raccomandazioni_produttore", [])
        result.setdefault("rischi_residui", [])
        result["note"] = "Alcuni campi potrebbero essere incompleti (recupero parziale)."
        return result

    # Fallback finale
    return {
        "rischi_principali": ["Risposta AI non analizzabile — riprovare."],
        "dispositivi_protezione": [],
        "raccomandazioni_produttore": [],
        "rischi_residui": [],
        "note": f"Errore parsing. Risposta raw: {text[:300]}",
    }


_NULL_STR_VALUES = {"null", "none", "n/a", "non previsto", "non applicabile"}

def _nullable_str(value) -> Optional[str]:
    """Restituisce None se il valore è una stringa null-like (es. 'Null', 'None', 'N/A')."""
    if value is None:
        return None
    s = str(value).strip()
    return None if s.lower() in _NULL_STR_VALUES else s


def _build_safety_card(
    brand: str, model: str, data: dict,
    fonte_url: Optional[str], fonte_tipo: str
) -> SafetyCard:
    # Etichetta fonte unica per tutte le sezioni (singola fonte)
    if fonte_tipo == "fallback_ai":
        label = "AI"
    elif fonte_tipo == "inail":
        label = "INAIL"
    else:
        label = f"Produttore ({brand})"

    def _tag(items: list) -> list:
        """Converte stringhe in {testo, fonte}; se già dict mantiene e aggiunge fonte se mancante."""
        result = []
        for item in items:
            if isinstance(item, dict):
                result.append(item if "fonte" in item else {**item, "fonte": label})
            elif item:
                result.append({"testo": str(item), "fonte": label})
        return result

    def _tag_devices(devices: list) -> list:
        result = []
        for d in devices:
            if isinstance(d, dict) and d.get("nome"):
                result.append(d if "fonte" in d else {**d, "fonte": label})
        return result

    return SafetyCard(
        brand=brand,
        model=model,
        rischi_principali=_tag(data.get("rischi_principali", [])),
        dispositivi_protezione=_tag(data.get("dispositivi_protezione", [])),
        raccomandazioni_produttore=_tag(data.get("raccomandazioni_produttore", [])),
        rischi_residui=_tag(data.get("rischi_residui", [])),
        dispositivi_sicurezza=_tag_devices(data.get("dispositivi_sicurezza", [])),
        checklist=data.get("checklist", []),
        # Nuovi campi ispettivi
        procedure_emergenza=_tag(data.get("procedure_emergenza") or []),
        limiti_operativi=_tag(data.get("limiti_operativi") or []),
        pittogrammi_sicurezza=data.get("pittogrammi_sicurezza") or [],
        abilitazione_operatore=_nullable_str(data.get("abilitazione_operatore")),
        documenti_da_richiedere=data.get("documenti_da_richiedere") or [],
        verifiche_periodiche=_nullable_str(data.get("verifiche_periodiche")),
        confidence_ai=data.get("confidence_ai"),
        fonte_manuale=fonte_url,
        fonte_tipo=fonte_tipo,
        note=data.get("note"),
        fonte_rischi=label,
        fonte_protezione=label,
        fonte_raccomandazioni=label,
        fonte_residui=label,
    )
