interface Props {
  isOnline: boolean
}

export function OfflineBadge({ isOnline }: Props) {
  if (isOnline) return null
  return (
    <div style={{
      background: '#dc2626',
      color: '#fff',
      textAlign: 'center',
      padding: '6px 12px',
      fontSize: '13px',
      fontWeight: 600,
    }}>
      OFFLINE — visualizzando l'ultima scheda salvata
    </div>
  )
}
