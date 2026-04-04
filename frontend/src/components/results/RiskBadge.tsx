interface Props {
  text: string
  variant?: 'risk' | 'protection' | 'recommendation' | 'residual'
}

const VARIANT_STYLE: Record<NonNullable<Props['variant']>, { bg: string; color: string; dot: string }> = {
  risk:           { bg: '#fef2f2', color: '#991b1b', dot: '#dc2626' },
  protection:     { bg: '#f0fdf4', color: '#166534', dot: '#16a34a' },
  recommendation: { bg: '#eff6ff', color: '#1e3a8a', dot: '#2563eb' },
  residual:       { bg: '#fffbeb', color: '#92400e', dot: '#d97706' },
}

export function RiskBadge({ text, variant = 'risk' }: Props) {
  const style = VARIANT_STYLE[variant]
  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-start',
      gap: 10,
      padding: '10px 12px',
      background: style.bg,
      borderRadius: 8,
      marginBottom: 8,
    }}>
      <span style={{
        width: 8,
        height: 8,
        borderRadius: '50%',
        background: style.dot,
        marginTop: 5,
        flexShrink: 0,
      }} />
      <span style={{ fontSize: 14, color: style.color, lineHeight: 1.5 }}>{text}</span>
    </div>
  )
}
