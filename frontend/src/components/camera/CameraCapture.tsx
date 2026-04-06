import { useRef, useState } from 'react'
import { useImagePreprocess } from '../../hooks/useImagePreprocess'

interface Props {
  onImageReady: (base64: string, previewUrl: string) => void
  disabled?: boolean
}

export function CameraCapture({ onImageReady, disabled = false }: Props) {
  const cameraInputRef = useRef<HTMLInputElement>(null)
  const galleryInputRef = useRef<HTMLInputElement>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { processImage } = useImagePreprocess()

  const handleFile = async (file: File) => {
    if (!file.type.startsWith('image/')) {
      setError('Seleziona un file immagine valido')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const base64 = await processImage(file)
      const previewUrl = URL.createObjectURL(file)
      onImageReady(base64, previewUrl)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    // reset per permettere di selezionare lo stesso file di nuovo
    e.target.value = ''
  }

  return (
    <div style={{ padding: '24px 16px', textAlign: 'center' }}>
      <div style={{ fontSize: 48, marginBottom: 12 }}>📷</div>
      <p style={{ fontSize: 18, fontWeight: 700, color: '#1e40af', margin: '0 0 16px' }}>
        Carica la targa
      </p>

      <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
        {/* Pulsante fotocamera — apre direttamente la camera posteriore */}
        <button
          onClick={() => cameraInputRef.current?.click()}
          disabled={loading || disabled}
          style={{
            flex: 1,
            maxWidth: 180,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 8,
            border: '2px solid #93c5fd',
            borderRadius: 16,
            padding: '20px 12px',
            cursor: (loading || disabled) ? 'not-allowed' : 'pointer',
            background: disabled ? '#f1f5f9' : '#eff6ff',
            color: disabled ? '#94a3b8' : '#1e40af',
            fontWeight: 600,
            fontSize: 15,
            transition: 'background 0.2s',
            opacity: disabled ? 0.6 : 1,
          }}
        >
          <span style={{ fontSize: 32 }}>📷</span>
          Fotocamera
        </button>

        {/* Pulsante raccolta — apre la galleria foto senza capture */}
        <button
          onClick={() => galleryInputRef.current?.click()}
          disabled={loading || disabled}
          style={{
            flex: 1,
            maxWidth: 180,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 8,
            border: '2px solid #a5b4fc',
            borderRadius: 16,
            padding: '20px 12px',
            cursor: (loading || disabled) ? 'not-allowed' : 'pointer',
            background: disabled ? '#f1f5f9' : '#eef2ff',
            color: disabled ? '#94a3b8' : '#3730a3',
            fontWeight: 600,
            fontSize: 15,
            transition: 'background 0.2s',
            opacity: disabled ? 0.6 : 1,
          }}
        >
          <span style={{ fontSize: 32 }}>🖼️</span>
          Raccolta
        </button>
      </div>

      {loading && (
        <p style={{ marginTop: 16, color: '#1e40af', fontSize: 14 }}>
          Elaborazione immagine...
        </p>
      )}

      {error && (
        <p style={{ color: '#dc2626', marginTop: 8, fontSize: 14 }}>{error}</p>
      )}

      {/* Input fotocamera — capture="environment" forza la camera posteriore */}
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleChange}
        style={{ display: 'none' }}
      />

      {/* Input galleria — nessun capture, apre il selettore file/foto */}
      <input
        ref={galleryInputRef}
        type="file"
        accept="image/*"
        onChange={handleChange}
        style={{ display: 'none' }}
      />

      <p style={{ marginTop: 16, fontSize: 12, color: '#94a3b8' }}>
        Suggerimento: buona illuminazione e targa centrata nell'inquadratura
      </p>
    </div>
  )
}
