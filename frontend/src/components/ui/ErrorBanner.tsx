interface Props {
  message: string
  onRetry: () => void
}

export function ErrorBanner({ message, onRetry }: Props) {
  return (
    <div style={{
      background: '#fef2f2',
      border: '1px solid #fca5a5',
      borderRadius: 8,
      padding: '16px',
      margin: '16px',
    }}>
      <p style={{ color: '#dc2626', fontWeight: 600, margin: '0 0 8px' }}>
        Errore durante l'analisi
      </p>
      <p style={{ color: '#7f1d1d', fontSize: 14, margin: '0 0 12px' }}>{message}</p>
      <button
        onClick={onRetry}
        style={{
          background: '#dc2626',
          color: '#fff',
          border: 'none',
          borderRadius: 6,
          padding: '8px 20px',
          fontWeight: 600,
          cursor: 'pointer',
        }}
      >
        Riprova
      </button>
    </div>
  )
}
