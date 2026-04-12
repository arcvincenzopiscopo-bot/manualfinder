export interface PlateOCRResult {
  brand: string | null
  model: string | null
  machine_type: string | null  // Tipo di macchina (es: "piattaforma aerea", "escavatore")
  machine_type_id: number | null  // ID nel catalogo machine_types (null = non nel catalogo)
  serial_number: string | null
  year: string | null
  confidence: 'high' | 'medium' | 'low'
  raw_text: string
  notes: string | null
  // Nuovi campi per routing ante-CE
  ce_marking: 'presente' | 'assente' | 'non_visibile' | null
  machine_category: 'cantiere' | 'industriale' | 'agricola' | 'sollevamento' | 'altro' | null
  qr_url: string | null
  qr_urls: string[]
  // Flag incertezza OCR: True se meno di 2/4 varianti multishot concordano sul campo
  serial_number_uncertain?: boolean
  year_uncertain?: boolean
  model_uncertain?: boolean
}

// Metadati fonte strategia A–F — popolati da source_manager nel backend
export interface SourceMetadata {
  strategy: 'A' | 'B' | 'C' | 'D' | 'E' | 'F'
  badge_label: string
  badge_color: string
  disclaimer: string
  affidabilita: number       // 0-100
  fonte_tipo: string
  inail_is_local?: boolean   // true = PDF INAIL dalla cartella locale (prevalidato admin)
  rag_has_inail?: boolean    // true = corpus RAG contiene quaderni INAIL indicizzati per questo tipo
}

export interface MachineType {
  id: number
  name: string
  requires_patentino: boolean
  requires_verifiche: boolean
  inail_search_hint: string | null
  usage_count: number
  vita_utile_anni: number | null
}

export interface ChecklistItem {
  testo: string
  livello: 1 | 2      // 1 = blocco immediato; 2 = prescrizione
  norma?: string      // es. "All. V D.Lgs 81/08 punto 6.1"
  prescrizione_precompilata?: string  // testo verbale ispettivo pronto per copia
}

export interface DocumentoRichiesto {
  documento: string      // "Manuale d'uso e manutenzione in italiano"
  smart_hint: string     // "Verificare che il numero di serie coincida con l'etichetta"
  validity_requirements?: string    // Elementi obbligatori per la validità del documento
  irregularity_indicators?: string  // Segnali di non conformità o non aggiornamento
}

export interface ManualSearchResult {
  url: string
  title: string
  source_type: 'inail' | 'manufacturer' | 'web'
  language: string
  is_pdf: boolean
  relevance_score: number
}

// Singola voce di una sezione sicurezza con attribuzione della fonte
export interface SafetyItem {
  testo: string
  fonte: string  // "INAIL" | "Produttore (Brand)" | "AI"
  // Classificazione rischio ISO 12100 (presente solo su rischi_principali)
  probabilita?: 'P1' | 'P2' | 'P3'  // P1=raro, P2=possibile, P3=probabile
  gravita?: 'S1' | 'S2' | 'S3'      // S1=lieve, S2=grave, S3=mortale/invalidante
  // DPI: destinatario del dispositivo di protezione individuale
  recipient?: 'operatore' | 'personale_a_terra' | 'entrambi'
  // Procedure emergenza: tier della fonte e disclaimer AI
  source_tier?: 'manuale' | 'inail' | 'ai'
  ai_disclaimer?: boolean
}

// Dispositivo di sicurezza installato sulla macchina dal costruttore
export interface DispositivoSicurezza {
  nome: string
  tipo: 'interblocco' | 'sensore' | 'riparo' | 'arresto_emergenza' | 'segnalazione' | 'limitatore' | string
  descrizione: string
  verifica_ispezione: string
  fonte: string  // "INAIL" | "Produttore (Brand)" | "AI"
}

export interface AllegatoVRequisito {
  id: string
  titolo: string
  testo: string
  criticita: 'alta' | 'media' | 'bassa'
  verifica: string
}

export interface TabellaCEAnte {
  aspetto: string
  allegato_v: string
  dir_ce: string
  gap: string
}

