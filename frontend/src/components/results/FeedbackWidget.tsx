/**
 * FeedbackWidget: raccoglie il rating ispettore sulla scheda sicurezza.
 * Submit a POST /feedback/card. Mostrato in fondo a SafetyCard.
 */
import { useState } from 'react'
import type { SafetyCard } from '../../types'

interface Props {
  card: SafetyCard
}

const PROBLEMI_LABELS: Record<string, string> = {
  norme_errate:                'Norme citate errate',
  checklist_incompleta:        'Checklist incompleta',
  dati_macchina_sbagliati:     'Dati macchina errati',
  prescrizioni_inutilizzabili: 'Prescrizioni inutilizzabili',
  fonte_non_affidabile:        'Fonte non affidabile',
}

export function FeedbackWidget({ card }: Props) {
  const [rating, setRating] = useState<number | null>(null)
  const [problemi, setProblemi] = useState<string[]>([])
  const [submitted, setSubmitted] = useState(false)
  const [sendError, setSendError] = useState(false)
  const [loading, setLoading] = useState(false)

  if (submitted) {
    return (
      <div style={{
        borderTop: '1px solid #f1f5f9',
        marginTop: 20,
        paddingTop: 14,
        textAlign: 'center',
        fontSize: 13,
        color: sendError ? '#dc2626' : '#64748b',
      }}>
        {sendError ? '⚠ Feedback non inviato (errore di rete) — grazie comunque' : '✅ Grazie per il feedback'}
      </div>
    )
  }

  const toggleProblema = (key: string) => {
    setProblemi(prev =>
      prev.includes(key) ? prev.filter(p => p !== key) : [...prev, key]
    )
  }

  const submit = async () => {
    if (rating === null) return
    setLoading(true)
    try {
      const res = await fetch('/feedback/card', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          brand: card.brand,
          model: card.model,
          machine_type: card.machine_type ?? null,
          rating,
          problemi,
          strategy: card.source_metadata?.strategy ?? null,
          fonte_tipo: card.fonte_tipo ?? null,
        }),
      })
      if (!res.ok) setSendError(true)
      setSubmitted(true)
    } catch {
      setSendError(true)
      setSubmitted(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      borderTop: '1px solid #f1f5f9',
      marginTop: 20,
      paddingTop: 14,
    }}>
      <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 8 }}>
        Questa scheda è stata utile per il sopralluogo?
      </div>

      {/* Rating 1-5 */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
        {[1, 2, 3, 4, 5].map(r => (
          <button
            key={r}
            onClick={() => setRating(r)}
            title={['Molto scarsa', 'Scarsa', 'Sufficiente', 'Buona', 'Ottima'][r - 1]}
            style={{
              background: rating === r ? '#1e40af' : '#f8fafc',
              color: rating === r ? '#fff' : '#475569',
              border: `1px solid ${rating === r ? '#1e40af' : '#e2e8f0'}`,
              borderRadius: 8,
              width: 36,
              height: 36,
              cursor: 'pointer',
              fontSize: 14,
              fontWeight: 600,
              transition: 'all 0.15s',
            }}
          >
            {r}
          </button>
        ))}
      </div>

      {/* Problemi (visibili solo se rating ≤ 2) */}
      {rating !== null && rating <= 2 && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 5 }}>
            Cosa non va? (opzionale)
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
            {Object.entries(PROBLEMI_LABELS).map(([key, label]) => (
              <button
                key={key}
                onClick={() => toggleProblema(key)}
                style={{
                  background: problemi.includes(key) ? '#fef2f2' : '#f8fafc',
                  color: problemi.includes(key) ? '#dc2626' : '#475569',
                  border: `1px solid ${problemi.includes(key) ? '#dc2626' : '#e2e8f0'}`,
                  borderRadius: 5,
                  padding: '3px 9px',
                  cursor: 'pointer',
                  fontSize: 11,
                  transition: 'all 0.15s',
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      )}

      {rating !== null && (
        <button
          onClick={submit}
          disabled={loading}
          style={{
            background: '#1e40af',
            color: '#fff',
            border: 'none',
            borderRadius: 7,
            padding: '5px 16px',
            cursor: loading ? 'default' : 'pointer',
            fontSize: 12,
            fontWeight: 600,
            opacity: loading ? 0.7 : 1,
          }}
        >
          {loading ? 'Invio…' : 'Invia feedback'}
        </button>
      )}
    </div>
  )
}
