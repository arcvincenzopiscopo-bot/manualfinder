"""
Generazione della scheda di sicurezza dal manuale del macchinario.
Usa Claude (L1) o Gemini (L2) per analizzare PDF e produrre JSON strutturato.
Strategia dual-source: INAIL (normativa) + produttore (raccomandazioni specifiche).

Layer RAG: il contesto normativo (D.Lgs 81/08 dizionario + Direttiva Macchine/INAIL ChromaDB)
viene anteposto al prompt come blocco aggiuntivo. Il flusso di analisi PDF rimane invariato.
"""
import json
import re
import logging
from typing import Optional
from app.config import settings
from app.models.responses import SafetyCard
from app.services import pdf_service
from app.data.allegato_v_data import get_machine_category, format_requisiti_for_prompt

logger = logging.getLogger(__name__)

# ─── RAG / Normative context ──────────────────────────────────────────────────
# Import lazy — evita crash se chromadb/sentence-transformers non installati su Render.
# Il sistema degrada silenziosamente al solo dizionario D.Lgs se RAG non disponibile.

def _get_normative_context(machine_type: Optional[str]) -> str:
    """
    Recupera il contesto normativo completo per il prompt.
    Fallback gerarchico: dizionario D.Lgs → RAG ChromaDB → stringa vuota.
    Mai solleva eccezioni — l'analisi del PDF procede comunque.
    """
    if not machine_type:
        return ""
    try:
        from app.services.hybrid_retriever import get_full_normative_context
        return get_full_normative_context(machine_type)
    except Exception as e:
        logger.debug("Normative context non disponibile: %s", e)
        return ""


def _log_rag_metadata(machine_type: Optional[str], fonte_tipo: str) -> None:
    """Log strutturato sulle fonti normative usate per questa Safety Card."""
    if not machine_type:
        return
    try:
        from app.services.hybrid_retriever import get_normative_metadata
        meta = get_normative_metadata(machine_type)
        logger.info(
            "rag_context machine_type=%s fonte_tipo=%s dlgs_refs=%d rag_available=%s rag_chunks=%d",
            machine_type,
            fonte_tipo,
            meta.get("dlgs_refs", 0),
            meta.get("rag_available", False),
            meta.get("rag_chunks", 0),
        )
    except Exception:
        pass


def _enrich_card_sources(card, machine_type: Optional[str]) -> None:
    """Popola i campi fonte_* della card solo se vuoti."""
    if not machine_type:
        return
    try:
        from app.services.hybrid_retriever import enrich_card_with_sources
        enrich_card_with_sources(card.__dict__, machine_type)
        # Riapplica i valori aggiornati al modello Pydantic
        for field in ["fonte_rischi", "fonte_protezione", "fonte_raccomandazioni", "fonte_residui"]:
            if field in card.__dict__ and not getattr(card, field, None):
                setattr(card, field, card.__dict__.get(field))
    except Exception:
        pass


SYSTEM_PROMPT = """Sei un esperto di sicurezza sul lavoro specializzato nell'analisi di manuali tecnici di macchinari di ogni settore produttivo (edilizia, industria, logistica, agricoltura, sollevamento e altri), con profonda conoscenza di:
- D.Lgs. 81/2008 (Testo Unico sulla Sicurezza sul Lavoro) e relativi Allegati
- Direttive Macchine 89/392/CEE, 98/37/CE e 2006/42/CE
- Accordi Stato-Regioni (es. 22/02/2012 per abilitazioni operatori)
- Norme armonizzate EN, UNI EN, ISO applicabili ai macchinari

Il tuo compito è analizzare la documentazione fornita (manuali ufficiali, schede INAIL, normative) e produrre una scheda di sicurezza strutturata che un ISPETTORE DEL LAVORO possa utilizzare DIRETTAMENTE durante un accesso ispettivo in qualsiasi luogo di lavoro italiano (cantiere edile, stabilimento industriale, azienda agricola, hub logistico, ecc.).

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


def _workplace_prompt_hints(workplace_context: Optional[dict]) -> str:
    """
    Genera vincoli aggiuntivi contestuali da iniettare nei prompt AI.
    Fornisce esempi DPI e rischi tipici per il settore ispettivo selezionato,
    così l'AI non si limita ai soli esempi da cantiere edile.
    """
    if not workplace_context or not isinstance(workplace_context, dict):
        return ""

    category = workplace_context.get("category", "")

    _labels = {
        "cantiere":    "Cantiere edile",
        "industria":   "Stabilimento industriale",
        "logistica":   "Hub logistico / magazzino",
        "agricoltura": "Azienda agricola",
        "sollevamento": "Operazioni di sollevamento",
        "altro":       "Luogo di lavoro generico",
    }

    _dpi = {
        "cantiere": (
            'elmetto EN 397 → "operatore"; '
            'imbracatura anticaduta EN 361 cat. C → "operatore" (lavori in quota); '
            'gilet alta visibilità EN ISO 20471 → "personale_a_terra"; '
            'scarpe antinfortunistiche EN ISO 20345 → "entrambi"; '
            'guanti EN 388 → "operatore"; '
            'maschera antipolvere FFP2 → "operatore" (polveri/diesel)'
        ),
        "industria": (
            'cuffie antirumore EN 352 → "operatore" (rumore >85 dB); '
            'occhiali EN 166 → "operatore" (proiezioni materiale/fluidi); '
            'scarpe antinfortunistiche EN ISO 20345 → "entrambi"; '
            'guanti EN 388 → "operatore"; '
            'tuta EN ISO 13688 → "operatore"; '
            'ripari fissi/mobili organi in moto → protezione collettiva, recipient "entrambi"'
        ),
        "logistica": (
            'gilet alta visibilità EN ISO 20471 → "entrambi"; '
            'scarpe antinfortunistiche EN ISO 20345 → "entrambi"; '
            'guanti anti-taglio EN 388 → "operatore"; '
            'elmetto EN 397 → "operatore" (rischio caduta materiale); '
            'segnaletica pavimento corsie pedoni/mezzi → protezione collettiva, recipient "entrambi"'
        ),
        "agricoltura": (
            'casco EN 397 → "operatore"; '
            'stivali antinfortunistici EN ISO 20345 → "operatore"; '
            'guanti EN 388 → "operatore"; '
            'maschera FFP2/FFP3 → "operatore" (polveri, fitosanitari); '
            'occhiali EN 166 → "operatore" (trattamenti fitosanitari); '
            'carter protezione PTO → protezione collettiva, recipient "entrambi"'
        ),
        "sollevamento": (
            'elmetto EN 397 → "entrambi" (zona influenza carico); '
            'imbracatura anticaduta EN 361 → "operatore" (accesso in quota sull\'apparecchio); '
            'guanti EN 388 → "operatore"; '
            'scarpe antinfortunistiche EN ISO 20345 → "entrambi"; '
            'gilet alta visibilità EN ISO 20471 → "personale_a_terra"; '
            'delimitazione zona influenza carico → protezione collettiva, recipient "entrambi"'
        ),
    }

    _risks = {
        "cantiere":    "caduta dall'alto, investimento da mezzi, seppellimento/cedimento terreno, ribaltamento, elettrocuzione da linee aeree/interrate",
        "industria":   "rumore occupazionale, vibrazioni mano-braccio/corpo intero, schiacciamento da organi in moto, proiezione materiali/utensili, contatto con sostanze chimiche, tagli",
        "logistica":   "investimento da carrelli elevatori, caduta materiale da scaffalature, ribaltamento del carrello, movimentazione manuale carichi, urti in spazi ristretti",
        "agricoltura": "ribaltamento su terreno accidentato/in pendenza, presa/trascinamento da PTO, schiacciamento tra trattore e attrezzo trainato, esposizione a fitosanitari, caduta dalla macchina",
        "sollevamento": "caduta del carico, cedimento strutturale dell'apparecchio, urto del carico su persone, ribaltamento per instabilità del piano d'appoggio, contatto con linee elettriche aeree",
    }

    label = _labels.get(category, category)
    dpi = _dpi.get(category, "")
    risks = _risks.get(category, "")

    lines = [f"\n- CONTESTO SETTORE: Il sopralluogo avviene in '{label}'."]
    if dpi:
        lines.append(f"  Adatta i DPI a questo settore. Esempi tipici: {dpi}.")
    if risks:
        lines.append(f"  Enfatizza i rischi caratteristici del settore: {risks}.")
    return "\n".join(lines)


def _build_inail_prompt(machine_rules: Optional[dict] = None,
                        workplace_context: Optional[dict] = None) -> str:
    """
    Prompt per analisi scheda INAIL: estrae rischi normativi, DPI, dispositivi di sicurezza,
    abilitazioni operatore, documenti da richiedere, verifiche periodiche, checklist sopralluogo.
    Se machine_rules è fornito, aggiunge contesto specifico per tipo macchina da Supabase.
    """
    base = """Analizza questa scheda INAIL o documento normativo ed estrai le informazioni di sicurezza nel seguente formato JSON:

