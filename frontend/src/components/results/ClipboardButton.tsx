import { useState } from 'react'

export function ClipboardButton({ text }: { text?: string }) {
  const [copied, setCopied] = useState(false)
  const disabled = !text

  const handleCopy = async () => {
    if (disabled) return
    try {
      await navigator.clipboard.writeText(text!)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard API non disponibile (es. HTTP non sicuro)
    }
  }

  return (
    <button
      onClick={handleCopy}
      disabled={disabled}
      title={disabled ? 'Prescrizione non disponibile' : 'Copia prescrizione nel verbale'}
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
  )
}
