import { useState } from 'react'

interface ClipboardButtonProps {
  text?: string
  norma?: string
}

export function ClipboardButton({ text, norma }: ClipboardButtonProps) {
  const [showPreview, setShowPreview] = useState(false)
  const [copied, setCopied] = useState(false)
  const disabled = !text

  const handleClick = () => {
    if (disabled) return
    setShowPreview(true)
  }

  const handleConfirmCopy = async () => {
    try {
      await navigator.clipboard.writeText(text!)
      setCopied(true)
      setShowPreview(false)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard API non disponibile (es. HTTP non sicuro)
    }
  }

  return (
    <>
      <button
        onClick={handleClick}
        disabled={disabled}
        title={disabled ? 'Prescrizione non disponibile' : 'Anteprima e copia prescrizione nel verbale'}
        style={{
          background: 'none',
          border: 'none',
          cursor: disabled ? 'default' : 'pointer',
          opacity: disabled ? 0.3 : 1,
          fontSize: 16,
          padding: '2px 4px',
          borderRadius: 4,
          transition: 'opacity 0.2s',
          flexShrink: 0,
        }}
      >
        {copied ? '✅' : '📋'}
      </button>

      {showPreview && (
        <div
          onClick={() => setShowPreview(false)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.45)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: 24,
              maxWidth: 520,
              width: '100%',
              boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
            }}
          >
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#475569', marginBottom: 4, letterSpacing: '0.03em', textTransform: 'uppercase' }}>
                Anteprima prescrizione
              </div>
              {norma && (
                <div style={{ fontSize: 11, color: '#94a3b8', fontFamily: 'monospace', marginBottom: 8 }}>
                  {norma}
                </div>
              )}
              <div style={{
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: 6,
                padding: '12px 14px',
                fontSize: 13,
                fontFamily: 'monospace',
                color: '#1e293b',
                lineHeight: 1.6,
                whiteSpace: 'pre-wrap',
                maxHeight: 260,
                overflowY: 'auto',
              }}>
                {text}
              </div>
            </div>

            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowPreview(false)}
                style={{
                  padding: '8px 16px',
                  borderRadius: 6,
                  border: '1px solid #e2e8f0',
                  background: '#fff',
                  color: '#64748b',
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Annulla
              </button>
              <button
                onClick={handleConfirmCopy}
                style={{
                  padding: '8px 16px',
                  borderRadius: 6,
                  border: 'none',
                  background: '#1e40af',
                  color: '#fff',
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                📋 Copia al verbale
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
