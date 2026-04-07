import { useState, useCallback } from 'react'
import type { SafetyCard as SafetyCardType, SafetyItem, DispositivoSicurezza, PlateOCRResult } from '../../types'
import React from 'react'
import { RiskBadge } from './RiskBadge'
import { ManualLink } from './ManualLink'
import { ExportButton } from './ExportButton'
import { AllegatoVSection } from './AllegatoVSection'

interface Props {
  card: SafetyCardType
  ocr: PlateOCRResult | null
  onNewSearch: () => void
}

interface SectionProps {
  title: string
  items: SafetyItem[]
  variant: 'risk' | 'protection' | 'recommendation' | 'residual'
  icon: string
}

const SOURCE_BADGE_COLORS: Record<string, { bg: string; color: string }> = {
  'INAIL': { bg: '#dcfce7', color: '#166534' },
  'AI':    { bg: '#fef9c3', color: '#854d0e' },
  'DB':    { bg: '#f3e8ff', color: '#6b21a8' },  // viola — manuali verificati da ispettori
}

// Evidenzia riferimenti pagina/sezione manuale: [pag. 23], [Sez. 2.4], [p. 12], [cap. 3]
function highlightPageRefs(text: string): React.ReactNode {
  const parts = text.split(/(\[(?:pag|Sez|p|cap|sezione|section)\.\s*[\w.]+\])/gi)
  return parts.map((part, i) =>
    /^\[(?:pag|Sez|p|cap|sezione|section)\./i.test(part)
      ? <span key={i} style={{
          display: 'inline-block',
          padding: '0 5px',
          margin: '0 2px',
          borderRadius: 4,
          background: '#f1f5f9',
          color: '#475569',
          fontSize: '0.82em',
          fontWeight: 600,
          border: '1px solid #cbd5e1',
          fontFamily: 'monospace',
          whiteSpace: 'nowrap',
        }}>{part}</span>
      : part
  )
}

function getSourceBadgeStyle(label: string) {
  if (label in SOURCE_BADGE_COLORS) return SOURCE_BADGE_COLORS[label]
  if (label.startsWith('Manuale DB')) return SOURCE_BADGE_COLORS['DB']
  return { bg: '#e0f2fe', color: '#0369a1' }
}

function SourceBadge({ label, size = 10 }: { label: string; size?: number }) {
  const style = getSourceBadgeStyle(label)
  // Tronca etichette lunghe (es. "Manuale categoria simile (carrello elevatore)")
  const MAX = 32
  const display = label.length > MAX ? label.slice(0, MAX) + '…' : label
  return (
    <span
      title={label}
      style={{
        padding: '1px 6px',
        borderRadius: 8,
        background: style.bg,
        color: style.color,
        fontSize: size,
        fontWeight: 700,
        letterSpacing: '0.02em',
        whiteSpace: 'nowrap',
        flexShrink: 0,
        maxWidth: 160,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        display: 'inline-block',
      }}
    >
      {display}
    </span>
  )
}

function Section({ title, items, variant, icon }: SectionProps) {
  const [open, setOpen] = useState(true)

  if (!items.length) return null

  // Conta le fonti distinte per il riepilogo nel titolo (compatibile con stringa o oggetto)
  const fontiUniche = [...new Set(items.map(i => typeof i === 'string' ? null : i.fonte))].filter(Boolean) as string[]

  return (
    <div style={{ marginBottom: 16 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 14px',
          background: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: open ? '8px 8px 0 0' : 8,
          cursor: 'pointer',
          fontWeight: 700,
          fontSize: 15,
          color: '#1e293b',
          gap: 8,
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          {icon} {title}
          {fontiUniche.map(f => <SourceBadge key={f} label={f} />)}
        </span>
        <span style={{ fontSize: 12, color: '#94a3b8', flexShrink: 0 }}>
          {items.length} {open ? '▲' : '▼'}
        </span>
      </button>

      {open && (
        <div style={{
          padding: '12px',
          border: '1px solid #e2e8f0',
          borderTop: 'none',
          borderRadius: '0 0 8px 8px',
          background: '#fff',
        }}>
          {items.map((item, i) => {
            // Compatibilità: accetta sia {testo, fonte} che stringa plain
            const testo = typeof item === 'string' ? item : (item.testo ?? '')
            const fonte = typeof item === 'string' ? null : (item.fonte ?? null)
            const probabilita = typeof item !== 'string' ? item.probabilita : undefined
            const gravita = typeof item !== 'string' ? item.gravita : undefined
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 6, marginBottom: 8 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <RiskBadge text={testo} variant={variant} renderContent={highlightPageRefs(testo)} />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3, paddingTop: 10, flexShrink: 0 }}>
                  {fonte && <SourceBadge label={fonte} size={9} />}
                  {probabilita && gravita && (
                    <span title={`ISO 12100 — Probabilità: ${probabilita}, Gravità: ${gravita}`} style={{
                      padding: '1px 5px',
                      borderRadius: 4,
                      background: gravita === 'S3' ? '#fef2f2' : gravita === 'S2' ? '#fff7ed' : '#f0fdf4',
                      color: gravita === 'S3' ? '#991b1b' : gravita === 'S2' ? '#9a3412' : '#166534',
                      fontSize: 9,
                      fontWeight: 700,
                      fontFamily: 'monospace',
                      cursor: 'help',
                    }}>
                      {probabilita}×{gravita}
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

const TIPO_ICON: Record<string, string> = {
  interblocco:      '🔒',
  sensore:          '📡',
  riparo:           '🛡',
  arresto_emergenza:'🔴',
  segnalazione:     '🔔',
  limitatore:       '⚙️',
}

function DispositiviSicurezzaSection({ items }: { items: DispositivoSicurezza[] }) {
  const [open, setOpen] = useState(true)
  if (!items.length) return null

  const fontiUniche = [...new Set(items.map(i => i.fonte))].filter(Boolean)

  return (
    <div style={{ marginBottom: 16 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 14px',
          background: '#f0f9ff',
          border: '1px solid #bae6fd',
          borderRadius: open ? '8px 8px 0 0' : 8,
          cursor: 'pointer',
          fontWeight: 700,
          fontSize: 15,
          color: '#0c4a6e',
          gap: 8,
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          🔩 Dispositivi di sicurezza da verificare
          {fontiUniche.map(f => <SourceBadge key={f} label={f} />)}
        </span>
        <span style={{ fontSize: 12, color: '#94a3b8', flexShrink: 0 }}>
          {items.length} {open ? '▲' : '▼'}
        </span>
      </button>

      {open && (
        <div style={{
          border: '1px solid #bae6fd',
          borderTop: 'none',
          borderRadius: '0 0 8px 8px',
          background: '#fff',
          overflow: 'hidden',
        }}>
          {items.map((d, i) => (
            <div key={i} style={{
              padding: '12px 14px',
              borderBottom: i < items.length - 1 ? '1px solid #f0f9ff' : 'none',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 16 }}>{TIPO_ICON[d.tipo] ?? '⚙️'}</span>
                <strong style={{ fontSize: 13, color: '#0c4a6e' }}>{d.nome}</strong>
                <span style={{
                  padding: '1px 6px',
                  borderRadius: 6,
                  background: '#e0f2fe',
                  color: '#075985',
                  fontSize: 10,
                  fontWeight: 600,
                }}>
                  {d.tipo.replace('_', ' ')}
                </span>
                <SourceBadge label={d.fonte} size={9} />
              </div>
              <p style={{ margin: '0 0 6px', fontSize: 12, color: '#475569', paddingLeft: 24 }}>
                {d.descrizione}
              </p>
              <div style={{
                marginLeft: 24,
                padding: '6px 10px',
                background: '#f0fdf4',
                borderLeft: '3px solid #16a34a',
                borderRadius: '0 4px 4px 0',
                fontSize: 12,
                color: '#166534',
                fontWeight: 600,
              }}>
                ✓ {d.verifica_ispezione}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// Banner abilitazione operatore — mostrato solo se presente
function AbilitazioneBanner({ testo }: { testo: string }) {
  return (
    <div style={{
      background: '#eff6ff',
      border: '1px solid #93c5fd',
      borderRadius: 8,
      padding: '10px 14px',
      marginBottom: 16,
      fontSize: 13,
      color: '#1e40af',
    }}>
      <strong>🪪 Abilitazione operatore richiesta:</strong> {testo}
    </div>
  )
}

// Sezione documenti da richiedere — spuntabili come checklist
function DocumentiSection({ items }: { items: string[] }) {
  const [checked, setChecked] = useState<Set<number>>(new Set())
  if (!items.length) return null

  const toggle = (i: number) => setChecked(prev => {
    const next = new Set(prev)
    next.has(i) ? next.delete(i) : next.add(i)
    return next
  })

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{
        padding: '12px 14px',
        background: '#faf5ff',
        border: '1px solid #d8b4fe',
        borderRadius: '8px 8px 0 0',
        fontWeight: 700,
        fontSize: 15,
        color: '#6b21a8',
      }}>
        📁 Documenti da richiedere al datore di lavoro
      </div>
      <div style={{
        border: '1px solid #d8b4fe',
        borderTop: 'none',
        borderRadius: '0 0 8px 8px',
        background: '#fff',
      }}>
        {items.map((item, i) => (
          <label
            key={i}
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 12,
              padding: '10px 14px',
              borderBottom: i < items.length - 1 ? '1px solid #f3f0ff' : 'none',
              cursor: 'pointer',
              background: checked.has(i) ? '#f3f0ff' : '#fff',
            }}
          >
            <input
              type="checkbox"
              checked={checked.has(i)}
              onChange={() => toggle(i)}
              style={{ marginTop: 2, width: 16, height: 16, accentColor: '#7c3aed', flexShrink: 0 }}
            />
            <span style={{
              fontSize: 13,
              color: checked.has(i) ? '#a78bfa' : '#334155',
              textDecoration: checked.has(i) ? 'line-through' : 'none',
              lineHeight: 1.5,
            }}>
              {item}
            </span>
          </label>
        ))}
      </div>
    </div>
  )
}

// Sezione verifiche periodiche — banner informativo
function VerifichePeriodicheBanner({ testo }: { testo: string }) {
  return (
    <div style={{
      background: '#fff7ed',
      border: '1px solid #fed7aa',
      borderRadius: 8,
      padding: '10px 14px',
      marginBottom: 16,
      fontSize: 13,
      color: '#9a3412',
    }}>
      <strong>🗓 Verifiche periodiche obbligatorie:</strong> {testo}
    </div>
  )
}

// Sezione pittogrammi — semplice lista
function PittogrammiSection({ items }: { items: string[] }) {
  const [open, setOpen] = useState(true)
  if (!items.length) return null
  return (
    <div style={{ marginBottom: 16 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 14px',
          background: '#fefce8',
          border: '1px solid #fde047',
          borderRadius: open ? '8px 8px 0 0' : 8,
          cursor: 'pointer',
          fontWeight: 700,
          fontSize: 15,
          color: '#713f12',
          gap: 8,
        }}
      >
        <span>⚠ Pittogrammi da verificare sulla macchina</span>
        <span style={{ fontSize: 12, color: '#a16207', flexShrink: 0 }}>
          {items.length} {open ? '▲' : '▼'}
        </span>
      </button>
      {open && (
        <div style={{
          border: '1px solid #fde047',
          borderTop: 'none',
          borderRadius: '0 0 8px 8px',
          background: '#fff',
          padding: '8px 14px',
        }}>
          {items.map((item, i) => (
            <div key={i} style={{
              fontSize: 13,
              color: '#713f12',
              padding: '6px 0',
              borderBottom: i < items.length - 1 ? '1px solid #fef9c3' : 'none',
              lineHeight: 1.5,
            }}>
              ⚠ {item}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function NormativeSection({ items }: { items: string[] }) {
  const [open, setOpen] = useState(false)  // collapsed di default: non ingombra il flusso ispettivo
  if (!items.length) return null
  return (
    <div style={{ marginBottom: 16 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 14px',
          background: '#f0f9ff',
          border: '1px solid #bae6fd',
          borderRadius: open ? '8px 8px 0 0' : 8,
          cursor: 'pointer',
          fontWeight: 700,
          fontSize: 15,
          color: '#0c4a6e',
          gap: 8,
        }}
      >
        <span>📐 Normative applicabili</span>
        <span style={{ fontSize: 12, color: '#94a3b8', flexShrink: 0 }}>
          {items.length} {open ? '▲' : '▼'}
        </span>
      </button>
      {open && (
        <div style={{
          border: '1px solid #bae6fd',
          borderTop: 'none',
          borderRadius: '0 0 8px 8px',
          background: '#fff',
          padding: '8px 14px',
        }}>
          {items.map((norm, i) => (
            <div key={i} style={{
              fontSize: 12,
              color: '#0369a1',
              padding: '5px 0',
              borderBottom: i < items.length - 1 ? '1px solid #f0f9ff' : 'none',
              lineHeight: 1.5,
            }}>
              📌 {norm}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ChecklistSection({ items }: { items: string[] }) {
  const [checked, setChecked] = useState<Set<number>>(new Set())
  const [open, setOpen] = useState(true)

  const toggle = useCallback((i: number) => {
    setChecked(prev => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })
  }, [])

  if (!items.length) return null

  const done = checked.size
  const total = items.length

  return (
    <div style={{ marginBottom: 16 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 14px',
          background: done === total ? '#f0fdf4' : '#f8fafc',
          border: `1px solid ${done === total ? '#86efac' : '#e2e8f0'}`,
          borderRadius: open ? '8px 8px 0 0' : 8,
          cursor: 'pointer',
          fontWeight: 700,
          fontSize: 15,
          color: '#1e293b',
          gap: 8,
        }}
      >
        <span>✅ Checklist sopralluogo</span>
        <span style={{ fontSize: 12, color: done === total ? '#16a34a' : '#94a3b8', fontWeight: 700 }}>
          {done}/{total} {open ? '▲' : '▼'}
        </span>
      </button>

      {open && (
        <div style={{
          border: '1px solid #e2e8f0',
          borderTop: 'none',
          borderRadius: '0 0 8px 8px',
          background: '#fff',
          overflow: 'hidden',
        }}>
          {items.map((item, i) => (
            <label
              key={i}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 12,
                padding: '10px 14px',
                borderBottom: i < items.length - 1 ? '1px solid #f1f5f9' : 'none',
                cursor: 'pointer',
                background: checked.has(i) ? '#f0fdf4' : '#fff',
                transition: 'background 0.15s',
              }}
            >
              <input
                type="checkbox"
                checked={checked.has(i)}
                onChange={() => toggle(i)}
                style={{ marginTop: 2, width: 16, height: 16, accentColor: '#16a34a', flexShrink: 0 }}
              />
              <span style={{
                fontSize: 13,
                color: checked.has(i) ? '#86efac' : '#334155',
                textDecoration: checked.has(i) ? 'line-through' : 'none',
                lineHeight: 1.5,
              }}>
                {item}
              </span>
            </label>
          ))}
          {done > 0 && (
            <div style={{ padding: '8px 14px', background: '#f8fafc', fontSize: 12, color: '#64748b', textAlign: 'right' }}>
              <button
                onClick={() => setChecked(new Set())}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: 11 }}
              >
                Azzera
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ConfidenceBadge({ confidence }: { confidence: PlateOCRResult['confidence'] }) {
  const colors = {
    high:   { bg: '#f0fdf4', color: '#166534', label: 'Alta' },
    medium: { bg: '#fffbeb', color: '#92400e', label: 'Media' },
    low:    { bg: '#fef2f2', color: '#991b1b', label: 'Bassa' },
  }
  const c = colors[confidence]
  return (
    <span style={{
      padding: '2px 10px',
      borderRadius: 12,
      background: c.bg,
      color: c.color,
      fontSize: 12,
      fontWeight: 600,
    }}>
      OCR: {c.label}
    </span>
  )
}

function buildEmailDraft(card: SafetyCardType, ocr: PlateOCRResult | null): string {
  const serial = ocr?.serial_number ? `\nMatricola / N° serie: ${ocr.serial_number}` : ''
  const year = ocr?.year ? `\nAnno di fabbricazione: ${ocr.year}` : ''
  const subject = encodeURIComponent(`Richiesta manuale d'uso e dichiarazione CE — ${card.brand} ${card.model}`)
  const body = encodeURIComponent(
`Spett.le ${card.brand},

in qualità di ispettore della sicurezza sul lavoro, nell'ambito di un accesso ispettivo ai sensi del D.Lgs. 81/2008, si richiede cortesemente la trasmissione della seguente documentazione relativa al macchinario:

Marca: ${card.brand}
Modello: ${card.model}${serial}${year}

Documentazione richiesta:
- Manuale d'uso e manutenzione originale
- Dichiarazione di conformità CE (ove applicabile)
- Libretto di istruzione per l'operatore

La documentazione può essere inviata in formato PDF al presente indirizzo.

In attesa di cortese riscontro, si porgono distinti saluti.`
  )
  return `mailto:?subject=${subject}&body=${body}`
}

export function SafetyCard({ card, ocr, onNewSearch }: Props) {
  const isFallback = card.fonte_tipo === 'fallback_ai'

  return (
    <div className="safety-card-printable" style={{ padding: '16px' }}>

      {/* Header macchina */}
      <div style={{
        background: 'linear-gradient(135deg, #1e40af, #1d4ed8)',
        borderRadius: 12,
        padding: '16px',
        color: '#fff',
        marginBottom: 16,
      }}>
        <p style={{ margin: '0 0 4px', fontSize: 12, opacity: 0.8 }}>MACCHINARIO IDENTIFICATO</p>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800 }}>
          {card.brand} {card.model}
        </h2>
        <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {ocr?.serial_number && (
            <span style={{ fontSize: 12, opacity: 0.85 }}>N° serie: {ocr.serial_number}</span>
          )}
          {ocr?.year && (
            <span style={{ fontSize: 12, opacity: 0.85 }}>Anno: {ocr.year}</span>
          )}
          {ocr && <ConfidenceBadge confidence={ocr.confidence} />}
        </div>
      </div>

      {/* Safety Gate EU Alerts */}
      {card.safety_alerts?.length > 0 && (
        <div style={{
          background: '#fef2f2',
          border: '2px solid #fca5a5',
          borderRadius: 8,
          padding: '12px 14px',
          marginBottom: 16,
        }}>
          <p style={{ margin: '0 0 8px', fontSize: 13, fontWeight: 800, color: '#991b1b' }}>
            🚨 AVVISO SAFETY GATE EU — Richiami / Difetti Noti
          </p>
          {card.safety_alerts.map((alert, i) => (
            <div key={i} style={{
              background: alert.risk_level === 'serious' ? '#fee2e2' : '#fff7ed',
              border: `1px solid ${alert.risk_level === 'serious' ? '#fca5a5' : '#fed7aa'}`,
              borderRadius: 6,
              padding: '8px 10px',
              marginBottom: 6,
              fontSize: 12,
            }}>
              <strong style={{ color: '#991b1b' }}>{alert.title}</strong>
              {alert.description && <p style={{ margin: '4px 0 0', color: '#7f1d1d' }}>{alert.description}</p>}
              {alert.measures && <p style={{ margin: '4px 0 0', color: '#78350f' }}>Misure: {alert.measures}</p>}
              <div style={{ marginTop: 6, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {alert.reference && <span style={{ fontSize: 10, color: '#94a3b8' }}>Rif: {alert.reference}</span>}
                {alert.date && <span style={{ fontSize: 10, color: '#94a3b8' }}>{alert.date}</span>}
                {alert.url && (
                  <a href={alert.url} target="_blank" rel="noopener noreferrer"
                    style={{ fontSize: 10, color: '#dc2626', fontWeight: 600 }}>
                    Dettaglio Safety Gate →
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Warning fallback */}
      {isFallback && (
        <div style={{
          background: '#fffbeb',
          border: '1px solid #fde68a',
          borderRadius: 8,
          padding: '10px 14px',
          marginBottom: 16,
          fontSize: 13,
          color: '#92400e',
          fontWeight: 600,
        }}>
          ⚠️ Scheda generata senza manuale ufficiale. Verificare con la documentazione originale del costruttore.
          {card.confidence_ai && (
            <span style={{
              marginLeft: 8,
              padding: '1px 8px',
              borderRadius: 8,
              background: card.confidence_ai === 'high' ? '#dcfce7' : card.confidence_ai === 'medium' ? '#fef9c3' : '#fee2e2',
              color: card.confidence_ai === 'high' ? '#166534' : card.confidence_ai === 'medium' ? '#854d0e' : '#991b1b',
              fontSize: 11,
              fontWeight: 700,
            }}>
              Certezza AI: {card.confidence_ai === 'high' ? 'Alta' : card.confidence_ai === 'medium' ? 'Media' : 'Bassa'}
            </span>
          )}
        </div>
      )}

      {/* Avvisi da OCR */}
      {ocr?.notes && ocr.notes !== '' && (
        <div style={{
          background: '#fffbeb',
          border: '1px solid #fde68a',
          borderRadius: 8,
          padding: '10px 14px',
          marginBottom: 16,
          fontSize: 13,
          color: '#92400e',
        }}>
          ⚠️ {ocr.notes}
        </div>
      )}

      {/* Sezione Allegato V — solo per macchine ante-1996 */}
      <AllegatoVSection card={card} />

      {/* Abilitazione operatore — banner normativo */}
      {card.abilitazione_operatore && (
        <AbilitazioneBanner testo={card.abilitazione_operatore} />
      )}

      {/* Verifiche periodiche obbligatorie — banner */}
      {card.verifiche_periodiche && (
        <VerifichePeriodicheBanner testo={card.verifiche_periodiche} />
      )}

      {/* Normative applicabili per il tipo macchina (collapsed di default) */}
      <NormativeSection items={card.normative_applicabili ?? []} />

      {/* Sezioni sicurezza */}
      <Section
        title="Rischi principali"
        items={card.rischi_principali}
        variant="risk"
        icon="⚠️"
      />
      <Section
        title="Dispositivi di protezione (DPI)"
        items={card.dispositivi_protezione}
        variant="protection"
        icon="🛡️"
      />
      <DispositiviSicurezzaSection items={card.dispositivi_sicurezza ?? []} />
      <Section
        title="Raccomandazioni del produttore"
        items={card.raccomandazioni_produttore}
        variant="recommendation"
        icon="📋"
      />
      {/* Limiti operativi — portate, pressioni, pendenze con valori numerici */}
      {(card.limiti_operativi ?? []).length > 0 && (
        <Section
          title="Limiti operativi"
          items={card.limiti_operativi ?? []}
          variant="recommendation"
          icon="⚙️"
        />
      )}
      {/* Procedure di emergenza specifiche del modello */}
      {(card.procedure_emergenza ?? []).length > 0 && (
        <Section
          title="Procedure di emergenza"
          items={card.procedure_emergenza ?? []}
          variant="residual"
          icon="🚨"
        />
      )}
      <Section
        title="Rischi residui"
        items={card.rischi_residui}
        variant="residual"
        icon="🔶"
      />

      {/* Pittogrammi da verificare fisicamente sulla macchina */}
      <PittogrammiSection items={card.pittogrammi_sicurezza ?? []} />

      <ChecklistSection items={card.checklist ?? []} />

      {/* Documenti da richiedere al datore di lavoro */}
      <DocumentiSection items={card.documenti_da_richiedere ?? []} />

      {/* Note aggiuntive */}
      {card.note && !isFallback && (
        <div style={{
          background: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: 8,
          padding: '10px 14px',
          marginBottom: 16,
          fontSize: 13,
          color: '#475569',
        }}>
          📝 {card.note}
        </div>
      )}

      {/* Fonte manuale */}
      <ManualLink url={card.fonte_manuale} inailUrl={card.fonte_inail} tipo={card.fonte_tipo} brand={card.brand} model={card.model} machineType={card.machine_type ?? undefined} />

      {/* Footer con data */}
      <p style={{
        textAlign: 'center',
        fontSize: 11,
        color: '#94a3b8',
        margin: '12px 0',
      }}>
        Scheda generata il {new Date(card.generated_at).toLocaleString('it-IT')}
      </p>

      {/* Azioni */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 8 }}>
        <ExportButton card={card} />
        {isFallback && (
          <a
            href={buildEmailDraft(card, ocr)}
            style={{
              display: 'block',
              width: '100%',
              padding: '14px',
              background: '#fffbeb',
              color: '#92400e',
              border: '2px solid #fde68a',
              borderRadius: 8,
              fontSize: 15,
              fontWeight: 700,
              cursor: 'pointer',
              textAlign: 'center',
              textDecoration: 'none',
              boxSizing: 'border-box',
            }}
          >
            ✉ Richiedi manuale al produttore
          </a>
        )}
        <button
          onClick={onNewSearch}
          style={{
            width: '100%',
            padding: '14px',
            background: '#fff',
            color: '#1e40af',
            border: '2px solid #1e40af',
            borderRadius: 8,
            fontSize: 15,
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          + Nuova analisi
        </button>
      </div>
    </div>
  )
}
