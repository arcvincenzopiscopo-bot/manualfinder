import { useRef, useState } from 'react'
import { useImagePreprocess } from '../../hooks/useImagePreprocess'

interface Props {
  onImageReady: (base64: string, previewUrl: string) => void
}

export function CameraCapture({ onImageReady }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
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
  }

  return (
    <div style={{ padding: '24px 16px', textAlign: 'center' }}>
      <div
        onClick={() => inputRef.current?.click()}
        style={{
          border: '2px dashed #93c5fd',
          borderRadius: 16,
          padding: '40px 20px',
          cursor: 'pointer',
          background: '#eff6ff',
          transition: 'background 0.2s',
        }}
      >
        <div style={{ fontSize: 48, marginBottom: 12 }}>📷</div>
        <p style={{ fontSize: 18, fontWeight: 700, color: '#1e40af', margin: '0 0 6px' }}>
          Fotografa la targa
        </p>
        <p style={{ fontSize: 14, color: '#64748b', margin: 0 }}>
          Tocca per aprire la fotocamera o caricare un'immagine
        </p>
        {loading && (
          <p style={{ marginTop: 12, color: '#1e40af', fontSize: 14 }}>
            Elaborazione immagine...
          </p>
        )}
      </div>

      {error && (
        <p style={{ color: '#dc2626', marginTop: 8, fontSize: 14 }}>{error}</p>
      )}

      {/* Input nascosto con capture="environment" per aprire camera posteriore su mobile */}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleChange}
        style={{ display: 'none' }}
      />

      <p style={{ marginTop: 12, fontSize: 12, color: '#94a3b8' }}>
        Suggerimento: buona illuminazione e targa centrata nell'inquadratura
      </p>
    </div>
  )
}
