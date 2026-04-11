import { useState, useEffect, useRef } from 'react'
import { usePipeline } from './hooks/usePipeline'
import { useOfflineCache } from './hooks/useOfflineCache'
import { ocrPlate, checkHealth } from './services/api'
import { CameraCapture } from './components/camera/CameraCapture'
import { ImagePreview } from './components/camera/ImagePreview'
import { OcrConfirmForm } from './components/camera/OcrConfirmForm'
import { PipelineProgress } from './components/pipeline/PipelineProgress'
import { SafetyCard } from './components/results/SafetyCard'
import { ErrorBanner } from './components/ui/ErrorBanner'
import { OfflineBadge } from './components/ui/OfflineBadge'
import { UploadManualModal } from './components/upload/UploadManualModal'
import { AdminPanel } from './components/admin/AdminPanel'
import { WorkplaceContextDialog, loadWorkplaceContext, saveWorkplaceContext, clearWorkplaceContext, workplaceContextLabel } from './components/ui/WorkplaceContextDialog'
import type { PlateOCRResult, WorkplaceContext } from './types'

type AppState = 'idle' | 'preview' | 'ocr_loading' | 'confirming' | 'running' | 'done' | 'error'

/**
 * Attende che il backend risponda all'health check con backoff esponenziale.
 * Intervalli: 2s, 4s, 8s, 16s, 30s (cappato), max ~2 minuti totali.
 */
function useBackendReady() {
  const [ready, setReady] = useState<boolean | null>(null) // null = checking
  const attempts = useRef(0)

  useEffect(() => {
    let cancelled = false
    const MAX_ATTEMPTS = 10
    const BASE_DELAY_MS = 2000
    const MAX_DELAY_MS = 30_000

    async function poll() {
      const ok = await checkHealth()
      if (cancelled) return
      if (ok) {
        setReady(true)
        return
      }
      attempts.current += 1
      if (attempts.current >= MAX_ATTEMPTS) {
        setReady(false) // timeout — lascia comunque procedere
        return
      }
      const delay = Math.min(BASE_DELAY_MS * 2 ** (attempts.current - 1), MAX_DELAY_MS)
      setTimeout(poll, delay)
    }

    poll()
    return () => { cancelled = true }
  }, [])

  return ready
}

