import type { ManualSearchResult, PlateOCRResult, SSEEvent } from '../types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

/** Step 1: solo OCR — ritorna JSON con i dati estratti dalla targa */
export async function ocrPlate(imageBase64: string): Promise<PlateOCRResult & { brightness_warning?: string }> {
  const response = await fetch(`${BASE_URL}/analyze/ocr`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image_base64: imageBase64, image_mime: 'image/jpeg' }),
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(`OCR fallito (HTTP ${response.status}): ${text}`)
  }
  return response.json()
}

/** Step 2: pipeline completa (search → download → analisi) con SSE */
export async function analyzeFullSSE(
  imageBase64: string,
  brand: string,
  model: string,
  options: {
    onEvent: (event: SSEEvent) => void
    signal?: AbortSignal
    preferredLanguage?: string
    machineType?: string
    year?: string | null
    qrUrls?: string[]
  }
): Promise<void> {
  const response = await fetch(`${BASE_URL}/analyze/full`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_base64: imageBase64,
      brand,
      model,
      machine_type: options.machineType || null,
      year: options.year || null,
      preferred_language: options.preferredLanguage ?? 'it',
      qr_urls: options.qrUrls ?? [],
      qr_url: options.qrUrls?.[0] ?? null,
    }),
    signal: options.signal,
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const jsonStr = line.slice(6).trim()
        if (!jsonStr) continue
        try {
          options.onEvent(JSON.parse(jsonStr) as SSEEvent)
        } catch {
          // ignora eventi malformati
        }
      }
    }
  }
}

/** Inferisce il tipo di macchina da brand+modello tramite AI */
export async function inferMachineType(brand: string, model: string, hint?: string): Promise<string | null> {
  const params = new URLSearchParams({ brand, model })
  if (hint) params.set('hint', hint)
  const response = await fetch(`${BASE_URL}/analyze/infer-machine-type?${params}`)
  if (!response.ok) return null
  const data = await response.json()
  return data.machine_type ?? null
}

export async function searchManual(brand: string, model: string, lang = 'it'): Promise<ManualSearchResult[]> {
  const params = new URLSearchParams({ brand, model, lang })
  const response = await fetch(`${BASE_URL}/manual/search?${params}`)
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return response.json()
}

export interface SaveManualPayload {
  search_brand?: string
  search_model?: string
  search_machine_type?: string
  manual_brand: string
  manual_model: string
  manual_machine_type: string
  manual_year?: string
  manual_language?: string
  url: string
  title?: string
  is_pdf?: boolean
  notes?: string
}

export interface UploadManualMeta {
  brand: string
  model: string
  machine_type: string
  manual_year?: string
  manual_language?: string
  is_generic?: boolean
  notes?: string
  force?: boolean
}

export interface UploadManualResult {
  status: 'ok' | 'mismatch'
  filename?: string
  url?: string
  suggestions?: { brand: string; model: string; machine_type: string; reason: string }
}

export async function uploadManual(file: File, meta: UploadManualMeta): Promise<UploadManualResult> {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('brand', meta.brand)
  fd.append('model', meta.model)
  fd.append('machine_type', meta.machine_type)
  if (meta.manual_year) fd.append('manual_year', meta.manual_year)
  fd.append('manual_language', meta.manual_language ?? 'it')
  fd.append('is_generic', String(meta.is_generic ?? false))
  if (meta.notes) fd.append('notes', meta.notes)
  fd.append('force', String(meta.force ?? false))

  // NO 'Content-Type' header — browser lo imposta con il boundary multipart
  const response = await fetch(`${BASE_URL}/manuals/upload`, { method: 'POST', body: fd })
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(data.detail ?? `HTTP ${response.status}`)
  }
  return response.json()
}

export async function saveManual(data: SaveManualPayload): Promise<void> {
  const response = await fetch(`${BASE_URL}/manuals/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(`Errore salvataggio (HTTP ${response.status}): ${text}`)
  }
}

export async function checkUrlSaved(url: string): Promise<boolean> {
  try {
    const params = new URLSearchParams({ url })
    const response = await fetch(`${BASE_URL}/manuals/check-url?${params}`)
    if (!response.ok) return false
    const data = await response.json()
    return data.already_saved === true
  } catch {
    return false
  }
}

export type FeedbackType = 'not_a_manual' | 'wrong_category' | 'useful_other_category'

export async function submitManualFeedback(payload: {
  url: string
  feedback_type: FeedbackType
  brand?: string
  model?: string
  machine_type?: string
  useful_for_type?: string
  notes?: string
}): Promise<void> {
  const fd = new FormData()
  fd.append('url', payload.url)
  fd.append('feedback_type', payload.feedback_type)
  if (payload.brand) fd.append('brand', payload.brand)
  if (payload.model) fd.append('model', payload.model)
  if (payload.machine_type) fd.append('machine_type', payload.machine_type)
  if (payload.useful_for_type) fd.append('useful_for_type', payload.useful_for_type)
  if (payload.notes) fd.append('notes', payload.notes)
  await fetch(`${BASE_URL}/manuals/feedback`, { method: 'POST', body: fd })
}

export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${BASE_URL}/health`, { signal: AbortSignal.timeout(5000) })
    return response.ok
  } catch {
    return false
  }
}