export interface BozzaPrescrizione {
  req_id: string
  titolo: string
  criticita: 'alta' | 'media' | 'bassa'
  prescrizione: string
}

export interface SafetyCard {
  brand: string
  model: string
  rischi_principali: SafetyItem[]
  dispositivi_protezione: SafetyItem[]
  raccomandazioni_produttore: SafetyItem[]
  rischi_residui: SafetyItem[]
  dispositivi_sicurezza: DispositivoSicurezza[]
  fonte_manuale: string | null
  fonte_inail: string | null
  fonte_tipo: 'pdf' | 'fallback_ai' | 'inail' | 'inail+produttore' | null
  note: string | null
  generated_at: string
  language: string
  // Etichette fonte per sezione ("INAIL" | "Produttore (Brand)" | "AI")
  fonte_rischi: string | null
  fonte_protezione: string | null
  fonte_raccomandazioni: string | null
  fonte_residui: string | null
  checklist: (ChecklistItem | string)[]
  // Nuovi campi ispettivi
  abilitazione_operatore: string | null        // Patentino/formazione obbligatoria (Accordo S-R 2012)
  documenti_da_richiedere: (DocumentoRichiesto | string)[]  // Documenti da richiedere al datore di lavoro
  verifiche_periodiche: string | null          // Obbligo verifica periodica INAIL ex Art. 71 c.11
  procedure_emergenza: SafetyItem[]            // Procedure specifiche del modello [{testo, fonte}]
  limiti_operativi: SafetyItem[]               // Portate, pressioni, pendenze con valori numerici
  pittogrammi_sicurezza: string[]              // Pittogrammi obbligatori da verificare sulla macchina
  confidence_ai: 'high' | 'medium' | 'low' | null  // Solo in modalità fallback AI
  normative_applicabili: string[]                   // Normative vigenti per il tipo macchina
  safety_alerts: Array<{
    title: string
    risk_level: 'serious' | 'medium' | 'low' | 'unknown'
    description: string
    measures: string
    reference: string
    date: string
    url: string
  }>
  // Allegato V / ante-CE
  is_allegato_v?: boolean
  machine_year?: string | null
  machine_type?: string | null
  allegato_v_category?: string | null
  allegato_v_label?: string | null
  allegato_v_requisiti?: AllegatoVRequisito[]
  tabella_ce_ante?: TabellaCEAnte[]
  gap_ce_ante?: string | null
  bozze_prescrizioni?: BozzaPrescrizione[]
  // Miglioramenti scheda
  attrezzature_intercambiabili?: string | null
  vita_utile_anni?: number | null
  focus_rischi_categoria?: string | null
  categoria_inail?: string | null
  // Metadati fonte strategia A–F
  source_metadata?: SourceMetadata | null
  // ID nel catalogo machine_types (disponibile dopo la pipeline)
  machine_type_id?: number | null
}

// Contestualizzazione sopralluogo (persistita in localStorage)
export type WorkplaceCategory = 'cantiere' | 'industria' | 'logistica' | 'altro'
export type WorkplacePhase = 'scavo' | 'fondazioni' | 'strutture' | 'finiture' | 'demolizione' | 'altro'

export interface WorkplaceContext {
  category: WorkplaceCategory
  phase?: WorkplacePhase  // solo se category === 'cantiere'
}

export interface SSEEvent {
  step: 'ocr' | 'search' | 'download' | 'analysis' | 'complete' | 'error'
  status: 'started' | 'completed' | 'failed'
  data: Record<string, unknown>
  progress: number
  message: string
}

export type PipelineStep = {
  id: SSEEvent['step']
  label: string
  status: 'idle' | 'running' | 'done' | 'error'
  message: string
}

export interface PipelineState {
  steps: PipelineStep[]
  progress: number
  ocr: PlateOCRResult | null
  searchResults: ManualSearchResult[]
  safetyCard: SafetyCard | null
  error: string | null
  isRunning: boolean
  isDone: boolean
}

export interface CachedResult {
  safetyCard: SafetyCard
  ocr: PlateOCRResult | null
  timestamp: number
}
