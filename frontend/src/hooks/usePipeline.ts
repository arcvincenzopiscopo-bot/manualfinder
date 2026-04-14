import { useState, useRef, useCallback } from 'react'
import { analyzeFullSSE } from '../services/api'
import type { PipelineState, PipelineStep, SSEEvent, ManualSearchResult, SafetyCard, WorkplaceContext, DebugEvent } from '../types'

let _debugEventCounter = 0

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
  debugWarnings: [],
  debugEvents: [],
}

export function usePipeline() {
  const [state, setState] = useState<PipelineState>(INITIAL_STATE)
  const abortRef = useRef<AbortController | null>(null)

  const handleEvent = useCallback((event: SSEEvent) => {
    setState(prev => {
      const next = { ...prev, progress: event.progress }

      const stepId = event.step as PipelineStep['id']

      // status='info': aggiorna solo il messaggio, mantieni lo status corrente (es. 'running')
      const isInfoUpdate = event.status === 'info'
      const stepStatus: PipelineStep['status'] =
        event.status === 'started'   ? 'running' :
        event.status === 'completed' ? 'done'    :
        event.status === 'info'      ? 'running' :
        'error'

      next.steps = prev.steps.map(s => {
        if (s.id !== stepId) return s
        // Per eventi 'info' non fare downgrade da 'done' a 'running' (sicurezza)
        const newStatus = isInfoUpdate ? (s.status === 'done' ? 'done' : stepStatus) : stepStatus
        return { ...s, status: newStatus, message: event.message }
      })

      if (event.step === 'debug') {
        const dbgEv: DebugEvent = {
          id: ++_debugEventCounter,
          ts: new Date().toISOString(),
          category: (event.data.category as DebugEvent['category']) ?? 'search',
          level: (event.status as DebugEvent['level']) ?? 'info',
          message: event.message,
          details: event.data,
        }
        next.debugEvents = [...prev.debugEvents, dbgEv]
        return next
      }

      if (event.step === 'search' && event.status === 'completed') {
        next.searchResults = (event.data.results as ManualSearchResult[]) ?? []
        const w = (event.data.debug_warnings as string[]) ?? []
        if (w.length > 0) next.debugWarnings = [...prev.debugWarnings, ...w]
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

  const run = useCallback(async (
    imageBase64: string, brand: string, model: string,
    machineType?: string, qrUrls?: string[], machineTypeId?: number | null,
    serialNumber?: string | null, year?: string | null,
    workplaceContext?: WorkplaceContext,
  ) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setState({ ...INITIAL_STATE, isRunning: true })

    try {
      await analyzeFullSSE(imageBase64, brand, model, {
        onEvent: handleEvent,
        signal: controller.signal,
        machineType,
        machineTypeId,
        qrUrls,
        serialNumber,
        year,
        workplaceContext,
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