{
  "rischi_principali": [
    {
      "testo": "[ALTA/MEDIA/BASSA] descrizione rischio specifico per questa categoria di macchina [Art. XX D.Lgs. 81/08 o norma applicabile]",
      "probabilita": "P1 | P2 | P3",
      "gravita": "S1 | S2 | S3"
    }
  ],
  "dispositivi_protezione": [
    {
      "testo": "DPI o protezione collettiva richiesta dalla normativa (es. 'Elmetto EN 397', 'Imbracatura anticaduta EN 361 cat. C', 'Parapetto perimetrale h≥1m')",
      "recipient": "operatore | personale_a_terra | entrambi"
    }
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
  "abilitazione_operatore": "Formazione e/o patentino obbligatorio per l'operatore secondo normativa italiana VIGENTE. Cita la norma più aggiornata in vigore (es. Accordo Stato-Regioni nella versione attuale, non necessariamente quella del 22/02/2012 se aggiornata). Indica: tipo corso, durata minima, soggetti formatori. Null se non previsto per questa categoria.",
  "documenti_da_richiedere": [
    {
      "documento": "Nome documento con riferimento normativo che ne impone la tenuta (es. 'Dichiarazione di conformità CE [Dir. 2006/42/CE Art. 7]', 'Registro verifiche periodiche [Art. 71 c.11 D.Lgs. 81/08]')",
      "smart_hint": "Suggerimento pratico per l'ispettore: cosa verificare specificamente su questo documento (es. 'Controllare che la lingua sia l'italiano e che il numero di serie coincida con l'etichetta')",
      "validity_requirements": "Elementi obbligatori che il documento deve contenere per essere valido ai sensi della norma (es. firma del datore di lavoro, timbro, data aggiornamento, numero seriale macchina coincidente con targa, lingua italiana)",
      "irregularity_indicators": "Segnali che indicano non conformità o documento non aggiornato che l'ispettore deve riconoscere (es. data antecedente a 3 anni, firma mancante, numero di serie non coincidente, documento in lingua straniera senza traduzione certificata)"
    }
  ],
  "verifiche_periodiche": "Obblighi di verifica periodica. Se applicabile: 1) categoria di appartenenza secondo Allegato VII D.Lgs. 81/08 e D.M. 11 aprile 2011 con testo esteso completo come riportato nella norma; 2) cadenza; 3) soggetto abilitato; 4) riferimento normativo VIGENTE aggiornato. Null se non previsti per questa categoria.",
  "checklist": [
    {
      "testo": "Verifica [componente/elemento specifico] — [dove trovarlo fisicamente sulla macchina] — [criterio di conformità] [Art. X D.Lgs. 81/08 o Allegato Y punto Z]",
      "livello": 1,
      "norma": "All. V D.Lgs. 81/08 punto X.X",
      "prescrizione_precompilata": "Si rileva [il problema specifico]. In violazione di [norma]. Si prescrive [azione correttiva] [entro termine se livello=2]."
    }
  ],
  "note": "requisiti normativi aggiuntivi, riferimenti specifici D.Lgs. 81/08, norme armonizzate applicabili, registri obbligatori"
}

VINCOLI:
- rischi_principali: 3-8 rischi come oggetti JSON con campi "testo", "probabilita", "gravita". ORDINATI da gravità S3→S1, a parità P3→P1. Il campo "testo" deve contenere [ALTA/MEDIA/BASSA] e riferimento normativo. Classificazione ISO 12100: probabilita = P1 (raro), P2 (possibile), P3 (probabile); gravita = S1 (lieve reversibile), S2 (grave/invalidante), S3 (morte/invalidante permanente).
- dispositivi_protezione: 3-8 oggetti {testo, recipient}. Il campo "recipient" indica a chi si applica: "operatore" (chi conduce/opera la macchina), "personale_a_terra" (chi lavora nell'area di influenza della macchina), "entrambi" (richiesto a tutti). SEMPRE specificare il campo recipient.{workplace_hints}
- dispositivi_sicurezza: 2-5 dispositivi di sicurezza richiesti dalla normativa per questa categoria di macchina.
- checklist: 4-6 oggetti {testo, livello, norma, prescrizione_precompilata}. livello=1 (STOP immediato: ripari fissi/mobili, pulsanti emergenza, freni, ROPS/FOPS); livello=2 (PRESCRIZIONE: segnalatori, illuminazione, targhette, estintori). Ordina L1 prima. Ogni testo risponde a: COSA verificare, DOVE trovarlo, COME valutare la conformità. Il campo "norma" è opzionale ma aggiungilo se disponibile. REGOLA prescrizione_precompilata: testo stile verbale ispettivo pronto per copia, usa SOLO la norma già in campo "norma", lascia "" se incerto.
- documenti_da_richiedere: 3-6 oggetti {documento, smart_hint, validity_requirements, irregularity_indicators} con il riferimento normativo nel campo "documento". ESSENZIALE per l'attività ispettiva. Lo smart_hint deve essere pratico e specifico. I campi validity_requirements e irregularity_indicators devono essere concreti e specifici per quel documento.
- abilitazione_operatore: se prevista da normativa vigente (Accordo Stato-Regioni nella versione più aggiornata in vigore, o norma settoriale specifica), descrivila in dettaglio (tipo corso, durata minima, ente formatore). Cita sempre la versione normativa attualmente in vigore, non necessariamente quella del 22/02/2012 se aggiornata.
- FEDELTÀ ALLA FONTE: Estrai SOLO ciò che è scritto in questo documento. Non integrare con conoscenze generali.
- Usa terminologia precisa del D.Lgs. 81/2008.
- CITAZIONI OBBLIGATORIE: per ogni voce estratta dal documento includi OBBLIGATORIAMENTE il riferimento alla sezione o pagina in formato [pag. X] o [Sez. X.X] DENTRO il campo "testo". Se non trovi il riferimento esatto, ometti la voce piuttosto che inventare un numero.
- Rispondi SOLO con il JSON valido."""
    base = base.replace("{workplace_hints}", _workplace_prompt_hints(workplace_context))
    return _append_machine_rules(base, machine_rules)


def _append_machine_rules(prompt: str, machine_rules: Optional[dict]) -> str:
    """Appende le regole specifiche per tipo macchina al prompt, se disponibili."""
    if not machine_rules:
        return prompt
    sections = []
    if machine_rules.get("extra_context"):
        sections.append(f"CONTESTO SPECIFICO TIPO MACCHINA:\n{machine_rules['extra_context']}")
    if machine_rules.get("specific_risks"):
        sections.append(f"RISCHI SPECIFICI DA EVIDENZIARE SEMPRE PER QUESTA CATEGORIA:\n{machine_rules['specific_risks']}")
    if machine_rules.get("normative_refs"):
        sections.append(f"NORMATIVE OBBLIGATORIE DA CITARE PER QUESTA CATEGORIA:\n{machine_rules['normative_refs']}")
    if machine_rules.get("inspection_focus"):
        sections.append(f"FOCUS ISPETTIVO PRIORITARIO PER QUESTA CATEGORIA:\n{machine_rules['inspection_focus']}")
    if sections:
        return prompt + "\n\n" + "\n\n".join(sections)
    return prompt


def _build_producer_prompt(brand: str, model: str, machine_rules: Optional[dict] = None,
                           is_category_match: bool = False) -> str:
    """
    Prompt per analisi manuale produttore: estrae raccomandazioni operative specifiche,
    limiti operativi con valori numerici, procedure di emergenza, pittogrammi, checklist preuso.
    Se machine_rules è fornito, aggiunge contesto specifico per tipo macchina da Supabase.
    Se is_category_match=True il manuale è di un modello simile, non esatto: omette dispositivi
    e limiti specifici del modello del manuale per non attribuirli alla macchina cercata.
    """
    if is_category_match:
        category_warning = (
            f"\n⚠ ATTENZIONE: Questo manuale NON appartiene a {brand} {model} ma a una macchina "
            f"della stessa categoria.\n"
            f"Estrai SOLO informazioni valide per TUTTA la categoria, non specifiche del modello del manuale.\n"
            f"Ometti completamente: dispositivi_sicurezza (specifici del modello del manuale), "
            f"limiti_operativi con valori numerici (si riferiscono al modello del manuale, non a {brand} {model}), "
            f"pittogrammi_sicurezza (posizioni fisiche specifiche di quel modello).\n\n"
        )
    else:
        category_warning = ""

    if is_category_match:
        dispositivi_vincolo = "lascia la lista vuota [] — questo manuale appartiene a un modello diverso"
        limiti_vincolo = f"lascia la lista vuota [] — i valori numerici si riferiscono al modello del manuale, non a {brand} {model}"
        pittogrammi_vincolo = "lascia la lista vuota [] — le posizioni fisiche sono specifiche del modello del manuale"
    else:
        dispositivi_vincolo = f"3-6 dispositivi di sicurezza FISICAMENTE INSTALLATI su {brand} {model} dal costruttore (interblocchi, sensori, ripari fissi/mobili, pulsanti emergenza, limitatori, valvole). Sii specifico sulla posizione fisica."
        limiti_vincolo = "includi SOLO valori ESPLICITAMENTE riportati nel manuale. NON generare valori ipotetici anche se plausibili per la categoria. Se non presenti, lascia la lista vuota []."
        pittogrammi_vincolo = "segnala SOLO i pittogrammi esplicitamente citati nel manuale con la loro posizione sulla macchina."

    # NOTA: stringa NORMALE (non f-string) — i placeholder {brand}, {model}, ecc. vengono
    # sostituiti manualmente via .replace() sotto. Così le graffe JSON non passano per il
    # format engine di Python e non possono rompere il template (bug storico sul JSON literal).
    template = """{category_warning}Analizza il manuale del macchinario {brand} {model} ed estrai le informazioni di sicurezza specifiche del costruttore nel seguente formato JSON:

{
  "raccomandazioni_produttore": [
    "prescrizione OPERATIVA DI SICUREZZA del costruttore {brand} per il modello {model} — SOLO quelle che proteggono l'incolumità di operatori e persone vicine (es. 'Non salire sul tetto cabina senza imbracatura', 'Abbassare il carico prima di scendere dal mezzo'). ESCLUDI istruzioni di manutenzione motore, gestione filtri, sostituzioni componenti, avvisi guasto. [sezione o pag. manuale]"
  ],
  "verifiche_sicurezza": [
    "controllo prescritto dal costruttore prima/durante/dopo l'uso — SOLO verifiche che impattano sulla sicurezza delle persone (es. freni, luci, sistemi ROPS/FOPS, stabilizzatori). ESCLUDI controlli olio, filtri, livelli fluidi, DPF, preriscaldamento motore. Specifica QUANDO e CON QUALE FREQUENZA [rif. sezione manuale]"
  ],
  "rischi_specifici_modello": [
    "rischio di INFORTUNIO specifico di questo modello {model} non coperto dalla normativa generale — con spiegazione tecnica. ESCLUDI rischi di guasto meccanico o danneggiamento della macchina senza conseguenze per persone."
  ],
  "dispositivi_sicurezza": [
    {
      "nome": "Nome esatto del dispositivo come indicato nel manuale {brand} {model} (es. 'Sensore pressione circuito frenante', 'Limitatore di carico elettronico')",
      "tipo": "interblocco | sensore | riparo | arresto_emergenza | segnalazione | limitatore",
      "descrizione": "Funzione del dispositivo e POSIZIONE FISICA sulla macchina {model} (es. 'Posizionato sul circuito frenante posteriore, accessibile dal vano motore lato destro')",
      "verifica_ispezione": "Verifica/Controlla/Accertati [dove trovarlo fisicamente su questa macchina] — [come verificare che funzioni] [sezione manuale di riferimento]"
    }
  ],
  "limiti_operativi": [
    "limite con VALORE NUMERICO e unità di misura come indicato nel manuale (es. 'Portata massima: 3.500 kg [Sez. 2.4]', 'Pendenza massima operativa: 30% [pag. 18]', 'Pressione idraulica max: 350 bar [Sez. 5.1]')"
  ],
  "procedure_emergenza": [
    {
      "testo": "Procedura di emergenza PER SALVAGUARDARE PERSONE specifica per {brand} {model}: Passo 1 — [azione]. Passo 2 — [azione]. Passo 3 — [azione]. [Sez. manuale]. INCLUDI SOLO: incendio, ribaltamento, cedimento freni/idraulico, investimento persone, folgorazione, seppellimento. ESCLUDI: rigenerazione DPF, surriscaldamento motore, avarie meccaniche senza rischio immediato per persone, istruzioni per chiamare l'officina.",
      "source_tier": "manuale"
    }
  ],
  "pittogrammi_sicurezza": [
    "pittogramma o avvertenza obbligatoria che deve essere presente e leggibile sulla macchina — specifica posizione (es. 'Pittogramma PERICOLO SCHIACCIAMENTO — pannello laterale sinistro cabina [pag. 12 manuale]')"
  ],
  "checklist": [
    {
      "testo": "Verifica [componente fisico specifico di {brand} {model}] — [dove trovarlo sulla macchina] — [criterio di conformità] [Sez. X.X o pag. YY manuale]",
      "livello": 1,
      "norma": "Sez. X.X manuale",
      "prescrizione_precompilata": "Si rileva [il problema specifico su {brand} {model}]. In violazione di [norma]. Si prescrive [azione correttiva] [entro termine se livello=2]."
    }
  ],
  "note": "avvertenze particolari del costruttore, condizioni d'uso, limitazioni ambientali o operative"
}

VINCOLI:
- raccomandazioni_produttore: 2-6 elementi SPECIFICI per {brand} {model} che riguardano esclusivamente la SICUREZZA DELLE PERSONE. NON includere: manutenzione motore/filtri/fluidi, gestione DPF, preriscaldamento, istruzioni per officina, avvisi di degradazione prestazioni. Ogni voce: sezione o pagina del manuale tra parentesi quadre.
- dispositivi_sicurezza: {dispositivi_vincolo}.
- limiti_operativi: {limiti_vincolo}.
- procedure_emergenza: 2-5 oggetti {testo, source_tier} SOLO per emergenze che mettono a rischio PERSONE (incendio, ribaltamento, cedimento freni, investimento, folgorazione). Il campo source_tier deve essere sempre "manuale". NON includere: rigenerazione DPF, surriscaldamento motore, avarie meccaniche senza rischio per persone, call to service. Se il manuale descrive solo procedure di manutenzione, lascia la lista vuota [].
- pittogrammi_sicurezza: {pittogrammi_vincolo}.
- checklist: 5-8 oggetti {testo, livello, norma, prescrizione_precompilata} SPECIFICI per {brand} {model}. livello=1 (STOP: ripari, emergenza, freni, ROPS); livello=2 (PRESCRIZIONE: segnalatori, pittogrammi, luci). Ogni testo: verbo imperativo + cosa + dove + criterio di conformità + riferimento sezione/pagina manuale. REGOLA prescrizione_precompilata: testo stile verbale ispettivo pronto per copia, usa SOLO la norma già in campo "norma", lascia "" se incerto.
- FEDELTÀ ALLA FONTE: Estrai SOLO ciò che è scritto in questo manuale. Per elementi non presenti, lascia la lista vuota — NON integrare con conoscenze generali sul tipo di macchina.
- CITAZIONI OBBLIGATORIE: ogni voce deve contenere il riferimento alla pagina o sezione del manuale in formato [pag. X] o [Sez. X.X] DENTRO il campo "testo". Se non trovi il riferimento esatto, ometti la voce piuttosto che inventare un numero di pagina.
- Se il manuale è in altra lingua: TRADUCI tutto in italiano. Non lasciare termini stranieri.
- Rispondi SOLO con il JSON valido."""

    base = (template
            .replace("{category_warning}", category_warning)
            .replace("{brand}", brand)
            .replace("{model}", model)
            .replace("{dispositivi_vincolo}", dispositivi_vincolo)
            .replace("{limiti_vincolo}", limiti_vincolo)
            .replace("{pittogrammi_vincolo}", pittogrammi_vincolo))
    return _append_machine_rules(base, machine_rules)


def _build_analysis_prompt(brand: str, model: str, is_category_match: bool = False,
                           workplace_context: Optional[dict] = None) -> str:
    """Prompt generico per analisi singola fonte — combina aspetti normativi e raccomandazioni costruttore."""
    if is_category_match:
        category_warning = (
            f"\n⚠ ATTENZIONE: Questo documento NON appartiene a {brand} {model} ma a una macchina "
            f"della stessa categoria.\n"
            f"Estrai SOLO informazioni valide per TUTTA la categoria.\n"
            f"Ometti completamente: dispositivi_sicurezza e limiti_operativi con valori numerici "
            f"(specifici del modello del documento, non di {brand} {model}).\n\n"
        )
        dispositivi_vincolo = "lascia la lista vuota [] — questo documento appartiene a un modello diverso"
        limiti_vincolo = f"lascia la lista vuota [] — i valori numerici si riferiscono al modello del documento, non a {brand} {model}"
    else:
        category_warning = ""
        dispositivi_vincolo = "3-6 dispositivi di sicurezza FISICAMENTE INSTALLATI sulla macchina dal costruttore (interblocchi, sensori, ripari, pulsanti emergenza, limitatori, valvole di sicurezza). Sii specifico sulla posizione fisica."
        limiti_vincolo = "includi SOLO valori ESPLICITAMENTE presenti nel documento — NON generare valori ipotetici."

    # Stringa NORMALE: placeholder sostituiti via .replace() per evitare che le graffe JSON
    # passino per il format engine di Python (vedi nota in _build_producer_prompt).
    template = """{category_warning}Analizza questo documento relativo al macchinario {brand} {model} ed estrai le informazioni di sicurezza nel seguente formato JSON:

{
  "rischi_principali": [
    {
      "testo": "[ALTA/MEDIA/BASSA] rischio di INFORTUNIO O DANNO ALLA SALUTE specifico per {brand} {model} [riferimento normativo o sezione documento]. INCLUDI SOLO rischi che minacciano l'incolumità di persone.",
      "probabilita": "P1 | P2 | P3",
      "gravita": "S1 | S2 | S3"
    }
  ],
  "dispositivi_protezione": [
    "DPI (cosa indossa l'operatore) OPPURE protezione collettiva — specifica e concreta per questo macchinario"
  ],
  "raccomandazioni_produttore": [
    "prescrizione OPERATIVA DI SICUREZZA del costruttore {brand} per {model} che protegge l'incolumità delle persone [sezione documento]. ESCLUDI istruzioni di manutenzione, gestione guasti, sostituzione componenti, contatto officina."
  ],
  "rischi_residui": [
    "rischio che persiste anche con tutte le protezioni attive — spiega PERCHÉ non eliminabile"
  ],
  "dispositivi_sicurezza": [
    {
      "nome": "Nome esatto del dispositivo installato su {brand} {model} (es. 'Pulsante di emergenza a fungo rosso')",
      "tipo": "interblocco | sensore | riparo | arresto_emergenza | segnalazione | limitatore",
      "descrizione": "Funzione del dispositivo e posizione fisica sulla macchina",
      "verifica_ispezione": "Verifica/Controlla/Accertati [dove trovarlo fisicamente] — [come verificare il funzionamento] [rif. sezione documento]"
    }
  ],
  "abilitazione_operatore": "Formazione obbligatoria richiesta dalla normativa italiana VIGENTE per questo tipo di macchina (cita la versione aggiornata dell'Accordo Stato-Regioni in vigore, o normativa settoriale specifica). Null se non obbligatoria.",
  "documenti_da_richiedere": [
    {
      "documento": "Nome documento [riferimento normativo che ne impone la tenuta]",
      "smart_hint": "Cosa verificare specificamente su questo documento durante l'ispezione"
    }
  ],
  "verifiche_periodiche": "Obblighi di verifica periodica. Se applicabile: 1) categoria di appartenenza secondo Allegato VII D.Lgs. 81/08 e D.M. 11 aprile 2011 con testo esteso completo come riportato nella norma; 2) cadenza; 3) soggetto abilitato; 4) riferimento normativo VIGENTE aggiornato. Null se non previsti.",
  "limiti_operativi": [
    "limite con VALORE NUMERICO e unità di misura esplicitamente riportato nel documento (es. 'Portata massima: 3.500 kg')"
  ],
  "procedure_emergenza": [
    "Procedura di emergenza PER SALVAGUARDARE PERSONE: Passo 1 — [azione]. Passo 2 — [azione]. [rif. sezione documento]. INCLUDI SOLO: incendio, ribaltamento, cedimento freni o idraulico, investimento persone, folgorazione, seppellimento, sversamento sostanze pericolose. ESCLUDI: procedure di manutenzione, gestione avarie meccaniche, rigenerazione filtri, istruzioni per officina."
  ],
  "pittogrammi_sicurezza": [
    "pittogramma o avvertenza che deve essere presente e leggibile sulla macchina — con posizione [rif. documento]"
  ],
  "checklist": [
    {
      "testo": "Verifica [elemento concreto fisico] — [dove trovarlo sulla macchina] — [come stabilire se conforme] [rif. normativo o sezione documento]",
      "livello": 1,
      "norma": "All. V D.Lgs. 81/08",
      "prescrizione_precompilata": "Si rileva [il problema specifico]. In violazione di [norma]. Si prescrive [azione correttiva] [entro termine se livello=2]."
    }
  ],
  "attrezzature_intercambiabili": "Se la macchina può montare attrezzature intercambiabili (pinze, bracci, forche, utensili da taglio, benne speciali ecc.), descrivi in 2-3 frasi: quali attrezzature sono compatibili, se richiedono marcatura CE propria, come verificare la compatibilità. Null se la macchina non prevede attrezzature intercambiabili.",
  "note": "osservazioni aggiuntive di sicurezza, limiti d'uso, condizioni ambientali"
}

VINCOLI:
- rischi_principali: 3-8 rischi SOLO per l'incolumità delle persone, ORDINATI da ALTA a BASSA gravità. Includi tag [ALTA/MEDIA/BASSA] e riferimento normativo/documentale. NON includere rischi di guasto meccanico, intasamento filtri, degradazione prestazioni o danni alla sola macchina.
- raccomandazioni_produttore: SOLO raccomandazioni che proteggono persone. NON manutenzione, fluidi, filtri DPF, preriscaldamento, avvisi motore.
- procedure_emergenza: SOLO per emergenze che minacciano persone (incendio, ribaltamento, cedimento freni, investimento, folgorazione). NON rigenerazione DPF, avarie meccaniche, call to service. Lista vuota [] se il documento non ne contiene.
- dispositivi_sicurezza: {dispositivi_vincolo}.
- checklist: 5-10 voci azionabili IMMEDIATAMENTE in sopralluogo. Ogni voce deve rispondere a: COSA verificare, DOVE trovarlo, COME stabilire la conformità. Includi riferimento sezione o articolo normativo tra parentesi quadre. REGOLA prescrizione_precompilata: testo stile verbale ispettivo pronto per copia, usa SOLO la norma già in campo "norma", lascia "" se incerto.
- limiti_operativi: {limiti_vincolo}.
- documenti_da_richiedere: 3-5 documenti essenziali per l'accesso ispettivo con riferimento normativo che ne impone la tenuta.
- FEDELTÀ ALLA FONTE: Estrai SOLO ciò che è scritto nel documento fornito.
- Se il documento è in altra lingua: TRADUCI tutto in italiano. NON lasciare termini stranieri.
- Usa terminologia del D.Lgs. 81/2008 e delle norme armonizzate dove appropriato."""

    base = (template
            .replace("{category_warning}", category_warning)
            .replace("{brand}", brand)
            .replace("{model}", model)
            .replace("{dispositivi_vincolo}", dispositivi_vincolo)
            .replace("{limiti_vincolo}", limiti_vincolo))
    return base + _workplace_prompt_hints(workplace_context) + "\n- Rispondi SOLO con il JSON valido."


FALLBACK_PROMPT_TEMPLATE = """Non è disponibile il manuale ufficiale del macchinario {brand} {model}.

STRATEGIA DI ANALISI (applica nell'ordine, sii ONESTO sulla certezza):
1. Se conosci questo modello esatto ({brand} {model}): usa quella conoscenza diretta → confidence_ai = "high"
2. Se conosci modelli simili della stessa marca (versioni precedenti/adiacenti): basa l'analisi su quelli, indicalo nelle note → confidence_ai = "medium"
3. Se conosci solo la categoria generica: usa D.Lgs. 81/2008 e conoscenza della categoria → confidence_ai = "low"

IMPORTANTE: Sii conservativo. È preferibile una scheda parziale ma affidabile piuttosto che una completa ma con dati inventati. Per i limiti operativi (portate, pressioni) NON generare valori ipotetici — lascia la lista vuota se non sei certo.

Genera una scheda di sicurezza INDICATIVA:

{{
  "rischi_principali": [
    "[ALTA/MEDIA/BASSA] rischio di INFORTUNIO O DANNO ALLA SALUTE specifico per {brand} {model}. SOLO rischi per persone: schiacciamento, ribaltamento, caduta, elettrocuzione, esplosione, rumore/vibrazioni, sostanze nocive, investimento. ESCLUDI guasti meccanici, intasamento filtri, danni al solo motore o ai componenti senza conseguenze per persone. NON citare articoli specifici del D.Lgs. 81/2008: in modalità AI senza documento le citazioni normative non possono essere verificate."
  ],
  "dispositivi_protezione": [
    "DPI o protezione collettiva richiesta per questa categoria di macchina"
  ],
  "raccomandazioni_produttore": [
    "raccomandazione operativa di SICUREZZA PER LE PERSONE basata sulla conoscenza di {brand} {model} o modelli simili. ESCLUDI istruzioni di manutenzione, gestione filtri/fluidi, avarie meccaniche."
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
  "abilitazione_operatore": "Formazione obbligatoria prevista dalla normativa italiana VIGENTE per questa categoria di macchina (cita la versione aggiornata dell'Accordo Stato-Regioni in vigore, o norma settoriale specifica). Null se non prevista.",
  "documenti_da_richiedere": [
    {{
      "documento": "Nome documento con riferimento normativo che ne impone la tenuta",
      "smart_hint": "Cosa verificare specificamente su questo documento (es. lingua italiana, numero di serie, data ultima verifica)"
    }}
  ],
  "verifiche_periodiche": "Obblighi di verifica periodica. Se applicabile: 1) categoria di appartenenza secondo Allegato VII D.Lgs. 81/08 e D.M. 11 aprile 2011 con testo esteso completo come riportato nella norma; 2) cadenza; 3) soggetto abilitato; 4) riferimento normativo VIGENTE aggiornato. Null se non previsti.",
  "limiti_operativi": [],
  "procedure_emergenza": [
    "Procedura di emergenza PER SALVAGUARDARE PERSONE tipica per {{brand}} {{model}}: Passo 1 — [azione]. Passo 2 — [azione]. SOLO: incendio, ribaltamento, cedimento freni, investimento, folgorazione. ESCLUDI avarie meccaniche senza rischio per persone."
  ],
  "pittogrammi_sicurezza": [
    "pittogramma di avvertenza tipicamente presente su questa categoria di macchina"
  ],
  "checklist": [
    {{
      "testo": "Verifica [elemento concreto fisico] — [dove trovarlo] — [come valutare la conformità]",
      "livello": 1,
      "norma": "All. V D.Lgs. 81/08",
      "prescrizione_precompilata": "Si rileva [il problema specifico]. In violazione di [norma]. Si prescrive [azione correttiva] [entro termine se livello=2]."
    }}
  ],
  "attrezzature_intercambiabili": "Se la macchina può montare attrezzature intercambiabili, descrivi in 2-3 frasi quali sono, se richiedono marcatura CE propria, come verificare la compatibilità. Null se non applicabile.",
  "confidence_ai": "high | medium | low",
  "note": "ATTENZIONE: Scheda generata da AI senza consultazione della documentazione ufficiale del costruttore. Non utilizzare come unica fonte di riferimento per prescrizioni ispettive."
}}

VINCOLI:
- rischi_principali: 3-8 rischi ORDINATI da ALTA a BASSA gravità con tag [ALTA/MEDIA/BASSA]. SOLO rischi per l'incolumità delle persone — NON guasti meccanici, filtri, avarie senza conseguenze per persone. NON citare articoli specifici del D.Lgs. 81/2008 (es. Art. 69, Art. 71): in modalità AI senza documento le citazioni non sono verificabili e rischiano di essere errate.
- raccomandazioni_produttore: SOLO raccomandazioni che proteggono persone (operatore, bystander). NON manutenzione, fluidi, DPF, call to service.
- procedure_emergenza: SOLO per emergenze che minacciano persone. Lista vuota [] se non applicabile.
- dispositivi_sicurezza: 2-5 dispositivi tipici per questa categoria — specifica posizione fisica sulla macchina
- checklist: 5-8 oggetti {{testo, livello, norma, prescrizione_precompilata}}. livello=1 (STOP: ripari, emergenza, freni, ROPS); livello=2 (PRESCRIZIONE: segnalatori, luci, targhette). Ogni testo: verbo imperativo + COSA + DOVE + COME. NON aggiungere riferimenti a articoli specifici del D.Lgs. 81/2008. REGOLA prescrizione_precompilata: testo stile verbale ispettivo pronto per copia, usa SOLO la norma già in campo "norma", lascia "" se incerto.
- documenti_da_richiedere: 3-5 oggetti {{documento, smart_hint}} essenziali con riferimento normativo nel campo "documento". Lo smart_hint deve essere concreto e operativo.
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
    "descrizione rischio di INFORTUNIO O DANNO ALLA SALUTE [ALTA/MEDIA/BASSA] — con riferimento normativo. SOLO rischi per persone, NON guasti meccanici o danni alla macchina."
  ],
  "dispositivi_protezione": ["DPI o protezione collettiva richiesta"],
  "raccomandazioni_produttore": ["prescrizione OPERATIVA DI SICUREZZA PER PERSONE del costruttore — ESCLUDI manutenzione, fluidi, DPF, officina."],
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
  "verifiche_periodiche": "Se applicabile: 1) categoria Allegato VII D.Lgs. 81/08 e D.M. 11 aprile 2011 con testo esteso completo; 2) cadenza; 3) soggetto abilitato; 4) normativa VIGENTE aggiornata. Null se non previsto",
  "limiti_operativi": ["limite con valore numerico e unità di misura"],
  "procedure_emergenza": ["Procedura PER SALVAGUARDARE PERSONE: Passo 1 — ... Passo 2 — ... SOLO: incendio, ribaltamento, cedimento freni, investimento, folgorazione. ESCLUDI avarie meccaniche senza rischio per persone."],
  "pittogrammi_sicurezza": ["avvertenza/pittogramma obbligatorio sulla macchina"],
  "checklist": [
    {{
      "testo": "Verifica [elemento fisico] — [dove trovarlo] — [criterio di conformità] [rif. normativo o sezione manuale]",
      "livello": 1,
      "norma": "All. V D.Lgs. 81/08",
      "prescrizione_precompilata": "Si rileva [il problema specifico]. In violazione di [norma]. Si prescrive [azione correttiva] [entro termine se livello=2]."
    }}
  ],
  "documenti_da_richiedere": [
    {{
      "documento": "Nome documento [riferimento normativo]",
      "smart_hint": "Cosa verificare specificamente su questo documento"
    }}
  ],
  "attrezzature_intercambiabili": "Se la macchina può montare attrezzature intercambiabili, descrivi brevemente. Null se non applicabile.",
  "note": "avvertenze residue importanti"
}}

ISTRUZIONI DI CONSOLIDAMENTO:
- rischi_principali: ordina da ALTA a BASSA gravità; deduplica per contenuto semantico. SCARTA qualsiasi rischio di guasto meccanico, intasamento filtri, degradazione prestazioni o danni alla sola macchina senza conseguenze per persone.
- raccomandazioni_produttore: SCARTA istruzioni di manutenzione, gestione fluidi, DPF, preriscaldamento, istruzioni per officina. Mantieni SOLO raccomandazioni che proteggono l'incolumità di operatori e persone vicine.
- procedure_emergenza: SCARTA qualsiasi procedura di manutenzione o gestione avaria meccanica. Mantieni SOLO procedure per incendio, ribaltamento, cedimento freni/idraulico, investimento persone, folgorazione, seppellimento. Se nessuna è pertinente, lascia la lista vuota [].
- dispositivi_sicurezza: deduplica per nome (case-insensitive); mantieni la descrizione più completa tra i duplicati
- checklist: unisci tutte le voci, rimuovi i duplicati semantici, mantieni 5-10 oggetti {testo, livello, norma, prescrizione_precompilata} ordinati per priorità ispettiva (livello=1 STOP prima). REGOLA prescrizione_precompilata: testo stile verbale ispettivo pronto per copia, usa SOLO la norma già in campo "norma", lascia "" se incerto.
- documenti_da_richiedere: unisci e deduplica; mantieni oggetti {documento, smart_hint}
- limiti_operativi: includi SOLO valori esplicitamente presenti nel manuale — non generare valori ipotetici
- Per ogni sezione lista: 3-8 elementi totali, preferendo i più specifici e verificabili
- Rispondi SOLO con il JSON valido."""

LEGAL_ENRICH_PROMPT = """Sei un esperto di normativa italiana sulla sicurezza sul lavoro con conoscenza aggiornata delle norme vigenti.

Tipo di macchina: {machine_label}

Rispondi SOLO con un JSON valido con questi due campi:

{{
  "abilitazione_operatore": "Descrizione completa dell'obbligo di abilitazione/formazione previsto dalla normativa italiana ATTUALMENTE IN VIGORE per questa categoria di macchina. Indica: la norma più aggiornata applicabile (es. Accordo Stato-Regioni nella versione vigente, o norma settoriale specifica), nome esatto del titolo abilitativo, durata minima del corso (ore teoriche + pratiche), soggetti formatori autorizzati, eventuale obbligo di aggiornamento periodico. Se non prevista da nessuna norma vigente, scrivi null.",
  "verifiche_periodiche": "Descrizione completa degli obblighi di verifica periodica. Struttura obbligatoria: 1) Categoria di appartenenza secondo l'Allegato VII D.Lgs. 81/08 e D.M. 11 aprile 2011 con testo esteso completo come riportato nella norma (es. 'Apparecchi di sollevamento materiali con portata superiore a 200 kg, non azionati a mano, di tipo mobile o trasferibile, con modalità di utilizzo regolare'); 2) Cadenza della verifica; 3) Soggetto abilitato (INAIL/ASL/organismo notificato); 4) Riferimento normativo vigente aggiornato. Se la macchina non rientra in nessuna categoria dell'Allegato VII, scrivi null."
}}

ISTRUZIONI:
- Usa SEMPRE la versione più aggiornata della normativa vigente alla data odierna — non fermarti a citare la versione originale di una norma se è stata modificata, integrata o sostituita
- Per le abilitazioni operatore: l'Accordo Stato-Regioni 22/02/2012 è stato aggiornato più volte; verifica se esistono accordi successivi o integrazioni per la categoria in esame e cita quello più recente in vigore
- Per le verifiche periodiche: il D.Lgs. 81/08 Allegato VII è stato aggiornato da decreti successivi; cita il riferimento normativo attuale corretto
- Se la norma originale non è stata modificata, citala pure — l'importante è che sia ancora in vigore
- Se la macchina non rientra in nessuna categoria normata, scrivi null — NON inventare obblighi inesistenti
- Cita sempre: nome della norma, data/numero, articolo o allegato specifico
- Rispondi SOLO con il JSON valido, senza testo aggiuntivo

RIFERIMENTI NORMATIVI PRECISI (usa SOLO questi, non inventare):

ABILITAZIONE OPERATORE — categorie coperte dall'Accordo Stato-Regioni 22/02/2012 (e successive integrazioni):
  COPERTI (obbligo abilitazione): PLE (piattaforme di lavoro elevabili), carrelli elevatori (frontali, laterali, retrattili, trilaterali, bidirezionali, a braccio), gru per autocarro, gru mobili, gru a torre, escavatori, pale caricatrici frontali, terne, autoribaltabili a cingoli, trattori agricoli/forestali, macchine movimento terra (terne incluse), pompe per cls (gli autisti di pompa per calcestruzzo sono coperti dall'Accordo S-R 22/02/2012 come "pompa per calcestruzzo"), piattaforme di lavoro mobili elevabili.
  NON COPERTI (nessun obbligo abilitazione specifica): compressori d'aria, generatori elettrici, piastre vibranti, rulli compattatori, fresatrici stradali, macchine per il calcestruzzo (betoniere), saldatrici, macchinari industriali fissi (presse, piegatrici), bulldozer/apripista (D6, D8, ecc.) — per questi il D.Lgs. 81/08 richiede solo la formazione generica ex Art. 37 e informazione/addestramento specifico Art. 73, senza patentino obbligatorio. Scrivi null per queste categorie.
  ATTENZIONE — NON confondere e NON citare Accordo S-R 2012 per le categorie NON COPERTI sopra elencate: per piastra vibrante, compressore, generatore, betoniera, bulldozer → abilitazione_operatore = null (nessun patentino). Non scrivere frasi tipo "sebbene non sia previsto" — scrivi semplicemente null. Per le pompe calcestruzzo (autobetonpompe) invece SÌ è previsto l'obbligo.

VERIFICHE PERIODICHE Allegato VII D.Lgs. 81/08 — categorie soggette:
  SOGGETTI a verifiche: apparecchi di sollevamento materiali con portata > 200 kg (gru, carrelli elevatori, argani, paranchi), apparecchi di sollevamento persone (PLE, ascensori da cantiere, montacarichi), recipienti in pressione, generatori di vapore/acqua surriscaldata, impianti di messa a terra, impianti parafulmine.
  TERNE/RETROESCAVATORI: le terne (es. JCB 3CX, Case 580, Caterpillar 432) RIENTRANO nell'Allegato VII come "apparecchi di sollevamento materiali con portata > 200 kg" SOLO quando attrezzate con benna rovescia o forche — la funzione sollevamento è accessoria ma soggetta. Categoria: "Apparecchi di sollevamento materiali, non azionati a mano, con portata superiore a 200 kg". Cadenza: biennale (prima verifica INAIL, successive ASL/organismo notificato).
  NON soggetti a verifiche Allegato VII: bulldozer/apripista, piastre vibranti, rulli compattatori, compressori d'aria (salvo serbatoi in pressione > 50 litri), generatori elettrici (salvo impianti di messa a terra), escavatori puri (senza funzione di sollevamento), dumper, finitrici, macchine industriali fisse (presse, piegatrici, laser).
  ATTENZIONE: un escavatore (Caterpillar 320, Komatsu PC200) senza gancio di sollevamento NON è soggetto a verifiche Allegato VII. Scrivi null per questi.
  PALE CARICATRICI FRONTALI (wheel loader — es. Volvo L30G/L60/L90, Caterpillar 950/966, Komatsu WA, Liebherr L):
    - Se usata SOLO per movimento terra (benna per scavo/carico): NON soggetta → verifiche_periodiche = null
    - Se usata (anche saltuariamente) per sollevamento carichi sospesi > 200 kg (balle, pallet, tubi, forche): SOGGETTA come "apparecchio di sollevamento materiali di tipo mobile" → verifiche annuali, prima verifica INAIL poi ASL/organismo notificato [Art. 71 c.11 D.Lgs. 81/08 + Allegato VII]
    - In assenza di informazioni sull'utilizzo specifico: scrivi SEMPRE il seguente avviso — "⚠ VERIFICARE IN SOPRALLUOGO: se la macchina viene utilizzata (anche saltuariamente) per sollevare carichi sospesi superiori a 200 kg (es. con forche, gancio, benna rovescia), è soggetta a verifiche periodiche annuali come apparecchio di sollevamento materiali [Art. 71 c.11 D.Lgs. 81/08 + Allegato VII]. L'ispettore deve accertare l'utilizzo effettivo e richiedere il registro delle verifiche se applicabile." """


async def _enrich_legal_fields(card, machine_label: str, provider: str) -> None:
    """
    Arricchisce in-place i campi abilitazione_operatore e verifiche_periodiche
    ricavandoli dalla normativa vigente in base al tipo di macchina.
    Chiamato solo quando uno o entrambi i campi sono None dopo l'analisi documentale.
    """
    try:
        prompt = LEGAL_ENRICH_PROMPT.format(machine_label=machine_label)
        result = await _call_ai_with_text("", prompt, provider, is_fallback=True)
        if card.abilitazione_operatore is None:
            card.abilitazione_operatore = _nullable_str(result.get("abilitazione_operatore"))
        if card.verifiche_periodiche is None:
            card.verifiche_periodiche = _nullable_str(result.get("verifiche_periodiche"))
    except Exception:
        pass  # Campo resta None — non bloccare la generazione della scheda


async def generate_safety_card(
    brand: str,
    model: str,
    # Nuova firma dual-source
    inail_bytes: Optional[bytes] = None,
    inail_url: Optional[str] = None,
    producer_bytes: Optional[bytes] = None,
    producer_url: Optional[str] = None,
    producer_page_count: int = 0,
    # Scheda tecnica commerciale (dati numerici specifici del modello)
    datasheet_bytes: Optional[bytes] = None,
    datasheet_url: Optional[str] = None,
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
    # ID nel catalogo machine_types (None = testo libero, fallback normative hardcoded)
    machine_type_id: Optional[int] = None,
    # Contesto sopralluogo (cantiere/industria/logistica/altro; + fase solo per cantiere)
    workplace_context: Optional[dict] = None,
) -> SafetyCard:
    """
    Genera la scheda di sicurezza combinando INAIL (normativa) + produttore (raccomandazioni).
    Se disponibile una sola fonte, usa quella. Senza fonti: fallback AI.
    """
    provider = settings.get_analysis_provider()

    # Carica regole prompt per tipo macchina da Supabase (cache 15 min).
    # Se non trovate, genera automaticamente via AI (Haiku/Flash) e salva per usi futuri.
    machine_rules: Optional[dict] = None
    try:
        from app.services.prompt_rules_service import get_rules_for_machine_type, generate_and_save_rule
        machine_rules = get_rules_for_machine_type(machine_type or "")
        if machine_rules is None and machine_type and machine_type.strip() and provider != "none":
            machine_rules = await generate_and_save_rule(machine_type, provider)
    except Exception:
        pass

    # Compatibilità legacy: se arriva pdf_bytes dalla vecchia firma
    if pdf_bytes and not inail_bytes and not producer_bytes:
        inail_bytes = pdf_bytes
        inail_url = pdf_url
        producer_page_count = page_count

    has_inail = inail_bytes is not None
    has_producer = producer_bytes is not None

    logger.info(
        "generate_safety_card strategy: has_inail=%s has_producer=%s producer_pages=%d "
        "machine_type=%s producer_label=%s brand=%s model=%s",
        has_inail, has_producer, producer_page_count or 0,
        machine_type or "-", producer_source_label or "-", brand, model,
    )

    # Determina strategia fonte A–F (source_manager) — usata per badge UI e log
    from app.services.source_manager import resolve_sources, source_context_to_dict
    _source_ctx = resolve_sources(
        inail_bytes=inail_bytes,
        producer_bytes=producer_bytes,
        producer_source_label=producer_source_label,
    )

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

    # Calcola il contesto normativo RAG una volta sola — passato a tutte le funzioni interne
    # Fallback silenzioso: se dizionario+RAG non disponibili → stringa vuota
    _norm_ctx = _get_normative_context(machine_type)

    # Inietta contesto sopralluogo all'inizio del contesto normativo (se fornito)
    if workplace_context and isinstance(workplace_context, dict):
        _cat_labels = {
            "cantiere": "Cantiere edile",
            "industria": "Stabilimento industriale",
            "logistica": "Hub logistico / magazzino",
            "altro": "Luogo di lavoro non specificato",
        }
        _phase_labels = {
            "scavo": "Fase di scavo",
            "fondazioni": "Fase di fondazioni",
            "strutture": "Fase di strutture",
            "finiture": "Fase di finiture",
            "demolizione": "Fase di demolizione",
            "altro": "Fase generica",
        }
        _cat = _cat_labels.get(workplace_context.get("category", ""), "")
        _phase = _phase_labels.get(workplace_context.get("phase", ""), "")
        _ctx_block = f"CONTESTO SOPRALLUOGO: Luogo di lavoro: {_cat}."
        if _phase:
            _ctx_block += f" {_phase}."
        _ctx_block += (
            "\nAdatta le raccomandazioni, le priorità di rischio e i controlli checklist "
            "al contesto specifico del sopralluogo."
        )
        _norm_ctx = _ctx_block + ("\n\n" + _norm_ctx if _norm_ctx else "")

    if not has_inail and not has_producer:
        card = await _generate_fallback(
            brand, model, provider, norme=norme or [],
            allegato_v_context=allegato_v_context,
            machine_type=machine_type,
            normative_context=_norm_ctx,
            workplace_context=workplace_context,
        )
        # Se disponibile un datasheet (scheda tecnica commerciale ≤20 pagine),
        # estrai i limiti operativi e sovrascrivili nel risultato fallback AI.
        # Il datasheet non influenza rischi, procedure o dispositivi.
        if datasheet_bytes and not card.limiti_operativi:
            try:
                limiti = await _extract_limiti_from_datasheet(
                    datasheet_bytes, brand, model, provider
                )
                if limiti:
                    card.limiti_operativi = limiti
                    if datasheet_url:
                        card.fonte_manuale = datasheet_url
            except Exception:
                pass  # Non bloccare la scheda se l'estrazione datasheet fallisce
        if ante_ce_note:
            card.note = f"{ante_ce_note} | {card.note}" if card.note else ante_ce_note
    elif has_inail and has_producer:
        card = await _analyze_dual_source(
            brand, model, inail_bytes, inail_url, producer_bytes, producer_url, producer_page_count, provider,
            allegato_v_context=allegato_v_context,
            producer_source_label=effective_producer_label,
            machine_rules=machine_rules,
            normative_context=_norm_ctx,
            workplace_context=workplace_context,
        )
        if ante_ce_note:
            card.note = f"{ante_ce_note} | {card.note}" if card.note else ante_ce_note
    elif has_inail:
        card = await _analyze_pdf_direct(
            brand, model, inail_bytes, inail_url, provider,
            allegato_v_context=allegato_v_context,
            fonte_tipo="inail",
            normative_context=_norm_ctx,
            workplace_context=workplace_context,
        )
        if ante_ce_note:
            card.note = f"{ante_ce_note} | {card.note}" if card.note else ante_ce_note
    elif producer_page_count <= 100:
        card = await _analyze_pdf_direct(
            brand, model, producer_bytes, producer_url, provider,
            allegato_v_context=allegato_v_context,
            is_category_match="categoria" in (producer_source_label or "").lower(),
            normative_context=_norm_ctx,
            workplace_context=workplace_context,
        )
        if ante_ce_note:
            card.note = f"{ante_ce_note} | {card.note}" if card.note else ante_ce_note
    else:
        card = await _analyze_pdf_map_reduce(brand, model, producer_bytes, producer_url, provider,
                                             workplace_context=workplace_context,
                                             is_category_match="categoria" in (producer_source_label or "").lower())
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

    # Arricchimento normativo: se abilitazione o verifiche periodiche non sono state
    # estratte dal documento (il manuale del produttore spesso non le riporta),
    # le ricava dalla normativa vigente in base al tipo di macchina.
    if card.abilitazione_operatore is None or card.verifiche_periodiche is None:
        machine_label = machine_type or f"{brand} {model}"
        await _enrich_legal_fields(card, machine_label, provider)

    # Override deterministico post-AI: per macchine la cui classificazione normativa
    # è nota e non ambigua, forza i valori corretti indipendentemente da quanto
    # estratto dal PDF o generato dall'AI (che spesso sbaglia su queste categorie).
    _apply_normative_overrides(card, machine_type, machine_type_id=machine_type_id)

    # Normative applicabili: mapping deterministico per tipo macchina + norme dalla targa OCR
    try:
        from app.data.machine_normative import get_normative
        card.normative_applicabili = get_normative(machine_type or "")
        if norme:
            # Anteponi le norme dalla targa OCR (rilevate direttamente dalla macchina)
            seen: set[str] = set(card.normative_applicabili)
            extra = [n for n in norme if n not in seen]
            card.normative_applicabili = extra + card.normative_applicabili
    except Exception:
        pass  # Non bloccare la generazione della scheda

    # Arricchisce i campi fonte_* con le sorgenti normative usate (solo se vuoti)
    _enrich_card_sources(card, machine_type)

    # Valida riferimenti normativi nella checklist e svuota prescrizioni non verificate
    _validate_normative_refs(card)

    # Inietta metadati fonte (strategia A–F, badge, disclaimer, affidabilità)
    card.source_metadata = source_context_to_dict(_source_ctx)

    # Log strutturato per osservabilità RAG
    _log_rag_metadata(machine_type, card.fonte_tipo or "unknown")

    # Log asincrono strategia fonte → analysis_log (non bloccante)
    _log_analysis_sync(brand, model, machine_type, _source_ctx, machine_type_id=machine_type_id)

    return card

def _validate_normative_refs(card: "SafetyCard") -> None:
    """
    Verifica che le norme citate nella checklist esistano nel dizionario D.Lgs 81/08.
    Se una norma non è nel dizionario, svuota prescrizione_precompilata (non rimuove l'item).
    """
    try:
        from app.data.riferimenti_normativi import _RIFERIMENTI_SEED
        # Estrae tutti gli articoli verificati dal dizionario
        norme_certe: set[str] = set()
        for ref in _RIFERIMENTI_SEED.values():
            norma = ref.get("norma") or ref.get("articolo") or ""
            if norma:
                norme_certe.add(norma.lower())

        if not norme_certe:
            return

        for item in card.checklist:
            if not isinstance(item, dict):
                continue
            norma = (item.get("norma") or "").strip()
            if not norma:
                continue
            norma_l = norma.lower()
            # Verifica se la norma citata contiene almeno uno degli articoli certi
            verificata = any(n in norma_l for n in norme_certe)
            if not verificata:
                item["prescrizione_precompilata"] = ""
                item["_norma_non_verificata"] = True
    except Exception:
        pass  # Non bloccare mai la generazione della scheda


def _log_analysis_sync(
    brand: str,
    model: str,
    machine_type: Optional[str],
    ctx: "SourceContext",
    machine_type_id: Optional[int] = None,
) -> None:
    """
    Inserisce un record in analysis_log con la strategia fonte usata.
    Usa psycopg2 sincrono. Fallisce silenziosamente — non blocca la risposta.
    """
    try:
        import psycopg2
        db_url = settings.database_url
        if not db_url:
            return
        # Auto-resolve ID se non fornito
        if machine_type_id is None and machine_type:
            try:
                from app.services.machine_type_service import resolve_machine_type_id
                machine_type_id = resolve_machine_type_id(machine_type)
            except Exception:
                pass
        conn = psycopg2.connect(db_url)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO analysis_log
                        (brand, model, machine_type_id,
                         strategy, badge_label, affidabilita, fonte_tipo)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (brand, model, machine_type_id,
                     ctx.strategy, ctx.badge_label,
                     ctx.affidabilita, ctx.fonte_tipo),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass  # Log non bloccante


def _ensure_analysis_log_table() -> None:
    """Crea la tabella analysis_log se non esiste. Chiamata lazy al primo log."""
    try:
        import psycopg2
        db_url = settings.database_url
        if not db_url:
            return
        conn = psycopg2.connect(db_url)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS analysis_log (
                        id          SERIAL PRIMARY KEY,
                        ts          TIMESTAMP NOT NULL DEFAULT NOW(),
                        brand       TEXT,
                        model       TEXT,
                        machine_type TEXT,
                        strategy    TEXT NOT NULL,
                        badge_label TEXT,
                        affidabilita INT,
                        fonte_tipo  TEXT
                    )
                """)
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


# Crea la tabella al primo import del modulo (lazy, non blocca avvio se DB non disponibile)
try:
    _ensure_analysis_log_table()
except Exception:
    pass


# Macchine per cui abilitazione_operatore deve essere sempre null
# (non coperte dall'Accordo Stato-Regioni 2012 né da altra norma settoriale)
_NO_PATENTINO_TYPES: frozenset[str] = frozenset({
    "compressore", "motocompressore", "compressore d'aria", "compressore aria",
    "gruppo elettrogeno", "generatore", "generatore elettrico",
    "piastra vibrante", "costipatore",
    "rullo compattatore", "rullo compressore", "rullo", "compattatore",
    "bulldozer", "apripista",
    "betoniera",
    "saldatrice", "saldatrice mig", "saldatrice tig", "saldatrice ad arco",
    "pressa", "pressa idraulica", "pressa piegatrice", "piegatrice",
    "punzonatrice", "cesoie", "tranciatrice",
    "tornio", "fresatrice", "rettificatrice",
    "laser", "macchina taglio laser", "taglio laser",
    "troncatrice", "troncatrice per alluminio",
    "benna a polipo", "benna carico-pietrisco", "benna", "polipo",
    "pinza demolitrice", "martello demolitore",
    "vibratore per calcestruzzo",
})

# Macchine per cui verifiche_periodiche deve essere sempre null
# (non rientrano nell'Allegato VII D.Lgs. 81/08 come apparecchi di sollevamento
#  né come recipienti in pressione)
_NO_VERIFICHE_TYPES: frozenset[str] = frozenset({
    "compressore", "motocompressore", "compressore d'aria", "compressore aria",
    "gruppo elettrogeno", "generatore", "generatore elettrico",
    "piastra vibrante", "costipatore",
    "rullo compattatore", "rullo compressore", "rullo", "compattatore",
    "bulldozer", "apripista",
    "betoniera",
    "saldatrice", "saldatrice mig", "saldatrice tig", "saldatrice ad arco",
    "pressa", "pressa idraulica", "pressa piegatrice", "piegatrice",
    "punzonatrice", "cesoie", "tranciatrice",
    "tornio", "fresatrice", "rettificatrice",
    "laser", "macchina taglio laser", "taglio laser",
    "troncatrice", "troncatrice per alluminio",
    "dumper", "finitrice",
    "benna a polipo", "benna carico-pietrisco", "benna", "polipo",
    "pinza demolitrice", "martello demolitore",
    "vibratore per calcestruzzo",
    "escavatore", "escavatore idraulico",  # puro, senza funzione di sollevamento
})


def _apply_normative_overrides(card, machine_type: Optional[str], machine_type_id: Optional[int] = None) -> None:
    """
    Forza a None i campi normativi per categorie dove la regola è certa e l'AI sbaglia spesso.
    Priorità: DB flags (machine_type_id) > frozenset hardcoded (backward compat).
    Chiamata dopo _enrich_legal_fields() — sovrascrive sia output AI che contenuto estratto dal PDF.
    """
    if machine_type_id is not None:
        # DB è la fonte autorevole — fail-safe conservativo integrato in get_type_flags
        try:
            from app.services.machine_type_service import get_type_flags
            flags = get_type_flags(machine_type_id)
            if not flags["requires_patentino"]:
                card.abilitazione_operatore = None
            if not flags["requires_verifiche"]:
                card.verifiche_periodiche = None
            return  # DB ha risposto — non serve il fallback hardcoded
        except Exception:
            pass  # Fallback sotto

    # Fallback hardcoded (backward compat quando machine_type_id non disponibile)
    if not machine_type:
        return
    mt = machine_type.lower().strip()

    if mt in _NO_PATENTINO_TYPES:
        card.abilitazione_operatore = None

    if mt in _NO_VERIFICHE_TYPES:
        card.verifiche_periodiche = None


_EMERGENCY_TYPES = {
    "incendio":            ["incendio", "fuoco", "fire"],
    "ribaltamento":        ["ribaltamento", "capovolgimento", "rollover"],
    "cedimento_freni":     ["freni", "idraulico", "cedimento freni", "cedimento idraulico", "brake"],
    "investimento_persone":["investimento", "persona investita", "pedestrian", "persone"],
    "folgorazione":        ["folgorazione", "elettrico", "electrocution", "scarica"],
    "seppellimento":       ["seppellimento", "crollo", "burial", "collapse"],
}

AI_DISCLAIMER_TEXT = (
    "Procedura generata da intelligenza artificiale sulla base delle linee guida INAIL. "
    "Verificare con il manuale del costruttore prima dell'applicazione."
)


async def _fill_emergency_gaps(
    procedures: list,
    brand: str,
    model: str,
    machine_type: Optional[str],
    provider: str,
) -> list:
    """
    Controlla quali tipi di emergenza (whitelist) non sono coperti dalle procedure esistenti.
    Per i tipi mancanti genera una procedura AI con source_tier='ai' e ai_disclaimer=True.
    Restituisce la lista aggiornata (originale + nuove).
    """
    def _covers_type(testo: str, keywords: list[str]) -> bool:
        t = testo.lower()
        return any(kw in t for kw in keywords)

    missing_types: list[str] = []
    for etype, keywords in _EMERGENCY_TYPES.items():
        covered = any(
            _covers_type(p.get("testo", "") if isinstance(p, dict) else str(p), keywords)
            for p in procedures
        )
        if not covered:
            missing_types.append(etype)

    if not missing_types:
        return procedures

    machine_desc = f"{brand} {model}" + (f" ({machine_type})" if machine_type else "")
    missing_labels = {
        "incendio": "Incendio a bordo macchina",
        "ribaltamento": "Ribaltamento della macchina",
        "cedimento_freni": "Cedimento freni/sistema idraulico",
        "investimento_persone": "Investimento di persone",
        "folgorazione": "Folgorazione / contatto con linee elettriche",
        "seppellimento": "Seppellimento / crollo di scavi o strutture",
    }
    labels_list = "\n".join(f"- {missing_labels[t]}" for t in missing_types)

    prompt = f"""Genera procedure di emergenza sintetiche per la macchina {machine_desc}.
Crea UNA procedura per CIASCUNO dei seguenti tipi di emergenza che mettono a rischio persone:
{labels_list}

Rispondi SOLO con questo JSON:
{{
  "procedures": [
    {{"testo": "Tipo emergenza — Passo 1: [azione]. Passo 2: [azione]. Passo 3: [azione]."}},
    ...
  ]
}}

Genera esattamente {len(missing_types)} oggetti nell'array procedures, uno per tipo.
Le procedure devono essere pratiche per la categoria di macchina. Rispondi SOLO con il JSON."""

    try:
        raw = await _call_ai_with_text("", prompt, provider, is_fallback=True)
        generated: list = raw.get("procedures", []) if isinstance(raw, dict) else []
    except Exception:
        generated = []

    ai_procedures = []
    for item in generated:
        if isinstance(item, dict) and item.get("testo"):
            ai_procedures.append({
                "testo": item["testo"],
                "fonte": "AI (INAIL linee guida)",
                "source_tier": "ai",
                "ai_disclaimer": True,
            })

    return procedures + ai_procedures


async def _analyze_dual_source(
    brand: str, model: str,
    inail_bytes: bytes, inail_url: Optional[str],
    producer_bytes: bytes, producer_url: Optional[str],
    producer_pages: int,
    provider: str,
    allegato_v_context: Optional[str] = None,
    producer_source_label: Optional[str] = None,
    machine_rules: Optional[dict] = None,
    normative_context: str = "",
    workplace_context: Optional[dict] = None,
) -> SafetyCard:
    """
    Analisi combinata: INAIL → rischi/DPI/residui; produttore → raccomandazioni specifiche.
    Le due analisi vengono eseguite in parallelo, poi fuse.
    """
    import asyncio

    is_category_match = "categoria" in (producer_source_label or "").lower()
    inail_prompt = _build_inail_prompt(machine_rules=machine_rules, workplace_context=workplace_context)
    producer_prompt = _build_producer_prompt(brand, model, machine_rules=machine_rules,
                                             is_category_match=is_category_match)
    if allegato_v_context:
        inail_prompt += f"\n\nCONTESTO ALLEGATO V (macchina ante-1996):\n{allegato_v_context}\n{ALLEGATO_V_EXTRA_FIELDS}"

    # Anteponi contesto normativo RAG (dizionario D.Lgs + Direttiva/INAIL ChromaDB)
    # Solo al prompt INAIL (fonte normativa) — non al produttore (fonte operativa)
    if normative_context:
        inail_prompt = normative_context + "\n\n---\n\n" + inail_prompt

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
        """Converte una lista di stringhe/dicts in {testo, fonte, ...}; preserva campi extra (probabilita, gravita)."""
        result = []
        for item in items:
            if not item:
                continue
            if isinstance(item, dict):
                result.append(item if "fonte" in item else {**item, "fonte": fonte})
            else:
                result.append({"testo": str(item), "fonte": fonte})
        return result

    def _tag_devices(devices: list, fonte: str) -> list:
        """Aggiunge il campo fonte a ogni dispositivo di sicurezza."""
        result = []
        for d in devices:
            if isinstance(d, dict) and d.get("nome"):
                result.append({**d, "fonte": fonte})
        return result

    # ── PESATURA FONTI ────────────────────────────────────────────────────────
    # INAIL = fonte normativa → vince sempre sui campi normativi (rischi, DPI, residui).
    # Produttore = fonte operativa → aggiunge solo ciò che INAIL non copre già.
    # Deduplicazione semantica (Jaccard su token) per evitare ridondanze tra fonti.

    # Rischi: INAIL è primario; produttore aggiunge SOLO rischi semanticamente nuovi
    rischi = _tag_items(inail_json.get("rischi_principali") or [], inail_label)
    dpi = _tag_items(inail_json.get("dispositivi_protezione") or [], inail_label)
    racc = _tag_items(
        (producer_json.get("raccomandazioni_produttore") or []) +
        (producer_json.get("verifiche_sicurezza") or []),
        producer_label,
    )
    residui = _tag_items(inail_json.get("rischi_residui") or [], inail_label)

    # Arricchisci con rischi specifici del modello — dedup semantica contro rischi INAIL
    rischi_specifici_raw = _tag_items(
        producer_json.get("rischi_specifici_modello") or [], producer_label
    )
    nuovi_rischi = _semantic_dedup(rischi_specifici_raw, rischi)
    rischi.extend(nuovi_rischi)

    # Dispositivi di sicurezza: INAIL è normativo → vince sui conflitti per nome;
    # produttore aggiunge dispositivi specifici del modello non già in INAIL
    disp_inail = _tag_devices(inail_json.get("dispositivi_sicurezza") or [], inail_label)
    disp_prod  = _tag_devices(producer_json.get("dispositivi_sicurezza") or [], producer_label)
    seen_device_names: set[str] = set()
    dispositivi_merged = []
    # INAIL prima (fonte normativa ha precedenza in caso di conflitto per nome)
    for d in disp_inail + disp_prod:
        key = d.get("nome", "").lower().strip()
        if key and key not in seen_device_names:
            seen_device_names.add(key)
            dispositivi_merged.append(d)

    # Checklist: INAIL prima, poi produttore con dedup semantica
    # Normalizza: accetta sia stringhe (compat. retroattiva) sia oggetti {testo, livello, norma, ...}
    def _norm_cl(items: list) -> list[dict]:
        result = []
        for i in items:
            if isinstance(i, str):
                result.append({"testo": i, "livello": 2})
            elif isinstance(i, dict) and i.get("testo"):
                result.append(i)
        return result

    checklist_inail_raw = _norm_cl(inail_json.get("checklist") or [])
    checklist_prod_raw  = _norm_cl(producer_json.get("checklist") or [])
    # Dedup esatta su INAIL stesso (su campo testo)
    seen_cl: set[str] = set()
    checklist_inail_deduped: list[dict] = []
    for item in checklist_inail_raw:
        key = item["testo"].lower().strip()
        if key not in seen_cl:
            seen_cl.add(key)
            checklist_inail_deduped.append(item)
    # Dedup semantica: aggiunge dal produttore solo voci non già coperte da INAIL
    cl_inail_for_dedup = [{"testo": i["testo"]} for i in checklist_inail_deduped]
    cl_prod_for_dedup  = [{"testo": i["testo"]} for i in checklist_prod_raw]
    nuove_cl_keys = {d["testo"] for d in _semantic_dedup(cl_prod_for_dedup, cl_inail_for_dedup)}
    nuove_cl = [i for i in checklist_prod_raw if i["testo"] in nuove_cl_keys]
    checklist_merged = checklist_inail_deduped + nuove_cl

    # Nuovi campi ispettivi da fonti distinte
    procedure_emergenza = _tag_items(
        producer_json.get("procedure_emergenza") or [],
        producer_label,
    )
    # Completa con procedure AI per tipi di emergenza non coperti (F4 — cascade)
    procedure_emergenza = await _fill_emergency_gaps(
        procedure_emergenza, brand, model,
        machine_type=None, provider=provider,
    )
    limiti_operativi = _tag_items(
        producer_json.get("limiti_operativi") or [],
        producer_label,
    )
    pittogrammi_sicurezza = producer_json.get("pittogrammi_sicurezza") or []

    # abilitazione_operatore: INAIL è fonte normativa primaria; produttore come fallback
    # o integrazione se aggiunge informazioni non presenti in INAIL
    _abilitazione_inail = _nullable_str(inail_json.get("abilitazione_operatore"))
    _abilitazione_prod  = _nullable_str(producer_json.get("abilitazione_operatore"))
    if _abilitazione_inail and _abilitazione_prod:
        # Combina se il produttore aggiunge info non già presenti (evita duplicati verbatim)
        if _abilitazione_prod.lower().strip() not in _abilitazione_inail.lower():
            abilitazione_operatore = f"{_abilitazione_inail} | [{brand}] {_abilitazione_prod}"
        else:
            abilitazione_operatore = _abilitazione_inail
    else:
        abilitazione_operatore = _abilitazione_inail or _abilitazione_prod

    # verifiche_periodiche: stessa logica — INAIL primario, produttore come fallback/integrazione
    _verifiche_inail = _nullable_str(inail_json.get("verifiche_periodiche"))
    _verifiche_prod  = _nullable_str(producer_json.get("verifiche_periodiche"))
    if _verifiche_inail and _verifiche_prod:
        if _verifiche_prod.lower().strip() not in _verifiche_inail.lower():
            verifiche_periodiche = f"{_verifiche_inail} | [{brand}] {_verifiche_prod}"
        else:
            verifiche_periodiche = _verifiche_inail
    else:
        verifiche_periodiche = _verifiche_inail or _verifiche_prod

    # documenti_da_richiedere: merge liste, deduplicati (INAIL prima, poi aggiunte del produttore)
    # Normalizza: accetta sia stringhe (compat.) sia oggetti {documento, smart_hint}
    _docs_inail = inail_json.get("documenti_da_richiedere") or []
    _docs_prod  = producer_json.get("documenti_da_richiedere") or []
    _docs_seen: set[str] = set()
    documenti_da_richiedere = []
    for doc in _docs_inail + _docs_prod:
        if isinstance(doc, str):
            key = doc.lower().strip()
            if key not in _docs_seen:
                _docs_seen.add(key)
                documenti_da_richiedere.append({"documento": doc, "smart_hint": ""})
        elif isinstance(doc, dict) and doc.get("documento"):
            key = doc["documento"].lower().strip()
            if key not in _docs_seen:
                _docs_seen.add(key)
                documenti_da_richiedere.append(doc)

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
    fonte_tipo: str = "pdf",
    is_category_match: bool = False,
    normative_context: str = "",
    workplace_context: Optional[dict] = None,
) -> SafetyCard:
    """Analisi diretta del PDF (≤100 pagine) — inviato come documento nativo."""
    pdf_b64 = pdf_service.pdf_to_base64(pdf_bytes)
    prompt = _build_analysis_prompt(brand, model, is_category_match=is_category_match,
                                    workplace_context=workplace_context)
    if allegato_v_context:
        prompt += f"\n\nCONTESTO ALLEGATO V (macchina ante-1996):\n{allegato_v_context}\n{ALLEGATO_V_EXTRA_FIELDS}"

    # Anteponi contesto normativo RAG se disponibile
    if normative_context:
        prompt = normative_context + "\n\n---\n\n" + prompt

    # Rileva lingua dal testo estratto e rafforza istruzione traduzione
    text = pdf_service.extract_full_text(pdf_bytes)
    lang = _detect_language(text)
    prompt += _translation_note(lang)

    if provider == "anthropic":
        result_json = await _call_claude_with_pdf(pdf_b64, prompt)
    else:
        result_json = await _call_ai_with_text(text, prompt, provider)

    card = _build_safety_card(brand, model, result_json, pdf_url, fonte_tipo)
    card.gap_ce_ante = result_json.get("gap_ce_ante")
    card.bozze_prescrizioni = result_json.get("bozze_prescrizioni") or []
    return card


async def _analyze_pdf_map_reduce(
    brand: str, model: str, pdf_bytes: bytes, pdf_url: Optional[str], provider: str,
    workplace_context: Optional[dict] = None,
    is_category_match: bool = False,
) -> SafetyCard:
    """Analisi map-reduce per PDF grandi (>100 pagine)."""
    text = pdf_service.extract_safety_relevant_text(pdf_bytes, max_pages=50)
    chunks = pdf_service.chunk_text(text, max_chars=80000)
    prompt = _build_analysis_prompt(brand, model, is_category_match=is_category_match,
                                    workplace_context=workplace_context)

    # MAP: analizza ogni chunk
    partial = []
    for i, chunk in enumerate(chunks[:8]):  # Max 8 chunk (aumentato da 5 per manuali molto grandi)
        try:
            partial_json = await _call_ai_with_text(chunk, prompt, provider)
            partial.append(json.dumps(partial_json, ensure_ascii=False))
        except Exception as e:
            logger.warning("map-reduce chunk %d/%d failed for %s %s: %s", i + 1, min(8, len(chunks)), brand, model, e)
            continue

    if not partial:
        return await _generate_fallback(brand, model, provider)

    if len(partial) == 1:
        return _build_safety_card(brand, model, json.loads(partial[0]), pdf_url, "pdf")

    # REDUCE: sintetizza i risultati parziali
    # Usa .replace() invece di .format() per evitare che i { } dell'output AI
    # (JSON delle analisi parziali) vengano interpretati come format specifier.
    partial_analyses_str = "\n\n---\n\n".join(partial)
    reduce_prompt = (
        REDUCE_PROMPT
        .replace("{n}", str(len(partial)))
        .replace("{partial_analyses}", partial_analyses_str)
    )
    result_json = await _call_ai_with_text("", reduce_prompt, provider, is_reduce=True)
    return _build_safety_card(brand, model, result_json, pdf_url, "pdf")


async def _generate_fallback(
    brand: str, model: str, provider: str,
    norme: list = [],
    allegato_v_context: Optional[str] = None,
    machine_type: Optional[str] = None,
    normative_context: str = "",
    workplace_context: Optional[dict] = None,
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
    # Inietta norma EN di categoria per migliorare precisione valori limite nel fallback.
    # get_normative() già esiste e mappa tipo macchina → norme EN/UNI/ISO applicabili.
    if machine_type and not norme_context:
        try:
            from app.data.machine_normative import get_normative
            cat_norme = get_normative(machine_type)
            norma_en = next((n for n in cat_norme if "EN" in n or "ISO" in n), None)
            if norma_en:
                norme_context = (
                    f"\n\nNORMA EN APPLICABILE A QUESTA CATEGORIA: {norma_en}\n"
                    "Per i limiti operativi e i dispositivi obbligatori, usa i valori minimi/massimi "
                    "definiti da questa norma come riferimento. Citala nelle voci pertinenti."
                )
        except Exception:
            pass
    av_context = ""
    if allegato_v_context:
        av_context = f"\n\nCONTESTO ALLEGATO V (macchina ante-1996):\n{allegato_v_context}\n{ALLEGATO_V_EXTRA_FIELDS}"
    # Sanitizza brand/model da caratteri che rompono .format() (es. '{', '}' da OCR errato)
    safe_brand = brand.replace("{", "{{").replace("}", "}}")
    safe_model = model.replace("{", "{{").replace("}", "}}")
    # Inietta il tipo macchina confermato dall'utente: essenziale per evitare che l'AI
    # generi la scheda per la categoria sbagliata quando brand+model sono sconosciuti.
    machine_type_context = ""
    if machine_type and machine_type.strip():
        safe_mt = machine_type.strip()
        machine_type_context = (
            f"\n\nTIPO MACCHINA CONFERMATO DALL'UTENTE: {safe_mt}\n"
            f"⚠ CRITICO: Genera la scheda di sicurezza ESCLUSIVAMENTE per una '{safe_mt}'. "
            f"NON generare contenuti per altri tipi di macchina (es. PLE, escavatore, carrello elevatore) "
            f"anche se il brand+modello non ti sono noti. "
            f"Usa questa classificazione per tutti i rischi, dispositivi, normative e procedure."
        )
    workplace_hints = _workplace_prompt_hints(workplace_context)
    prompt = FALLBACK_PROMPT_TEMPLATE.format(brand=safe_brand, model=safe_model) + machine_type_context + norme_context + av_context + workplace_hints
    # Anteponi contesto normativo RAG se disponibile
    if normative_context:
        prompt = normative_context + "\n\n---\n\n" + prompt
    result_json = await _call_ai_with_text("", prompt, provider, is_fallback=True)
    card = _build_safety_card(brand, model, result_json, None, "fallback_ai")
    card.gap_ce_ante = result_json.get("gap_ce_ante")
    card.bozze_prescrizioni = result_json.get("bozze_prescrizioni") or []
    return card


_DATASHEET_LIMITI_PROMPT = """Dalla scheda tecnica commerciale di {brand} {model} estrai SOLO i dati numerici misurabili:
potenza (kW o HP), peso (kg o t), livello rumore dichiarato (dB(A)), dimensioni operative (mm o cm),
portata/capacità massima (kg o t), velocità massima (km/h o m/s), tensione alimentazione (V/Hz),
grado di protezione IP, altre specifiche numeriche rilevanti per la sicurezza.

Rispondi SOLO con JSON valido:
{{"limiti_operativi": [{{"valore": "...", "unita": "...", "descrizione": "..."}}]}}

Lista vuota [] se nessun dato numerico trovato nel documento.
Non inventare valori non presenti nel testo."""


async def _extract_limiti_from_datasheet(
    pdf_bytes: bytes, brand: str, model: str, provider: str
) -> list:
    """
    Estrae solo i dati numerici (limiti_operativi) da una scheda tecnica commerciale.
    Usato esclusivamente quando non è disponibile né INAIL né manuale produttore.
    """
    try:
        text = pdf_service.extract_full_text(pdf_bytes)
        if not text or len(text.strip()) < 50:
            return []
        safe_brand = brand.replace("{", "{{").replace("}", "}}")
        safe_model = model.replace("{", "{{").replace("}", "}}")
        prompt = _DATASHEET_LIMITI_PROMPT.format(brand=safe_brand, model=safe_model)
        result_json = await _call_ai_with_text(text[:4000], prompt, provider)
        limiti = result_json.get("limiti_operativi") or []
        # Valida struttura minima: ogni voce deve avere almeno "valore"
        return [item for item in limiti if isinstance(item, dict) and item.get("valore")]
    except Exception:
        return []


import logging as _logging
_ai_logger = _logging.getLogger(__name__)


def _check_anthropic_finish_reason(response) -> None:
    """Logga un warning se la risposta Claude è stata troncata per limite token."""
    if getattr(response, "stop_reason", None) == "max_tokens":
        usage = getattr(response, "usage", None)
        out = getattr(usage, "output_tokens", "?") if usage else "?"
        _ai_logger.warning(
            "Claude: risposta troncata per limite token (output_tokens=%s). "
            "Il JSON potrebbe essere incompleto — considera di aumentare max_tokens.", out
        )


def _check_gemini_finish_reason(response) -> None:
    """Logga un warning se la risposta Gemini è stata troncata per limite token."""
    try:
        candidate = response.candidates[0] if response.candidates else None
        if candidate is None:
            return
        reason = getattr(candidate, "finish_reason", None)
        # Il valore può essere l'enum o la stringa a seconda della versione SDK
        reason_str = reason.name if hasattr(reason, "name") else str(reason)
        if reason_str in ("MAX_TOKENS", "2"):  # 2 = MAX_TOKENS nell'enum gRPC
            _ai_logger.warning(
                "Gemini: risposta troncata per limite token (finish_reason=%s). "
                "Il JSON potrebbe essere incompleto — considera di aumentare max_output_tokens.",
                reason_str
            )
    except Exception:
        pass  # Non bloccare mai per un warning di diagnostica


async def _call_claude_with_pdf(pdf_b64: str, prompt: str) -> dict:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=16000,
        temperature=0,
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
    _check_anthropic_finish_reason(response)
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
            max_tokens=16000,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": full_prompt}],
        )
        _check_anthropic_finish_reason(response)
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
                max_output_tokens=16000,
                temperature=0.0,
                # thinking_budget=0 disabilita il reasoning interno del modello:
                # senza thinking, gemini-2.5-flash rispetta temperature=0 correttamente.
                # Il reasoning non serve per estrarre JSON strutturato da un documento.
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        _check_gemini_finish_reason(response)
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
    # Campi stringa singola — gestisce anche valori con virgolette escapate e testo lungo
    for str_field in ["gap_ce_ante", "abilitazione_operatore", "verifiche_periodiche", "confidence_ai"]:
        # Cerca sia "campo": "valore" che "campo": null
        m_null = re.search(rf'"{str_field}"\s*:\s*null', text, re.IGNORECASE)
        if m_null:
            result[str_field] = None
            continue
        m_str = re.search(rf'"{str_field}"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
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


def _semantic_dedup(items: list[dict], existing: list[dict], threshold: float = 0.55) -> list[dict]:
    """
    Deduplicazione semantica leggera basata su overlap di token.
    Aggiunge da `items` solo le voci il cui testo non sia già "coperto" da
    qualcosa in `existing` con Jaccard similarity ≥ threshold.

    Strategia: tokenizza in parole significative (≥4 char, escluse stopword
    comuni), calcola |A∩B|/|A∪B|. Nessuna dipendenza esterna.
    """
    _STOPWORDS = {
        "della", "dello", "degli", "delle", "nella", "nello", "negli", "nelle",
        "questo", "questa", "questi", "queste", "sono", "essere", "avere",
        "viene", "devono", "deve", "verificare", "controllo", "verifica",
        "assicurarsi", "accertarsi", "presenza", "assenza", "durante",
        "prima", "dopo", "ogni", "volta", "come", "dove", "cosa",
        "macchina", "macchinario", "operatore", "dispositivo",
    }

    def _tokens(text: str) -> set[str]:
        words = re.findall(r"[a-zA-ZÀ-ú]{4,}", text.lower())
        return {w for w in words if w not in _STOPWORDS}

    def _jaccard(a: set, b: set) -> float:
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    existing_token_sets = [_tokens(e.get("testo", "")) for e in existing]
    result = []
    combined_token_sets = list(existing_token_sets)
    for item in items:
        tok = _tokens(item.get("testo", ""))
        if not tok:
            continue
        if any(_jaccard(tok, ex) >= threshold for ex in combined_token_sets):
            continue  # semanticamente duplicato
        result.append(item)
        combined_token_sets.append(tok)
    return result

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
        attrezzature_intercambiabili=_nullable_str(data.get("attrezzature_intercambiabili")),
    )
