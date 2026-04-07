"""
Mapping deterministico machine_type → normative applicabili vigenti.
Aggiornare manualmente quando escono nuove norme o recepimenti italiani.
"""
from typing import List

# Normative sempre applicabili a qualsiasi macchinario
_ALWAYS_APPLICABLE: List[str] = [
    "Direttiva Macchine 2006/42/CE (D.Lgs. 17/2010)",
    "UNI EN ISO 12100:2010 — Sicurezza del macchinario: principi generali di progettazione",
    "D.Lgs. 81/2008 — Testo Unico Sicurezza sul Lavoro",
]

# Mapping: chiave (lowercase) → normative specifiche per il tipo
_NORMATIVE_MAP: dict[str, List[str]] = {
    "piattaforma aerea": [
        "EN 280:2013+A1:2015 — PLE con braccio mobile",
        "EN 1570-1:2011+A1:2014 — Tavole elevatori",
        "EN ISO 18878:2013 — Piattaforme elevabili mobili di lavoro: addestramento degli operatori",
        "D.Lgs. 81/2008 Allegato V e VII (verifiche periodiche annuali INAIL/ASL)",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori PLE (con/senza stabilizzatori)",
        "Circ. Min. Lav. 30/2011 — Modalità di effettuazione delle verifiche periodiche",
    ],
    "piattaforma a forbice": [
        "EN 1570-1:2011+A1:2014 — Tavole elevatori",
        "EN 280:2013+A1:2015 — PLE (se con braccio mobile)",
        "D.Lgs. 81/2008 Allegato V e VII",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori PLE",
    ],
    "carrello elevatore": [
        "EN ISO 3691-1:2015+A1:2020 — Carrelli industriali semoventi",
        "EN ISO 3691-4:2020 — Carrelli industriali senza conducente",
        "EN ISO 3691-5:2009 — Carrelli a presa anteriore con braccio telescopico",
        "EN 1551:2017 — Carrelli industriali con portata > 10 t",
        "D.Lgs. 81/2008 Allegato V e VII",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori carrelli elevatori",
    ],
    "sollevatore telescopico": [
        "EN ISO 3691-5:2009 — Carrelli a presa anteriore con braccio telescopico",
        "EN 1459-1:2017+A1:2020 — Carrelli telescopici",
        "D.Lgs. 81/2008 Allegato V e VII",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori carrelli telescopici",
    ],
    "gru mobile": [
        "EN 13000:2010+A1:2014 — Gru mobili",
        "EN 12999:2011+A1:2012 — Gru caricatrici",
        "UNI EN ISO 12100:2010",
        "D.Lgs. 81/2008 Allegato V e VII (verifica annuale/biennale INAIL)",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori gru mobili",
        "D.M. 11/04/2011 — Criteri generali verifica periodica attrezzature",
    ],
    "gru a torre": [
        "EN 14439:2009+A2:2011 — Gru a torre",
        "UNI EN ISO 12100:2010",
        "D.Lgs. 81/2008 Allegato V e VII",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori gru a torre",
    ],
    "gru": [
        "EN 13000:2010+A1:2014 — Gru mobili",
        "EN 14439:2009+A2:2011 — Gru a torre",
        "EN 13157:2004+A1:2009 — Gru azionate a mano",
        "D.Lgs. 81/2008 Allegato V e VII",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori gru",
    ],
    "escavatore": [
        "EN 474-1:2006+A4:2013 — Macchine per movimento terra: requisiti generali",
        "EN 474-5:2006+A3:2013 — Escavatori idraulici",
        "UNI EN ISO 12100:2010",
        "D.Lgs. 81/2008 Allegato V",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori escavatori idraulici/a fune",
    ],
    "pala caricatrice": [
        "EN 474-1:2006+A4:2013 — Requisiti generali macchine movimento terra",
        "EN 474-3:2006+A2:2012 — Pale caricatrici",
        "UNI EN ISO 12100:2010",
        "D.Lgs. 81/2008 Allegato V",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori pale caricatrici",
    ],
    "terna": [
        "EN 474-1:2006+A4:2013 — Requisiti generali",
        "EN 474-4:2006+A2:2012 — Terne",
        "UNI EN ISO 12100:2010",
        "D.Lgs. 81/2008 Allegato V",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori terne",
    ],
    "retroescavatore": [
        "EN 474-1:2006+A4:2013",
        "EN 474-4:2006+A2:2012 — Terne",
        "D.Lgs. 81/2008 Allegato V",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori terne",
    ],
    "bulldozer": [
        "EN 474-1:2006+A4:2013",
        "EN 474-2:2006+A1:2008 — Bulldozer",
        "D.Lgs. 81/2008 Allegato V",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori",
    ],
    "compressore": [
        "EN 1012-1:2010 — Compressori e pompe a vuoto: requisiti di sicurezza",
        "PED 2014/68/UE (Direttiva Attrezzature in Pressione) — se applicabile",
        "D.Lgs. 81/2008 Allegato V e VII (recipienti in pressione)",
        "D.M. 01/12/2004 n. 329 — Messa in servizio attrezzature a pressione",
    ],
    "generatore": [
        "EN IEC 60034-1:2010 — Macchine elettriche rotanti",
        "EN IEC 60204-1:2018 — Sicurezza macchine: equipaggiamento elettrico",
        "D.Lgs. 81/2008 Allegato V",
        "D.M. 37/2008 — Impianti elettrici nei cantieri",
    ],
    "pompa calcestruzzo": [
        "EN 12001:2012 — Macchine per convogliare calcestruzzo",
        "UNI EN ISO 12100:2010",
        "D.Lgs. 81/2008 Allegato V e VII",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori pompe calcestruzzo",
    ],
    "autoribaltabile": [
        "EN 474-1:2006+A4:2013",
        "EN 474-6:2006+A1:2009 — Dumper",
        "D.Lgs. 81/2008 Allegato V",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori dumper",
    ],
    "dumper": [
        "EN 474-1:2006+A4:2013",
        "EN 474-6:2006+A1:2009 — Dumper",
        "D.Lgs. 81/2008 Allegato V",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori dumper",
    ],
    "rullo compattatore": [
        "EN 500-1:2006+A1:2009 — Macchine per la costruzione di strade: requisiti generali",
        "EN 500-4:2011 — Rulli compattatori",
        "D.Lgs. 81/2008 Allegato V",
        "Accordo Stato-Regioni 22/02/2012 — Abilitazione operatori rulli compattatori",
    ],
    "betoniera": [
        "EN 14268:2004+A1:2009 — Mescolatori per calcestruzzo",
        "UNI EN ISO 12100:2010",
        "D.Lgs. 81/2008 Allegato V",
    ],
    "pressa piegatrice": [
        "EN 12622:2009+A1:2013 — Sicurezza macchine utensili: presse piegatrici idrauliche",
        "EN ISO 13849-1:2015 — Sicurezza del macchinario: parti dei sistemi di comando",
        "UNI EN ISO 12100:2010",
        "D.Lgs. 81/2008 Allegato V",
    ],
    "saldatrice": [
        "EN 60974-1:2012+A1:2017 — Apparecchi per saldatura ad arco",
        "EN 60974-9:2010 — Installazione e uso",
        "UNI EN ISO 12100:2010",
        "D.Lgs. 81/2008 Allegato V",
    ],
}


def get_normative(machine_type: str) -> List[str]:
    """
    Restituisce le normative applicabili per il tipo macchina specificato.
    Include sempre le normative di base + quelle specifiche per categoria.
    Fallisce silenziosamente restituendo solo le normative base.
    """
    mt = (machine_type or "").lower().strip()
    specific: List[str] = []
    for key, norms in _NORMATIVE_MAP.items():
        if key in mt or mt in key:
            specific = norms
            break
    # Evita duplicati (alcune normative base sono già nel mapping specifico)
    seen = set()
    result = []
    for n in _ALWAYS_APPLICABLE + specific:
        if n not in seen:
            seen.add(n)
            result.append(n)
    return result
