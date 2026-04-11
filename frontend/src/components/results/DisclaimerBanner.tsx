/**
 * DisclaimerBanner: avviso dismissabile sulla qualità della fonte.
 * Visibile solo per strategie C/D/E/F — non per A/B (manuale specifico).
 */
import { useState } from 'react'
import type { SourceMetadata } from '../../types'

interface Props {
  source: SourceMetadata | null | undefined
}

const STRATEGY_STYLE: Record<string, { bg: string; border: string; color: string }> = {
  C: { bg: '#fffbeb', border: '#fcd34d', color: '#92400e' },
  D: { bg: '#fff7ed', border: '#fb923c', color: '#9a3412' },
  E: { bg: '#eff6ff', border: '#93c5fd', color: '#1e40af' },
  F: { bg: '#fef2f2', border: '#fca5a5', color: '#7f1d1d' },
}

export function DisclaimerBanner({ source }: Props) {
  const [dismissed, setDismissed] = useState(false)

  if (!source || !source.disclaimer || dismissed) return null
  // Mostra solo per strategie non-specifiche (C, D, E, F)
  if (source.strategy === 'A' || source.strategy === 'B') return null

  const style = STRATEGY_STYLE[source.strategy] ?? STRATEGY_STYLE['F']

  return (
    <div style={{
      background: style.bg,
      border: `1px solid ${style.border}`,
      borderRadius: 8,
      padding: '10px 14px',
      marginBottom: 14,
      display: 'flex',
      gap: 10,
      alignItems: 'flex-start',
      fontSize: 12,
      color: style.color,
      lineHeight: 1.5,
    }}>
      <span style={{ fontSize: 16, flexShrink: 0, marginTop: 1 }}>⚠️</span>
      <span style={{ flex: 1 }}>{source.disclaimer}</span>
      <button
        onClick={() => setDismissed(true)}
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          color: style.color,
          opacity: 0.6,
          fontSize: 14,
          padding: '0 2px',
          flexShrink: 0,
          lineHeight: 1,
        }}
        title="Chiudi avviso"
      >
        ✕
      </button>
    </div>
  )
}
