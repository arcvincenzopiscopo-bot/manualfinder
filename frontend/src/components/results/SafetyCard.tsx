import { useState, useCallback } from 'react'
import type { SafetyCard as SafetyCardType, SafetyItem, DispositivoSicurezza, PlateOCRResult, ChecklistItem, DocumentoRichiesto } from '../../types'
import React from 'react'
import { RiskBadge } from './RiskBadge'
import { ManualLink } from './ManualLink'
import { ExportButton } from './ExportButton'
import { AllegatoVSection } from './AllegatoVSection'
import { ClipboardButton } from './ClipboardButton'
import { SourceBadgeBar } from './SourceBadgeBar'
import { DisclaimerBanner } from './DisclaimerBanner'
import { FeedbackWidget } from './FeedbackWidget'

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
  sourceLabel?: string
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
      ? <span key={`ref_${i}_${part.slice(0, 16)}`} style={{
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

function Section({ title, items, variant, icon, sourceLabel }: SectionProps) {
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
          {sourceLabel && fontiUniche.length === 0 && <SourceBadge label={sourceLabel} />}
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
              <div key={`${i}_${testo.slice(0, 20)}`} style={{ display: 'flex', alignItems: 'flex-start', gap: 6, marginBottom: 8 }}>
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
            <div key={`${i}_${d.nome ?? ''}`} style={{
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

// Sezione documenti da richiedere — spuntabili come checklist con smart hint e doppio livello di espansione
function DocumentiSection({ items }: { items: (DocumentoRichiesto | string)[] }) {
  const [checked, setChecked] = useState<Set<number>>(new Set())
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const [expandedValidity, setExpandedValidity] = useState<Set<number>>(new Set())
  const [expandedIrregularity, setExpandedIrregularity] = useState<Set<number>>(new Set())
  if (!items.length) return null

  const parsed = items.map(i =>
    typeof i === 'string' ? { documento: i, smart_hint: '' } : i
  )

  const toggle = (i: number) => setChecked(prev => {
    const next = new Set(prev)
    next.has(i) ? next.delete(i) : next.add(i)
    return next
  })

  const toggleHint = (i: number) => setExpanded(prev => {
    const next = new Set(prev)
    next.has(i) ? next.delete(i) : next.add(i)
    return next
  })

  const toggleValidity = (i: number) => setExpandedValidity(prev => {
    const next = new Set(prev)
    next.has(i) ? next.delete(i) : next.add(i)
    return next
  })

  const toggleIrregularity = (i: number) => setExpandedIrregularity(prev => {
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
        {parsed.map((item, i) => {
          const hasL2 = !!(item.validity_requirements || item.irregularity_indicators)
          return (
            <div key={`${i}_${item.documento?.slice(0, 20) ?? ''}`} style={{
              borderBottom: i < parsed.length - 1 ? '1px solid #f3f0ff' : 'none',
              background: checked.has(i) ? '#f3f0ff' : '#fff',
            }}>
              <label style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '10px 14px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={checked.has(i)}
                  onChange={() => toggle(i)}
                  style={{ marginTop: 2, width: 16, height: 16, accentColor: '#7c3aed', flexShrink: 0 }}
                />
                <span style={{
                  flex: 1,
                  fontSize: 13,
                  color: checked.has(i) ? '#a78bfa' : '#334155',
                  textDecoration: checked.has(i) ? 'line-through' : 'none',
                  lineHeight: 1.5,
                }}>
                  {item.documento}
                </span>
                {item.smart_hint && (
                  <button
                    onClick={e => { e.preventDefault(); toggleHint(i) }}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 11, color: '#7c3aed', flexShrink: 0, padding: '2px 4px' }}
                    title="Mostra suggerimento"
                  >
                    {expanded.has(i) ? '▾ Suggerimento' : '▸ Suggerimento'}
                  </button>
                )}
              </label>

              {/* Livello 1: suggerimento pratico */}
              {item.smart_hint && expanded.has(i) && (
                <div style={{ padding: '0 14px 8px 42px', fontSize: 12, color: '#6b21a8', fontStyle: 'italic', lineHeight: 1.5 }}>
                  💡 {item.smart_hint}
                </div>
              )}

              {/* Livello 2: requisiti di validità e indicatori di irregolarità */}
              {item.smart_hint && expanded.has(i) && hasL2 && (
                <div style={{ padding: '0 14px 8px 42px', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {item.validity_requirements && (
                    <button
                      onClick={e => { e.preventDefault(); toggleValidity(i) }}
                      style={{
                        background: 'none', border: '1px solid #d8b4fe', cursor: 'pointer',
                        fontSize: 10, color: '#7c3aed', padding: '2px 8px', borderRadius: 20,
                        fontWeight: 600,
                      }}
                    >
                      {expandedValidity.has(i) ? '▾' : '▸'} Requisiti di validità
                    </button>
                  )}
                  {item.irregularity_indicators && (
                    <button
                      onClick={e => { e.preventDefault(); toggleIrregularity(i) }}
                      style={{
                        background: 'none', border: '1px solid #fca5a5', cursor: 'pointer',
                        fontSize: 10, color: '#b91c1c', padding: '2px 8px', borderRadius: 20,
                        fontWeight: 600,
                      }}
                    >
                      {expandedIrregularity.has(i) ? '▾' : '▸'} Indicatori di irregolarità
                    </button>
                  )}
                </div>
              )}

              {item.validity_requirements && expandedValidity.has(i) && (
                <div style={{
                  padding: '4px 14px 8px 42px', fontSize: 12, color: '#6b21a8',
                  background: '#faf5ff', lineHeight: 1.5,
                }}>
                  ✓ {item.validity_requirements}
                </div>
              )}

              {item.irregularity_indicators && expandedIrregularity.has(i) && (
                <div style={{
                  padding: '4px 14px 8px 42px', fontSize: 12, color: '#991b1b',
                  background: '#fff1f2', lineHeight: 1.5,
                }}>
                  ⚠ {item.irregularity_indicators}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// DPI separati per destinatario (operatore / personale a terra)
function DPISection({ items, sourceLabel }: { items: SafetyItem[]; sourceLabel?: string }) {
  const hasRecipient = items.some(it => it.recipient)

  if (!hasRecipient) {
    // Fallback: rendering piatto per dati senza campo recipient
    return (
      <Section title="Dispositivi di protezione (DPI)" items={items} variant="protection" icon="🛡️" sourceLabel={sourceLabel} />
    )
  }

  const operatore = items.filter(it => it.recipient === 'operatore' || it.recipient === 'entrambi')
  const terra = items.filter(it => it.recipient === 'personale_a_terra' || it.recipient === 'entrambi')

  const renderBlock = (label: string, icon: string, blockItems: SafetyItem[], color: string, bg: string, border: string) => (
    <div style={{ marginBottom: 8 }}>
      <div style={{
        padding: '8px 14px',
        background: bg,
        border: `1px solid ${border}`,
        borderRadius: '6px 6px 0 0',
        fontWeight: 700,
        fontSize: 12,
        color,
        display: 'flex',
        alignItems: 'center',
        gap: 6,
      }}>
        {icon} {label}
      </div>
      <div style={{ border: `1px solid ${border}`, borderTop: 'none', borderRadius: '0 0 6px 6px', background: '#fff' }}>
        {blockItems.length === 0 ? (
          <div style={{ padding: '8px 14px', fontSize: 12, color: '#94a3b8', fontStyle: 'italic' }}>Nessun DPI specifico</div>
        ) : blockItems.map((it, i) => (
          <div key={`${i}_${String(it).slice(0, 20)}`} style={{
            padding: '8px 14px',
            fontSize: 13,
            color: '#334155',
            borderBottom: i < blockItems.length - 1 ? `1px solid ${border}` : 'none',
            lineHeight: 1.5,
          }}>
            🔹 {it.testo}
          </div>
        ))}
      </div>
    </div>
  )

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{
        padding: '12px 14px',
        background: '#ecfdf5',
        border: '1px solid #6ee7b7',
        borderRadius: '8px 8px 0 0',
        fontWeight: 700,
        fontSize: 15,
        color: '#065f46',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <span>🛡️ Dispositivi di protezione (DPI)</span>
        {sourceLabel && <span style={{ fontSize: 10, color: '#6ee7b7', fontWeight: 600 }}>{sourceLabel}</span>}
      </div>
      <div style={{ border: '1px solid #6ee7b7', borderTop: 'none', borderRadius: '0 0 8px 8px', background: '#fff', padding: '10px 10px 2px' }}>
        {renderBlock('Operatore a bordo macchina', '👷', operatore, '#065f46', '#f0fdf4', '#bbf7d0')}
        {renderBlock('Personale a terra (area di influenza)', '🚧', terra, '#92400e', '#fffbeb', '#fde68a')}
      </div>
    </div>
  )
}

// Sezione procedure di emergenza con cascade sorgenti
function ProcedureEmergenzaSection({ items }: { items: SafetyItem[] }) {
  if (!items.length) return null
  const hasTiers = items.some(it => it.source_tier)

  const tierBadge = (item: SafetyItem) => {
    if (!item.source_tier) return null
    const config = {
      manuale: { label: '📖 Manuale', color: '#166534', bg: '#dcfce7' },
      inail:   { label: '🏛 INAIL',  color: '#1e40af', bg: '#dbeafe' },
      ai:      { label: '🤖 AI',     color: '#374151', bg: '#f3f4f6' },
    }[item.source_tier]
    if (!config) return null
    return (
      <span style={{
        fontSize: 9, fontWeight: 700, padding: '2px 6px', borderRadius: 20,
        background: config.bg, color: config.color, letterSpacing: '0.02em', flexShrink: 0,
      }}>
        {config.label}
      </span>
    )
  }

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{
        padding: '12px 14px',
        background: '#fff5f5',
        border: '1px solid #fca5a5',
        borderRadius: '8px 8px 0 0',
        fontWeight: 700,
        fontSize: 15,
        color: '#991b1b',
      }}>
        🚨 Procedure di emergenza
        {hasTiers && (
          <span style={{ fontSize: 10, fontWeight: 400, color: '#b91c1c', marginLeft: 8 }}>
            (fonte: {['📖 Manuale', '🏛 INAIL', '🤖 AI'].join(' → ')})
          </span>
        )}
      </div>
      <div style={{ border: '1px solid #fca5a5', borderTop: 'none', borderRadius: '0 0 8px 8px', background: '#fff' }}>
        {items.map((item, i) => (
          <div key={`${i}_${item.testo?.slice(0, 20) ?? ''}`} style={{ borderBottom: i < items.length - 1 ? '1px solid #fee2e2' : 'none', padding: '10px 14px' }}>
            {item.ai_disclaimer && (
              <div style={{
                background: '#fefce8',
                border: '1px solid #fde047',
                borderRadius: 6,
                padding: '6px 10px',
                marginBottom: 8,
                fontSize: 11,
                color: '#713f12',
                lineHeight: 1.5,
              }}>
                ⚠ Procedura generata da intelligenza artificiale sulla base delle linee guida INAIL. Verificare con il manuale del costruttore prima dell'applicazione.
              </div>
            )}
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
              <div style={{ flex: 1, fontSize: 13, color: '#1e293b', lineHeight: 1.6 }}>{item.testo}</div>
              {tierBadge(item)}
            </div>
            {item.fonte && (
              <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>Fonte: {item.fonte}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// Sezione attrezzature intercambiabili
function AttrezzatureSection({ testo }: { testo: string }) {
  return (
    <div style={{
      background: '#f8fafc',
      border: '1px solid #cbd5e1',
      borderRadius: 8,
      padding: '12px 14px',
      marginBottom: 16,
    }}>
      <div style={{ fontWeight: 700, fontSize: 14, color: '#334155', marginBottom: 6 }}>
        🔩 Interfaccia attrezzature intercambiabili
      </div>
      <p style={{ margin: 0, fontSize: 13, color: '#475569', lineHeight: 1.6 }}>{testo}</p>
    </div>
  )
}

// Focus rischi di categoria INAIL
function FocusRischiSection({ testo, categoria }: { testo: string; categoria?: string }) {
  return (
    <div style={{
      background: '#eff6ff',
      border: '1px solid #bfdbfe',
      borderRadius: 8,
      padding: '12px 14px',
      marginBottom: 16,
    }}>
      <div style={{ fontWeight: 700, fontSize: 14, color: '#1e40af', marginBottom: categoria ? 2 : 6 }}>
        📊 Focus Rischi di Categoria INAIL
      </div>
      {categoria && (
        <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6, fontWeight: 600 }}>
          Categoria: {categoria}
        </div>
      )}
      <p style={{ margin: 0, fontSize: 13, color: '#1e3a8a', lineHeight: 1.6 }}>{testo}</p>
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
            <div key={`${i}_${String(item).slice(0, 20)}`} style={{
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
            <div key={`${i}_${String(norm).slice(0, 20)}`} style={{
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

function ChecklistSection({ items }: { items: (ChecklistItem | string)[] }) {
  const [checked, setChecked] = useState<Set<string>>(new Set())
  const [open, setOpen] = useState(true)

  // Normalizza a oggetti; fallback stringa → livello 2
  const parsed: ChecklistItem[] = items.map((item, i) =>
    typeof item === 'string'
      ? { testo: item, livello: 2 as const, _idx: i } as any
      : { ...item, _idx: i }
  )
  const l1 = parsed.filter(it => it.livello === 1)
  const l2 = parsed.filter(it => it.livello === 2)
  const allItems = [...l1, ...l2]

  const toggle = useCallback((key: string) => {
    setChecked(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }, [])

  if (!items.length) return null

  const done = checked.size
  const total = allItems.length

  const renderItem = (item: ChecklistItem & { _idx: number }, globalIdx: number) => {
    const key = `${item._idx}`
    const isL1 = item.livello === 1
    const isDone = checked.has(key)
    return (
      <label
        key={key}
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 12,
          padding: '10px 14px',
          borderBottom: globalIdx < allItems.length - 1 ? `1px solid ${isL1 ? '#fee2e2' : '#f1f5f9'}` : 'none',
          borderLeft: `3px solid ${isL1 ? '#dc2626' : '#ea580c'}`,
          cursor: 'pointer',
          background: isDone ? '#f0fdf4' : (isL1 ? '#fff5f5' : '#fff'),
          transition: 'background 0.15s',
        }}
      >
        <input
          type="checkbox"
          checked={isDone}
          onChange={() => toggle(key)}
          style={{ marginTop: 2, width: 16, height: 16, accentColor: isL1 ? '#dc2626' : '#ea580c', flexShrink: 0 }}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2, flexWrap: 'wrap' }}>
            <span style={{
              fontSize: 9, fontWeight: 800, padding: '1px 5px', borderRadius: 4,
              background: isL1 ? '#fef2f2' : '#fff7ed',
              color: isL1 ? '#dc2626' : '#ea580c',
              letterSpacing: '0.03em',
              flexShrink: 0,
            }}>
              {isL1 ? 'STOP' : 'PRESCRIZIONE'}
            </span>
            {item.norma && (
              <span style={{ fontSize: 9, color: '#94a3b8', fontFamily: 'monospace' }}>{item.norma}</span>
            )}
          </div>
          <span style={{
            fontSize: 13,
            color: isDone ? '#86efac' : '#334155',
            textDecoration: isDone ? 'line-through' : 'none',
            lineHeight: 1.5,
          }}>
            {item.testo}
          </span>
        </div>
        <ClipboardButton text={item.prescrizione_precompilata} norma={item.norma} />
      </label>
    )
  }

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
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          ✅ Checklist sopralluogo
          {l1.length > 0 && (
            <span style={{ fontSize: 10, fontWeight: 800, padding: '1px 6px', borderRadius: 4, background: '#fef2f2', color: '#dc2626' }}>
              {l1.length} STOP
            </span>
          )}
          {l2.length > 0 && (
            <span style={{ fontSize: 10, fontWeight: 800, padding: '1px 6px', borderRadius: 4, background: '#fff7ed', color: '#ea580c' }}>
              {l2.length} prescrizioni
            </span>
          )}
        </span>
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
          {allItems.map((item, globalIdx) => renderItem(item as any, globalIdx))}
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

function EmptySection({ title, icon }: { title: string; icon: string }) {
  return (
    <div style={{
      border: '1px dashed #cbd5e1',
      borderRadius: 8,
      padding: '12px 16px',
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      opacity: 0.6,
      marginBottom: 16,
    }}>
      <span style={{ fontSize: 18 }}>{icon}</span>
      <div>
        <span style={{ fontWeight: 600, fontSize: 13, color: '#64748b' }}>{title}</span>
        <span style={{ fontSize: 12, color: '#94a3b8', marginLeft: 8 }}>
          ⚪ Nessun dato disponibile per questa sezione
        </span>
      </div>
    </div>
  )
}

const _API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '/api') as string

function buildEmailDraft(card: SafetyCardType, ocr: PlateOCRResult | null, toEmail?: string): string {
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
  const to = toEmail ?? ''
  return `mailto:${to}?subject=${subject}&body=${body}`
}

const STORAGE_KEY = 'safetycard_view_mode'

export function SafetyCard({ card, ocr, onNewSearch }: Props) {
  const isFallback = card.fonte_tipo === 'fallback_ai'
  const [fetchingEmail, setFetchingEmail] = useState(false)
  const [viewMode, setViewMode] = useState<'cantiere' | 'ufficio'>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      return saved === 'ufficio' ? 'ufficio' : 'cantiere'
    } catch { return 'cantiere' }
  })
  const [isPrinting, setIsPrinting] = useState(false)

  const switchMode = (mode: 'cantiere' | 'ufficio') => {
    setViewMode(mode)
    try { localStorage.setItem(STORAGE_KEY, mode) } catch {}
  }

  async function handleEmailRequest() {
    setFetchingEmail(true)
    try {
      const res = await fetch(
        `${_API_BASE}/machine-types/manufacturer-email?brand=${encodeURIComponent(card.brand)}&model=${encodeURIComponent(card.model)}`
      )
      const data = res.ok ? await res.json() : { email: null }
      window.open(buildEmailDraft(card, ocr, data.email ?? undefined), '_blank')
    } catch {
      // Fallback silenzioso: apre mailto: senza destinatario
      window.open(buildEmailDraft(card, ocr), '_blank')
    } finally {
      setFetchingEmail(false)
    }
  }

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
          {card.vita_utile_anni != null && (
            <span style={{ fontSize: 12, opacity: 0.85, background: 'rgba(255,255,255,0.2)', padding: '1px 7px', borderRadius: 8 }}>
              ⏳ Vita utile stimata: {card.vita_utile_anni} anni
            </span>
          )}
          {ocr && <ConfidenceBadge confidence={ocr.confidence} />}
        </div>

        {/* Banner Fine Vita */}
        {(() => {
          if (!card.vita_utile_anni || !card.machine_year) return null
          const endYear = parseInt(card.machine_year) + card.vita_utile_anni
          if (endYear > new Date().getFullYear()) return null
          return (
            <div style={{
              background: 'rgba(254,242,242,0.95)', border: '1px solid #fca5a5',
              borderRadius: 8, padding: '10px 14px', marginTop: 12,
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              <span style={{ fontSize: 18 }}>⚠️</span>
              <div>
                <span style={{ fontWeight: 700, color: '#dc2626', fontSize: 13 }}>
                  POTENZIALE FINE VITA
                </span>
                <span style={{ color: '#7f1d1d', fontSize: 12, marginLeft: 8 }}>
                  Costruzione {card.machine_year} · Vita utile stimata {card.vita_utile_anni} anni · Scadenza presunta {endYear}
                </span>
              </div>
            </div>
          )
        })()}

        {/* Toggle Sede operativa / Ufficio */}
        <div style={{
          display: 'flex', borderRadius: 8, overflow: 'hidden',
          border: '1px solid rgba(255,255,255,0.3)', width: 'fit-content', marginTop: 12,
        }}>
          {(['cantiere', 'ufficio'] as const).map(mode => (
            <button
              key={mode}
              onClick={() => switchMode(mode)}
              style={{
                padding: '6px 18px', fontWeight: 600, fontSize: 13,
                border: 'none', cursor: 'pointer',
                background: viewMode === mode ? 'rgba(255,255,255,0.25)' : 'transparent',
                color: '#fff',
              }}
            >
              {mode === 'cantiere' ? '🏗️ Sede operativa' : '🏢 Ufficio'}
            </button>
          ))}
        </div>
      </div>

      {/* Badge fonte strategia A–F + disclaimer */}
      {card.source_metadata && (
        <SourceBadgeBar source={card.source_metadata} />
      )}
      <DisclaimerBanner source={card.source_metadata} />

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
            <div key={`${i}_${alert.risk_level}_${alert.title?.slice(0, 16) ?? ''}`} style={{
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

      {/* Focus rischi di categoria INAIL — visibile in entrambe le viste */}
      {card.focus_rischi_categoria && (
        <FocusRischiSection testo={card.focus_rischi_categoria} categoria={card.categoria_inail ?? undefined} />
      )}

      {/* ── VISTA CANTIERE ─────────────────────────────────────────── */}
      {(viewMode === 'cantiere' || isPrinting) && (
        <div data-section="cantiere">
          {(card.checklist ?? []).length > 0
            ? <ChecklistSection items={card.checklist ?? []} />
            : <EmptySection title="Checklist sopralluogo" icon="✅" />}
          {(card.documenti_da_richiedere ?? []).length > 0
            ? <DocumentiSection items={card.documenti_da_richiedere ?? []} />
            : <EmptySection title="Documenti da richiedere" icon="📄" />}
        </div>
      )}

      {/* ── VISTA UFFICIO ──────────────────────────────────────────── */}
      {(viewMode === 'ufficio' || isPrinting) && (
        <div data-section="ufficio">
          {/* Normative applicabili (collapsed di default) */}
          <NormativeSection items={card.normative_applicabili ?? []} />

          {/* Rischi principali */}
          {card.rischi_principali?.length > 0
            ? <Section title="Rischi principali" items={card.rischi_principali} variant="risk" icon="⚠️" sourceLabel={card.fonte_rischi ?? undefined} />
            : <EmptySection title="Rischi principali" icon="⚠️" />}

          {/* Dispositivi di protezione */}
          {card.dispositivi_protezione?.length > 0
            ? <DPISection items={card.dispositivi_protezione} sourceLabel={card.fonte_protezione ?? undefined} />
            : <EmptySection title="Dispositivi di protezione" icon="🛡️" />}

          {/* Dispositivi di sicurezza */}
          {(card.dispositivi_sicurezza ?? []).length > 0 && (
            <DispositiviSicurezzaSection items={card.dispositivi_sicurezza ?? []} />
          )}

          {/* Raccomandazioni produttore */}
          {card.raccomandazioni_produttore?.length > 0
            ? <Section title="Raccomandazioni del produttore" items={card.raccomandazioni_produttore} variant="recommendation" icon="📋" sourceLabel={card.fonte_raccomandazioni ?? undefined} />
            : <EmptySection title="Raccomandazioni del produttore" icon="📋" />}

          {/* Limiti operativi */}
          {(card.limiti_operativi ?? []).length > 0 && (
            <Section title="Limiti operativi" items={card.limiti_operativi ?? []} variant="recommendation" icon="⚙️" />
          )}

          {/* Attrezzature intercambiabili: null = non applicabile, "" = cercato ma non trovato */}
          {card.attrezzature_intercambiabili !== null && card.attrezzature_intercambiabili !== undefined && (
            card.attrezzature_intercambiabili
              ? <AttrezzatureSection testo={card.attrezzature_intercambiabili} />
              : <EmptySection title="Attrezzature intercambiabili" icon="🔩" />
          )}

          {/* Procedure di emergenza */}
          <ProcedureEmergenzaSection items={card.procedure_emergenza ?? []} />

          {/* Rischi residui */}
          {card.rischi_residui?.length > 0
            ? <Section title="Rischi residui" items={card.rischi_residui} variant="residual" icon="🔶" sourceLabel={card.fonte_residui ?? undefined} />
            : <EmptySection title="Rischi residui" icon="🔶" />}

          {/* Pittogrammi da verificare fisicamente sulla macchina */}
          <PittogrammiSection items={card.pittogrammi_sicurezza ?? []} />
        </div>
      )}

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
      <ManualLink url={card.fonte_manuale} inailUrl={card.fonte_inail} tipo={card.fonte_tipo} brand={card.brand} model={card.model} machineType={card.machine_type ?? undefined} machineTypeId={card.machine_type_id ?? undefined} />

      {/* Footer con data */}
      <p style={{
        textAlign: 'center',
        fontSize: 11,
        color: '#94a3b8',
        margin: '12px 0',
      }}>
        Scheda generata il {new Date(card.generated_at).toLocaleString('it-IT')}
      </p>

      {/* Feedback ispettori */}
      <FeedbackWidget card={card} />

      {/* Azioni */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 8 }}>
        <ExportButton
          card={card}
          onBeforeExport={() => setIsPrinting(true)}
          onAfterExport={() => setIsPrinting(false)}
        />
        <button
          onClick={handleEmailRequest}
          disabled={fetchingEmail}
          style={{
            display: 'block',
            width: '100%',
            padding: '14px',
            background: fetchingEmail ? '#fef9c3' : '#fffbeb',
            color: '#92400e',
            border: '2px solid #fde68a',
            borderRadius: 8,
            fontSize: 15,
            fontWeight: 700,
            cursor: fetchingEmail ? 'wait' : 'pointer',
            textAlign: 'center',
            boxSizing: 'border-box',
          }}
        >
          {fetchingEmail ? '⏳ Ricerca email produttore...' : '✉ Richiedi documentazione al produttore'}
        </button>
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
