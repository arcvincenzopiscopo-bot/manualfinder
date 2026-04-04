import { useState, useEffect } from 'react'
import { usePipeline } from './hooks/usePipeline'
import { useOfflineCache } from './hooks/useOfflineCache'
import { ocrPlate } from './services/api'
import { CameraCapture } from './components/camera/CameraCapture'
import { ImagePreview } from './components/camera/ImagePreview'
import { OcrConfirmForm } from './components/camera/OcrConfirmForm'
import { PipelineProgress } from './components/pipeline/PipelineProgress'
import { SafetyCard } from './components/results/SafetyCard'
import { ErrorBanner } from './components/ui/ErrorBanner'
import { OfflineBadge } from './components/ui/OfflineBadge'
import type { PlateOCRResult } from './types'

type AppState = 'idle' | 'preview' | 'ocr_loading' | 'confirming' | 'running' | 'done' | 'error'

export default function App() {
  const { state: pipeline, run, reset } = usePipeline()
  const { cached, isOnline, save } = useOfflineCache()

  const [appState, setAppState] = useState<AppState>('idle')
  const [imageBase64, setImageBase64] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [ocrResult, setOcrResult] = useState<(PlateOCRResult & { brightness_warning?: string }) | null>(null)
  const [ocrError, setOcrError] = useState<string | null>(null)

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

  const handleConfirm = (brand: string, model: string, serial: string, year: string, machineType: string) => {
    if (!imageBase64) return
    // Aggiorna ocrResult con i valori corretti dall'utente
    if (ocrResult) {
      setOcrResult({ ...ocrResult, brand, model, serial_number: serial || null, year: year || null, machine_type: machineType || null })
    }
    setAppState('running')
    run(imageBase64, brand, model, machineType)
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
        {/* Indicatore stato */}
        {appState !== 'idle' && appState !== 'done' && (
          <div style={{ marginLeft: 'auto' }}>
            <StepIndicator state={appState} />
          </div>
        )}
      </header>

      <main>
        {/* IDLE */}
        {appState === 'idle' && (
          <>
            <CameraCapture onImageReady={handleImageReady} />
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
              onRetry={ocrError ? handleStartOcr : () => { if (imageBase64 && ocrResult) handleConfirm(ocrResult.brand ?? '', ocrResult.model ?? '', ocrResult.serial_number ?? '', ocrResult.year ?? '', ocrResult.machine_type ?? '') }}
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
