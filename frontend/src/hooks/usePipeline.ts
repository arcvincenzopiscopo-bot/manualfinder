import { useState, useRef, useCallback } from 'react'
import { analyzeFullSSE } from '../services/api'
import type { PipelineState, PipelineStep, SSEEvent, ManualSearchResult, SafetyCard } from '../types'

// I 3 step della pipeline (OCR è separato)
const INITIAL_STEPS: PipelineStep[] = [
  { id: 'search',   label: 'Ricerca manuale',   status: 'idle', message: '' },
  { id: 'download', label: 'Download PDF',      status: 'idle', message: '' },
  { id: 'analysis', label: 'Analisi sicurezza', status: 'idle', message: '' },
  { id: 'complete', label: 'Completato',        status: 'idle', message: '' },
]

const INITIAL_STATE: PipelineState = {
  steps: INITIAL_STEPS,
  progress: 0,
  ocr: null,
  searchResults: [],
  safetyCard: null,
  error: null,
  isRunning: false,
  isDone: false,
}

export function usePipeline() {
  const [state, setState] = useState<PipelineState>(INITIAL_STATE)
  const abortRef = useRef<AbortController | null>(null)

  const handleEvent = useCallback((event: SSEEvent) => {
    setState(prev => {
      const next = { ...prev, progress: event.progress }

      const stepId = event.step as PipelineStep['id']
      const stepStatus =
        event.status === 'started'   ? 'running' :
        event.status === 'completed' ? 'done'    : 'error'

      next.steps = prev.steps.map(s =>
        s.id === stepId ? { ...s, status: stepStatus, message: event.message } : s
      )

      if (event.step === 'search' && event.status === 'completed') {
        next.searchResults = (event.data.results as ManualSearchResult[]) ?? []
      }

      if (event.step === 'complete' && event.status === 'completed') {
        next.safetyCard = (event.data.safety_card as SafetyCard) ?? null
        next.isDone = true
        next.isRunning = false
      }

      if (event.status === 'failed') {
        next.error = event.message
        next.isRunning = false
      }

      return next
    })
  }, [])

  const run = useCallback(async (imageBase64: string, brand: string, model: string, machineType?: string) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setState({ ...INITIAL_STATE, isRunning: true })

    try {
      await analyzeFullSSE(imageBase64, brand, model, {
        onEvent: handleEvent,
        signal: controller.signal,
        machineType,
      })
    } catch (err) {
      if ((err as Error).name === 'AbortError') return
      setState(prev => ({
        ...prev,
        isRunning: false,
        error: (err as Error).message ?? 'Errore sconosciuto',
      }))
    }
  }, [handleEvent])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    setState(INITIAL_STATE)
  }, [])

  return { state, run, reset }
}
