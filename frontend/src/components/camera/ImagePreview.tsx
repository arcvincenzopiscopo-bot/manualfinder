import { useState } from 'react'

interface Props {
  previewUrl: string
  brand?: string | null
  model?: string | null
  onRetake: () => void
  onAnalyze: () => void
  isRunning: boolean
}

export function ImagePreview({ previewUrl, brand, model, onRetake, onAnalyze, isRunning }: Props) {
  return (
    <div style={{ padding: '16px' }}>
      <img
        src={previewUrl}
        alt="Anteprima targa"
        style={{
          width: '100%',
          maxHeight: 300,
          objectFit: 'contain',
          borderRadius: 12,
          background: '#f1f5f9',
        }}
      />

      <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
        <button
          onClick={onRetake}
          disabled={isRunning}
          style={{
            flex: 1,
            padding: '12px',
            borderRadius: 8,
            border: '1px solid #cbd5e1',
            background: '#fff',
            fontWeight: 600,
            cursor: 'pointer',
            color: '#475569',
          }}
        >
          Riprendi
        </button>
        <button
          onClick={onAnalyze}
          disabled={isRunning}
          style={{
            flex: 2,
            padding: '12px',
            borderRadius: 8,
            border: 'none',
            background: isRunning ? '#93c5fd' : '#1e40af',
            color: '#fff',
            fontWeight: 700,
            fontSize: 16,
            cursor: isRunning ? 'not-allowed' : 'pointer',
          }}
        >
          {isRunning ? 'Lettura targa...' : 'Leggi targa →'}
        </button>
      </div>

      <p style={{ marginTop: 10, fontSize: 12, color: '#94a3b8', textAlign: 'center' }}>
        Dopo la lettura potrai verificare e correggere marca e modello
      </p>
    </div>
  )
}
