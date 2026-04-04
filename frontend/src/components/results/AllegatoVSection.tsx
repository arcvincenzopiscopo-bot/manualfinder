import { useState } from 'react'
import type { SafetyCard, AllegatoVRequisito, TabellaCEAnte, BozzaPrescrizione } from '../../types'

// ── Colori criticità ─────────────────────────────────────────────────────────
const CRITICITA_STYLE: Record<string, { bg: string; color: string; label: string }> = {
  alta:   { bg: '#fef2f2', color: '#991b1b', label: 'Alta' },
  media:  { bg: '#fffbeb', color: '#92400e', label: 'Media' },
  bassa:  { bg: '#f0fdf4', color: '#166534', label: 'Bassa' },
}

// ── RequisitItem ─────────────────────────────────────────────────────────────
function RequisitoItem({ req, prescrizione }: {
  req: AllegatoVRequisito
  prescrizione?: BozzaPrescrizione
}) {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const stile = CRITICITA_STYLE[req.criticita] ?? CRITICITA_STYLE['bassa']

  function copyPrescrizione() {
    if (!prescrizione) return
    navigator.clipboard.writeText(prescrizione.prescrizione).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div style={{
      border: `1px solid ${req.criticita === 'alta' ? '#fca5a5' : req.criticita === 'media' ? '#fde68a' : '#86efac'}`,
      borderRadius: 8,
      marginBottom: 8,
      overflow: 'hidden',
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 12px',
          background: stile.bg,
          border: 'none',
          cursor: 'pointer',
          gap: 8,
          textAlign: 'left',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
          <span style={{
            fontSize: 10,
            fontWeight: 700,
            padding: '2px 6px',
            borderRadius: 4,
            background: stile.color,
            color: '#fff',
            whiteSpace: 'nowrap',
          }}>
            {req.criticita.toUpperCase()}
          </span>
          <span style={{ fontSize: 12, fontWeight: 700, color: '#1e293b' }}>
            [{req.id}] {req.titolo}
          </span>
        </span>
        <span style={{ fontSize: 11, color: '#94a3b8' }}>{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div style={{ padding: '10px 12px', background: '#fff', borderTop: `1px solid ${stile.color}22` }}>
          <p style={{ margin: '0 0 8px', fontSize: 12, color: '#334155', lineHeight: 1.6 }}>
            {req.testo}
          </p>
          <div style={{
            background: '#f0fdf4',
            border: '1px solid #86efac',
            borderRadius: 6,
            padding: '6px 10px',
            marginBottom: prescrizione ? 8 : 0,
          }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: '#166534' }}>🔍 Verifica in sopralluogo: </span>
            <span style={{ fontSize: 11, color: '#166534' }}>{req.verifica}</span>
          </div>

          {prescrizione && (
            <div style={{
              background: '#fef2f2',
              border: '1px solid #fca5a5',
              borderRadius: 6,
              padding: '8px 10px',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: '#991b1b' }}>
                  📋 Bozza prescrizione (Art. 70 c.1 D.Lgs. 81/08)
                </span>
                <button
                  onClick={copyPrescrizione}
                  style={{
                    fontSize: 10,
                    padding: '2px 8px',
                    background: copied ? '#dcfce7' : '#fff',
                    border: '1px solid #e2e8f0',
                    borderRadius: 4,
                    cursor: 'pointer',
                    color: copied ? '#166534' : '#64748b',
                    fontWeight: 600,
                  }}
                >
                  {copied ? '✓ Copiato' : 'Copia bozza'}
                </button>
              </div>
              <p style={{ margin: 0, fontSize: 11, color: '#7f1d1d', lineHeight: 1.6, fontStyle: 'italic' }}>
                {prescrizione.prescrizione}
              </p>
              <p style={{ margin: '6px 0 0', fontSize: 10, color: '#94a3b8' }}>
                ⚠ Bozza generata da AI — verificare e adattare prima dell'uso ufficiale.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── TabellaComparativa ───────────────────────────────────────────────────────
function TabellaComparativa({ rows }: { rows: TabellaCEAnte[] }) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
        <thead>
          <tr style={{ background: '#1e40af', color: '#fff' }}>
            <th style={{ padding: '6px 8px', textAlign: 'left', width: '22%' }}>Aspetto</th>
            <th style={{ padding: '6px 8px', textAlign: 'left', width: '30%' }}>Allegato V (ante-1996)</th>
            <th style={{ padding: '6px 8px', textAlign: 'left', width: '30%' }}>Direttiva CE 2006/42</th>
            <th style={{ padding: '6px 8px', textAlign: 'left', width: '18%' }}>Gap</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={{ background: i % 2 === 0 ? '#f8fafc' : '#fff' }}>
              <td style={{ padding: '6px 8px', fontWeight: 700, color: '#1e293b', verticalAlign: 'top' }}>
                {row.aspetto}
              </td>
              <td style={{ padding: '6px 8px', color: '#374151', verticalAlign: 'top' }}>
                {row.allegato_v}
              </td>
              <td style={{ padding: '6px 8px', color: '#374151', verticalAlign: 'top' }}>
                {row.dir_ce}
              </td>
              <td style={{ padding: '6px 8px', color: '#92400e', verticalAlign: 'top', fontStyle: 'italic' }}>
                {row.gap}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Componente principale ────────────────────────────────────────────────────
export function AllegatoVSection({ card }: { card: SafetyCard }) {
  const [tab, setTab] = useState<'requisiti' | 'tabella' | 'gap'>('requisiti')

  if (!card.is_allegato_v) return null

  const requisiti = card.allegato_v_requisiti ?? []
  const tabella = card.tabella_ce_ante ?? []
  const prescrizioni = card.bozze_prescrizioni ?? []
  const prescrizioniMap = Object.fromEntries(prescrizioni.map(p => [p.req_id, p]))

  const critAlte = requisiti.filter(r => r.criticita === 'alta').length

  return (
    <div style={{
      border: '2px solid #dc2626',
      borderRadius: 10,
      marginBottom: 16,
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        background: 'linear-gradient(135deg, #7f1d1d, #991b1b)',
        padding: '12px 14px',
        color: '#fff',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 16, fontWeight: 800 }}>
            🚨 Allegato V D.Lgs. 81/08
          </span>
          <span style={{
            fontSize: 10, fontWeight: 700, padding: '2px 8px',
            background: '#fef2f2', color: '#991b1b', borderRadius: 10,
          }}>
            ANTE-1996
          </span>
          {card.machine_year && (
            <span style={{ fontSize: 11, opacity: 0.9 }}>Anno: {card.machine_year}</span>
          )}
        </div>
        <p style={{ margin: '4px 0 0', fontSize: 11, opacity: 0.85 }}>
          {card.allegato_v_label ?? 'Macchina ante-CE'} — nessuna marcatura CE richiesta.
          Deve essere adeguata ai requisiti minimi dell'Allegato V (Art. 70 c.1).
        </p>
        {critAlte > 0 && (
          <p style={{ margin: '4px 0 0', fontSize: 11, fontWeight: 700, color: '#fca5a5' }}>
            {critAlte} requisito/i a criticità ALTA — bozze prescrizione disponibili
          </p>
        )}
      </div>

      {/* Tab bar */}
      <div style={{ display: 'flex', borderBottom: '1px solid #e2e8f0', background: '#fef2f2' }}>
        {[
          { key: 'requisiti', label: `Requisiti (${requisiti.length})` },
          { key: 'tabella', label: 'Tabella CE vs Ante-CE' },
          { key: 'gap', label: 'Gap Analysis' },
        ].map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key as typeof tab)}
            style={{
              flex: 1,
              padding: '8px 4px',
              border: 'none',
              borderBottom: tab === t.key ? '3px solid #dc2626' : '3px solid transparent',
              background: 'none',
              fontSize: 11,
              fontWeight: tab === t.key ? 700 : 400,
              color: tab === t.key ? '#991b1b' : '#64748b',
              cursor: 'pointer',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Contenuto tab */}
      <div style={{ padding: '12px' }}>

        {tab === 'requisiti' && (
          <>
            {requisiti.length === 0 ? (
              <p style={{ fontSize: 12, color: '#94a3b8', textAlign: 'center', padding: 16 }}>
                Nessun requisito disponibile per questa categoria.
              </p>
            ) : (
              requisiti.map(req => (
                <RequisitoItem
                  key={req.id}
                  req={req}
                  prescrizione={prescrizioniMap[req.id]}
                />
              ))
            )}
          </>
        )}

        {tab === 'tabella' && (
          <>
            {tabella.length === 0 ? (
              <p style={{ fontSize: 12, color: '#94a3b8', textAlign: 'center', padding: 16 }}>
                Tabella non disponibile per questa categoria.
              </p>
            ) : (
              <>
                <p style={{ fontSize: 11, color: '#64748b', marginBottom: 8 }}>
                  Confronto tra i requisiti minimi dell'Allegato V e quanto sarebbe richiesto dalla
                  Direttiva Macchine 2006/42/CE per una macchina equivalente nuova.
                </p>
                <TabellaComparativa rows={tabella} />
              </>
            )}
          </>
        )}

        {tab === 'gap' && (
          <>
            {card.gap_ce_ante ? (
              <div style={{
                background: '#fffbeb',
                border: '1px solid #fde68a',
                borderRadius: 8,
                padding: '12px 14px',
              }}>
                <p style={{ margin: '0 0 6px', fontSize: 12, fontWeight: 700, color: '#92400e' }}>
                  🔍 Analisi del divario normativo (Allegato V → Direttiva CE 2006/42)
                </p>
                <p style={{ margin: 0, fontSize: 12, color: '#78350f', lineHeight: 1.7 }}>
                  {card.gap_ce_ante}
                </p>
              </div>
            ) : (
              <p style={{ fontSize: 12, color: '#94a3b8', textAlign: 'center', padding: 16 }}>
                Gap analysis non disponibile per questa macchina.
              </p>
            )}
            {tabella.length > 0 && (
              <p style={{ fontSize: 11, color: '#64748b', marginTop: 10 }}>
                Per i dettagli punto per punto, consulta la tab <strong>Tabella CE vs Ante-CE</strong>.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}
