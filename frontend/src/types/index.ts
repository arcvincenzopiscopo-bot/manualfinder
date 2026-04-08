export interface PlateOCRResult {
  brand: string | null
  model: string | null
  machine_type: string | null  // Tipo di macchina (es: "piattaforma aerea", "escavatore")
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
  checklist: string[]
  // Nuovi campi ispettivi
  abilitazione_operatore: string | null        // Patentino/formazione obbligatoria (Accordo S-R 2012)
  documenti_da_richiedere: string[]            // Documenti da richiedere al datore di lavoro
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