export default function App() {
  const { state: pipeline, run, reset } = usePipeline()
  const { cached, isOnline, save } = useOfflineCache()
  const backendReady = useBackendReady()

  const [isAdmin, setIsAdmin] = useState(window.location.hash === '#admin')
  useEffect(() => {
    const handler = () => setIsAdmin(window.location.hash === '#admin')
    window.addEventListener('hashchange', handler)
    return () => window.removeEventListener('hashchange', handler)
  }, [])

  if (isAdmin) return <AdminPanel />

  const [appState, setAppState] = useState<AppState>('idle')
  const [showUpload, setShowUpload] = useState(false)
  const [imageBase64, setImageBase64] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [ocrResult, setOcrResult] = useState<(PlateOCRResult & { brightness_warning?: string }) | null>(null)
  const [ocrError, setOcrError] = useState<string | null>(null)
  const [workplaceCtx, setWorkplaceCtx] = useState<WorkplaceContext | null>(() => loadWorkplaceContext())
  const [showCtxDialog, setShowCtxDialog] = useState(false)
  // Callback da eseguire dopo che il contesto è confermato
  const pendingConfirmRef = useRef<(() => void) | null>(null)

  // Sincronizza lo stato app con quello della pipeline
  useEffect(() => {
    if (appState !== 'running') return
    if (pipeline.isDone) setAppState('done')
    else if (pipeline.error) setAppState('error')
  }, [pipeline.isDone, pipeline.error, appState])

  // Salva in cache quando la pipeline completa
  useEffect(() => {
    if (pipeline.isDone && pipeline.safetyCard) {
      save(pipeline.safetyCard, ocrResult)
    }
  }, [pipeline.isDone, pipeline.safetyCard])

  const handleImageReady = (base64: string, preview: string) => {
    setImageBase64(base64)
    setPreviewUrl(preview)
    setOcrResult(null)
    setOcrError(null)
    setAppState('preview')
  }

  const handleStartOcr = async () => {
    if (!imageBase64) return
    setAppState('ocr_loading')
    setOcrError(null)
    try {
      const result = await ocrPlate(imageBase64)
      setOcrResult(result)
      setAppState('confirming')
    } catch (err) {
      setOcrError((err as Error).message)
      setAppState('error')
    }
  }

  const handleConfirm = (brand: string, model: string, serial: string, year: string, machineType: string, machineTypeId: number | null = null) => {
    if (!imageBase64) return
    if (ocrResult) {
      setOcrResult({ ...ocrResult, brand, model, serial_number: serial || null, year: year || null, machine_type: machineType || null, machine_type_id: machineTypeId })
    }

    const doRun = (ctx: WorkplaceContext | null) => {
      setAppState('running')
      run(imageBase64, brand, model, machineType, ocrResult?.qr_urls ?? [], machineTypeId, serial || null, year || null, ctx ?? undefined)
    }

    if (workplaceCtx) {
      doRun(workplaceCtx)
    } else {
      // Mostra dialog contesto — dopo conferma esegue il run
      pendingConfirmRef.current = () => doRun(loadWorkplaceContext())
      setShowCtxDialog(true)
    }
  }

  const handleCtxConfirm = (ctx: WorkplaceContext) => {
    setWorkplaceCtx(ctx)
    setShowCtxDialog(false)
    pendingConfirmRef.current?.()
    pendingConfirmRef.current = null
  }

  const handleCtxSkip = () => {
    setShowCtxDialog(false)
    pendingConfirmRef.current?.()
    pendingConfirmRef.current = null
  }

  const handleChangeCtx = () => {
    clearWorkplaceContext()
    setWorkplaceCtx(null)
    setShowCtxDialog(true)
    pendingConfirmRef.current = null
  }

  const handleNewSearch = () => {
    reset()
    setAppState('idle')
    setImageBase64(null)
    setOcrResult(null)
    setOcrError(null)
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setPreviewUrl(null)
  }

  return (
    <div style={{
      maxWidth: 480,
      margin: '0 auto',
      minHeight: '100dvh',
      background: '#fff',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    }}>
      <OfflineBadge isOnline={isOnline} />

      {/* Header */}
      <header style={{
        padding: '16px',
        borderBottom: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        background: '#fff',
        position: 'sticky',
        top: 0,
        zIndex: 10,
      }}>
        <div style={{
          width: 36, height: 36,
          background: '#1e40af', borderRadius: 8,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 20,
        }}>🔍</div>
        <div>
          <h1 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: '#1e293b' }}>ManualFinder</h1>
          <p style={{ margin: 0, fontSize: 12, color: '#64748b' }}>Sicurezza macchinari da cantiere</p>
        </div>
        {/* Indicatore stato + contesto + Upload */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          {appState !== 'idle' && appState !== 'done' && (
            <StepIndicator state={appState} />
          )}
          {/* Badge contesto sopralluogo */}
          {workplaceCtx && (
            <button
              onClick={handleChangeCtx}
              title="Cambia contesto sopralluogo"
              style={{
                background: '#eff6ff',
                border: '1px solid #bfdbfe',
                borderRadius: 20,
                padding: '3px 8px',
                fontSize: 11,
                fontWeight: 700,
                color: '#1e40af',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                maxWidth: 120,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {workplaceContextLabel(workplaceCtx)}
            </button>
          )}
          <button
            onClick={() => setShowUpload(true)}
            title="Carica manuale PDF"
            style={{ background: 'none', border: 'none', fontSize: 22, cursor: 'pointer', padding: '4px 6px', lineHeight: 1 }}
          >
            📤
          </button>
        </div>
      </header>

      {/* Banner backend in avvio (Render cold start) */}
      {backendReady === null && (
        <div style={{
          background: '#fffbeb',
          borderBottom: '1px solid #fde68a',
          padding: '10px 16px',
          fontSize: 13,
          color: '#92400e',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}>
          <span style={{ fontSize: 16 }}>⏳</span>
          <span>Backend in avvio, attendi qualche secondo prima di scattare la foto…</span>
        </div>
      )}

      {showUpload && <UploadManualModal onClose={() => setShowUpload(false)} />}

      {showCtxDialog && (
        <WorkplaceContextDialog
          onConfirm={handleCtxConfirm}
          onSkip={pendingConfirmRef.current ? handleCtxSkip : undefined}
        />
      )}

      <main>
        {/* IDLE */}
        {appState === 'idle' && (
          <>
            <CameraCapture onImageReady={handleImageReady} disabled={backendReady === null} />
            {!isOnline && cached && (
              <div style={{ padding: '0 16px 16px' }}>
                <p style={{ fontSize: 13, color: '#64748b', fontWeight: 600 }}>ULTIMA ANALISI SALVATA</p>
                <SafetyCard card={cached.safetyCard} ocr={cached.ocr} onNewSearch={() => {}} />
              </div>
            )}
          </>
        )}

        {/* PREVIEW: anteprima immagine prima di avviare OCR */}
        {appState === 'preview' && previewUrl && (
          <ImagePreview
            previewUrl={previewUrl}
            onRetake={handleNewSearch}
            onAnalyze={handleStartOcr}
            isRunning={false}
          />
        )}

        {/* OCR LOADING */}
        {appState === 'ocr_loading' && previewUrl && (
          <div>
            <img
              src={previewUrl}
              alt="Targa in analisi"
              style={{ width: '100%', maxHeight: 220, objectFit: 'contain', background: '#f1f5f9' }}
            />
            <div style={{ padding: 24, textAlign: 'center' }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>🔍</div>
              <p style={{ fontWeight: 700, fontSize: 16, color: '#1e40af', margin: '0 0 6px' }}>
                Lettura targa in corso...
              </p>
              <p style={{ fontSize: 13, color: '#64748b', margin: 0 }}>
                Estrazione marca e modello dall'immagine
              </p>
            </div>
          </div>
        )}

        {/* CONFIRMING: mostra form modificabile con risultati OCR */}
        {appState === 'confirming' && ocrResult && previewUrl && (
          <div>
            <img
              src={previewUrl}
              alt="Targa"
              style={{ width: '100%', maxHeight: 180, objectFit: 'contain', background: '#f1f5f9' }}
            />
            <OcrConfirmForm
              ocr={ocrResult}
              onConfirm={handleConfirm}
              onRetake={handleNewSearch}
            />
          </div>
        )}

        {/* RUNNING: pipeline search/download/analisi */}
        {appState === 'running' && (
          <>
            {previewUrl && (
              <img
                src={previewUrl}
                alt="Targa in analisi"
                style={{ width: '100%', maxHeight: 140, objectFit: 'contain', background: '#f1f5f9' }}
              />
            )}
            {/* Mini intestazione macchina confermata */}
            {ocrResult && (
              <div style={{ padding: '10px 16px', background: '#eff6ff', borderBottom: '1px solid #bfdbfe' }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: '#1e40af' }}>
                  {ocrResult.brand} {ocrResult.model}
                </span>
              </div>
            )}
            <PipelineProgress steps={pipeline.steps} progress={pipeline.progress} />
          </>
        )}

        {/* DONE */}
        {appState === 'done' && pipeline.safetyCard && (
          <SafetyCard card={pipeline.safetyCard} ocr={ocrResult} onNewSearch={handleNewSearch} />
        )}

        {/* ERROR */}
        {appState === 'error' && (
          <>
            {pipeline.steps.some(s => s.status !== 'idle') && (
              <PipelineProgress steps={pipeline.steps} progress={pipeline.progress} />
            )}
            <ErrorBanner
              message={ocrError ?? pipeline.error ?? 'Errore sconosciuto'}
              onRetry={ocrError ? handleStartOcr : () => { if (imageBase64 && ocrResult) handleConfirm(ocrResult.brand ?? '', ocrResult.model ?? '', ocrResult.serial_number ?? '', ocrResult.year ?? '', ocrResult.machine_type ?? '', ocrResult.machine_type_id ?? null) }}
            />
            <div style={{ padding: '0 16px 16px' }}>
              <button
                onClick={handleNewSearch}
                style={{ width: '100%', padding: '12px', background: '#fff', color: '#475569', border: '1px solid #cbd5e1', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}
              >
                Nuova analisi
              </button>
            </div>
          </>
        )}
      </main>
    </div>
  )
}

function StepIndicator({ state }: { state: AppState }) {
  const labels: Partial<Record<AppState, string>> = {
    ocr_loading: '1/3 OCR',
    confirming:  '1/3 Conferma',
    running:     '2/3 Analisi',
  }
  const label = labels[state]
  if (!label) return null
  return (
    <span style={{
      fontSize: 11, fontWeight: 700, color: '#2563eb',
      background: '#dbeafe', padding: '4px 10px', borderRadius: 20,
    }}>
      {label}
    </span>
  )
}
