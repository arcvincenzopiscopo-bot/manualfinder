from pydantic import BaseModel, field_validator
from typing import Optional, List, Any
from datetime import datetime


class PlateOCRResult(BaseModel):
    brand: Optional[str] = None
    model: Optional[str] = None
    machine_type: Optional[str] = None  # Tipo di macchina (es: "piattaforma aerea", "escavatore")
    serial_number: Optional[str] = None
    year: Optional[str] = None

    machine_type_id: Optional[int] = None  # ID nel catalogo machine_types (None = tipo non nel catalogo)
    confidence: str = "low"       # "high" | "medium" | "low"
    raw_text: str = ""
    norme: List[str] = []          # Norme armonizzate estratte dalla targa (EN, UNI, ISO)
    qr_url: Optional[str] = None   # Primo URL QR (backward compat)
    qr_urls: List[str] = []        # Tutti gli URL decodificati da QR Code sulla targa
    # Nuovi campi per determinazione ante-CE e routing ricerca
    ce_marking: Optional[str] = None      # "presente" | "assente" | "non_visibile"
    machine_category: Optional[str] = None # "cantiere" | "industriale" | "agricola" | "sollevamento" | "altro"
    # Flag di incertezza OCR: True se meno di 2/4 varianti multishot concordano sul campo
    serial_number_uncertain: bool = False
    year_uncertain: bool = False
    model_uncertain: bool = False

    @field_validator("brand", "model", "machine_type", "serial_number", "year", mode="before")
    @classmethod
    def coerce_to_str(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, list):
            return "\n".join(str(item) for item in v)
        return str(v)

    @field_validator("raw_text", mode="before")
    @classmethod
    def coerce_raw_text(cls, v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, list):
            return "\n".join(str(item) for item in v)
        return str(v)
    notes: Optional[str] = None


class ManualSearchResult(BaseModel):
    url: str
    title: str
    source_type: str              # "inail" | "manufacturer" | "web" | "datasheet"
    language: str = "unknown"     # "it" | "en" | "de" | "unknown"
    is_pdf: bool = False
    relevance_score: int = 0      # 0-100, per ordinamento
    snippet: Optional[str] = None  # estratto testo dal risultato di ricerca


class SafetyCard(BaseModel):
    brand: str
    model: str
    # Ogni voce è un dict {testo: str, fonte: str}
    # fonte può essere "INAIL" | "Produttore (Brand)" | "AI"
    rischi_principali: List[dict]
    dispositivi_protezione: List[dict]
    raccomandazioni_produttore: List[dict]
    rischi_residui: List[dict]
    # Dispositivi di sicurezza installati sulla macchina dal costruttore (interblocchi, sensori, ripari...)
    # Ogni voce: {nome, tipo, descrizione, verifica_ispezione, fonte}
    dispositivi_sicurezza: List[dict] = []
    fonte_manuale: Optional[str] = None       # URL manuale produttore
    fonte_inail: Optional[str] = None         # URL scheda INAIL (dual-source)
    fonte_tipo: Optional[str] = None          # "pdf" | "fallback_ai" | "inail" | "inail+produttore"
    note: Optional[str] = None
    generated_at: str = ""
    language: str = "it"
    # Etichette fonte per sezione — mostrate nell'UI come riepilogo nel titolo sezione
    fonte_rischi: Optional[str] = None
    fonte_protezione: Optional[str] = None
    fonte_raccomandazioni: Optional[str] = None
    fonte_residui: Optional[str] = None
    # Checklist ispettiva — voci spuntabili durante il sopralluogo
    # Ogni voce: {testo, livello (1|2), norma?} oppure stringa plain (compat. retroattiva)
    checklist: List[Any] = []
    # Nuovi campi ispettivi
    abilitazione_operatore: Optional[str] = None     # Patentino/formazione obbligatoria (Accordo S-R 2012)
    documenti_da_richiedere: List[Any] = []          # [{documento, smart_hint}] — o stringa (compat. retroattiva)
    verifiche_periodiche: Optional[str] = None       # Obbligo verifica periodica INAIL ex Art. 71 c.11
    procedure_emergenza: List[dict] = []             # [{testo, fonte}] — procedure specifiche del modello
    limiti_operativi: List[dict] = []                # [{testo, fonte}] — portate, pressioni, pendenze
    pittogrammi_sicurezza: List[str] = []            # Pittogrammi obbligatori da verificare sulla macchina
    confidence_ai: Optional[str] = None             # "high"|"medium"|"low" — solo in fallback mode
    normative_applicabili: List[str] = []           # Normative vigenti per il tipo macchina (ISO, EN, D.Lgs.)
    # Avvisi Safety Gate EU — alert per richiami o difetti noti
    safety_alerts: List[dict] = []
    # Allegato V / ante-CE — campi aggiuntivi per macchine pre-1996
    is_allegato_v: bool = False
    machine_year: Optional[str] = None
    machine_type: Optional[str] = None
    allegato_v_category: Optional[str] = None   # chiave categoria (es. "piattaforme_aeree")
    allegato_v_label: Optional[str] = None      # etichetta leggibile
    allegato_v_requisiti: List[dict] = []        # requisiti filtrati per categoria
    tabella_ce_ante: List[dict] = []             # confronto Allegato V vs Direttiva CE
    gap_ce_ante: Optional[str] = None           # gap analysis: cosa mancherebbe se fosse nuova
    bozze_prescrizioni: List[dict] = []         # bozze prescrizione per requisiti Allegato V non conformi
    # Nuovi campi miglioramento scheda
    attrezzature_intercambiabili: Optional[str] = None  # testo AI su attrezzature intercambiabili
    vita_utile_anni: Optional[int] = None               # vita utile stimata dalla tabella machine_types
    focus_rischi_categoria: Optional[str] = None        # testo hazard intelligence da machine_type_hazard
    categoria_inail: Optional[str] = None               # categoria "agente materiale" INAIL
    # Metadati fonte: strategia A-F, badge, affidabilità — popolati da source_manager
    source_metadata: Optional[dict] = None

    def __init__(self, **data):
        if not data.get("generated_at"):
            data["generated_at"] = datetime.utcnow().isoformat() + "Z"
        super().__init__(**data)


class SSEEvent(BaseModel):
    step: str      # "ocr" | "search" | "download" | "analysis" | "complete" | "error"
    status: str    # "started" | "completed" | "failed"
    data: dict = {}
    progress: int = 0   # 0-100
    message: str = ""   # Messaggio in italiano per l'UI
