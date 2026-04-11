import { useState } from 'react'
import type { WorkplaceCategory, WorkplaceContext, WorkplacePhase } from '../../types'

const CATEGORIES: { key: WorkplaceCategory; label: string; icon: string }[] = [
  { key: 'cantiere', label: 'Cantiere', icon: '🏗️' },
  { key: 'industria', label: 'Industria', icon: '🏭' },
  { key: 'logistica', label: 'Logistica', icon: '📦' },
  { key: 'altro', label: 'Altro', icon: '🔧' },
]

const PHASES: { key: WorkplacePhase; label: string }[] = [
  { key: 'scavo', label: 'Scavo' },
  { key: 'fondazioni', label: 'Fondazioni' },
  { key: 'strutture', label: 'Strutture' },
  { key: 'finiture', label: 'Finiture' },
  { key: 'demolizione', label: 'Demolizione' },
  { key: 'altro', label: 'Altro' },
]

const STORAGE_KEY = 'workplace_context'

export function loadWorkplaceContext(): WorkplaceContext | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function saveWorkplaceContext(ctx: WorkplaceContext): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(ctx))
}

export function clearWorkplaceContext(): void {
  localStorage.removeItem(STORAGE_KEY)
}

export function workplaceContextLabel(ctx: WorkplaceContext): string {
  const cat = CATEGORIES.find(c => c.key === ctx.category)
  if (!cat) return ''
  if (ctx.category === 'cantiere' && ctx.phase) {
    const phase = PHASES.find(p => p.key === ctx.phase)
    return `${cat.icon} ${cat.label} — ${phase?.label ?? ctx.phase}`
  }
  return `${cat.icon} ${cat.label}`
}

interface Props {
  onConfirm: (ctx: WorkplaceContext) => void
  onSkip?: () => void
}

export function WorkplaceContextDialog({ onConfirm, onSkip }: Props) {
  const [category, setCategory] = useState<WorkplaceCategory | null>(null)
  const [phase, setPhase] = useState<WorkplacePhase | null>(null)

  const needsPhase = category === 'cantiere'
  const canConfirm = category !== null && (!needsPhase || phase !== null)

  const handleConfirm = () => {
    if (!category) return
    const ctx: WorkplaceContext = { category, phase: needsPhase && phase ? phase : undefined }
    saveWorkplaceContext(ctx)
    onConfirm(ctx)
  }

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(0,0,0,0.5)',
      zIndex: 2000,
      display: 'flex',
      alignItems: 'flex-end',
      justifyContent: 'center',
    }}>
      <div style={{
        background: '#fff',
        borderRadius: '16px 16px 0 0',
        padding: '24px 20px 32px',
        width: '100%',
        maxWidth: 480,
        boxShadow: '0 -8px 40px rgba(0,0,0,0.2)',
      }}>
        <div style={{ marginBottom: 20, textAlign: 'center' }}>
          <div style={{ fontSize: 28, marginBottom: 8 }}>📍</div>
          <h2 style={{ margin: 0, fontSize: 17, fontWeight: 800, color: '#1e293b' }}>
            Contesto del sopralluogo
          </h2>
          <p style={{ margin: '6px 0 0', fontSize: 13, color: '#64748b' }}>
            Seleziona il tipo di luogo di lavoro. Verrà ricordato per tutte le macchine di questa visita.
          </p>
        </div>

        {/* Selezione categoria */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
          {CATEGORIES.map(cat => (
            <button
              key={cat.key}
              onClick={() => { setCategory(cat.key); setPhase(null) }}
              style={{
                padding: '14px 10px',
                borderRadius: 10,
                border: `2px solid ${category === cat.key ? '#1e40af' : '#e2e8f0'}`,
                background: category === cat.key ? '#eff6ff' : '#fff',
                color: category === cat.key ? '#1e40af' : '#475569',
                fontWeight: 700,
                fontSize: 14,
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <span style={{ fontSize: 22 }}>{cat.icon}</span>
              {cat.label}
            </button>
          ))}
        </div>

        {/* Selezione fase cantiere */}
        {needsPhase && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#64748b', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Fase lavorativa
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {PHASES.map(p => (
                <button
                  key={p.key}
                  onClick={() => setPhase(p.key)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: 20,
                    border: `2px solid ${phase === p.key ? '#1e40af' : '#e2e8f0'}`,
                    background: phase === p.key ? '#eff6ff' : '#fff',
                    color: phase === p.key ? '#1e40af' : '#475569',
                    fontWeight: 600,
                    fontSize: 13,
                    cursor: 'pointer',
                  }}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        )}

        <div style={{ display: 'flex', gap: 10 }}>
          {onSkip && (
            <button
              onClick={onSkip}
              style={{
                flex: 1,
                padding: '12px',
                borderRadius: 8,
                border: '1px solid #e2e8f0',
                background: '#fff',
                color: '#64748b',
                fontWeight: 600,
                fontSize: 14,
                cursor: 'pointer',
              }}
            >
              Salta
            </button>
          )}
          <button
            onClick={handleConfirm}
            disabled={!canConfirm}
            style={{
              flex: 2,
              padding: '14px',
              borderRadius: 8,
              border: 'none',
              background: canConfirm ? '#1e40af' : '#cbd5e1',
              color: '#fff',
              fontWeight: 700,
              fontSize: 15,
              cursor: canConfirm ? 'pointer' : 'not-allowed',
            }}
          >
            Conferma contesto →
          </button>
        </div>
      </div>
    </div>
  )
}
