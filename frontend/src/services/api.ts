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

export async function searchManual(brand: string, model: string, lang = 'it'): Promise<ManualSearchResult[]> {
  const params = new URLSearchParams({ brand, model, lang })
  const response = await fetch(`${BASE_URL}/manual/search?${params}`)
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return response.json()
}

export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${BASE_URL}/health`, { signal: AbortSignal.timeout(5000) })
    return response.ok
  } catch {
    return false
  }
}
