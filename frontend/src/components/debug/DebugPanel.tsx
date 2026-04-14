import { useState, useRef, useEffect } from 'react'
import type { DebugEvent } from '../../types'

const CATEGORY_ICON: Record<string, string> = {
  search:   '🔍',
  download: '📥',
  ai:       '🤖',
  analysis: '📊',
  error:    '❌',
  warning:  '⚠️',
}

const LEVEL_COLOR: Record<string, string> = {
  info:    '#1e293b',
  warning: '#92400e',
  error:   '#991b1b',
}

const LEVEL_BG: Record<string, string> = {
  info:    'transparent',
  warning: '#fef9c3',
  error:   '#fee2e2',
}

type FilterCategory = 'all' | DebugEvent['category']

interface Props {
  events: DebugEvent[]
  onClear: () => void
}

export function DebugPanel({ events, onClear }: Props) {
  const [collapsed, setCollapsed] = useState(false)
  const [filter, setFilter] = useState<FilterCategory>('all')
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())
  const bodyRef = useRef<HTMLDivElement>(null)

  // Auto-scroll al fondo quando arrivano nuovi eventi
  useEffect(() => {
    if (!collapsed && bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight
    }
  }, [events.length, collapsed])

  const filtered = filter === 'all' ? events : events.filter(e => e.category === filter)

  const counts: Partial<Record<DebugEvent['category'], number>> = {}
  for (const e of events) {
    counts[e.category] = (counts[e.category] ?? 0) + 1
  }
  const errorCount = events.filter(e => e.level === 'error').length
  const warnCount  = events.filter(e => e.level === 'warning').length

  function toggleExpand(id: number) {
    setExpandedIds(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function copyAll() {
    const text = events.map(e =>
      `[${e.ts.substring(11, 19)}] [${e.category.toUpperCase()}] [${e.level.toUpperCase()}] ${e.message}\n` +
      (Object.keys(e.details).length > 0 ? JSON.stringify(e.details, null, 2) + '\n' : '')
    ).join('\n')
    navigator.clipboard.writeText(text).catch(() => {})
  }

  const FILTERS: { key: FilterCategory; label: string }[] = [
    { key: 'all',      label: 'Tutti' },
    { key: 'search',   label: '🔍 Ricerca' },
    { key: 'download', label: '📥 Download' },
    { key: 'ai',       label: '🤖 AI' },
    { key: 'analysis', label: '📊 Analisi' },
    { key: 'warning',  label: '⚠️ Warning' },
    { key: 'error',    label: '❌ Errori' },
  ]

  return (
    <div style={{
      position: 'fixed', bottom: 0, left: 0, right: 0,
      zIndex: 9999,
      fontFamily: 'monospace',
      fontSize: 12,
      boxShadow: '0 -2px 12px rgba(0,0,0,0.18)',
      background: '#0f172a',
      color: '#e2e8f0',
      maxHeight: collapsed ? 38 : '42vh',
      transition: 'max-height 0.2s ease',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '0 10px', height: 38, flexShrink: 0,
        borderBottom: collapsed ? 'none' : '1px solid #1e293b',
        cursor: 'pointer',
        userSelect: 'none',
      }}
        onClick={() => setCollapsed(c => !c)}
      >
        <span style={{ fontWeight: 700, color: '#38bdf8', marginRight: 4 }}>🔧 Debug Panel</span>

        {/* Badge contatori */}
        {counts.search   && <Chip color="#2563eb">{CATEGORY_ICON.search} {counts.search}</Chip>}
        {counts.download && <Chip color="#7c3aed">{CATEGORY_ICON.download} {counts.download}</Chip>}
        {counts.ai       && <Chip color="#0891b2">{CATEGORY_ICON.ai} {counts.ai}</Chip>}
        {warnCount  > 0  && <Chip color="#d97706">⚠️ {warnCount}</Chip>}
        {errorCount > 0  && <Chip color="#dc2626">❌ {errorCount}</Chip>}

        <span style={{ flex: 1 }} />

        {/* Pulsanti — stopPropagation per non collassare/espandere */}
        <button
          onClick={e => { e.stopPropagation(); copyAll() }}
          style={btnStyle}
          title="Copia tutti i log"
        >Copia</button>
        <button
          onClick={e => { e.stopPropagation(); onClear() }}
          style={{ ...btnStyle, color: '#f87171' }}
          title="Cancella log"
        >Clear</button>
        <span style={{ color: '#64748b', fontSize: 14, marginLeft: 4 }}>
          {collapsed ? '▲' : '▼'}
        </span>
      </div>

      {/* Body */}
      {!collapsed && (
        <>
          {/* Tab filtri */}
          <div style={{
            display: 'flex', gap: 4, padding: '4px 8px',
            flexShrink: 0, borderBottom: '1px solid #1e293b',
            overflowX: 'auto',
          }}>
            {FILTERS.map(f => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                style={{
                  padding: '2px 8px', borderRadius: 10, border: 'none', cursor: 'pointer',
                  background: filter === f.key ? '#38bdf8' : '#1e293b',
                  color: filter === f.key ? '#0f172a' : '#94a3b8',
                  fontFamily: 'monospace', fontSize: 11, whiteSpace: 'nowrap',
                  fontWeight: filter === f.key ? 700 : 400,
                }}
              >{f.label}</button>
            ))}
          </div>

          {/* Lista eventi */}
          <div ref={bodyRef} style={{
            overflowY: 'auto', flex: 1,
            padding: '4px 0',
          }}>
            {filtered.length === 0 ? (
              <div style={{ padding: '12px 12px', color: '#475569', fontStyle: 'italic' }}>
                Nessun evento. Esegui una scansione per vedere i log.
              </div>
            ) : (
              filtered.map(ev => (
                <DebugRow
                  key={ev.id}
                  event={ev}
                  expanded={expandedIds.has(ev.id)}
                  onToggle={() => toggleExpand(ev.id)}
                />
              ))
            )}
          </div>
        </>
      )}
    </div>
  )
}

function DebugRow({ event, expanded, onToggle }: {
  event: DebugEvent
  expanded: boolean
  onToggle: () => void
}) {
  const ts = event.ts.substring(11, 19)
  const icon = CATEGORY_ICON[event.category] ?? '•'
  const color = LEVEL_COLOR[event.level] ?? '#e2e8f0'
  const bg = LEVEL_BG[event.level] ?? 'transparent'
  const hasDetails = Object.keys(event.details).filter(k => k !== 'category').length > 0

  return (
    <div
      onClick={hasDetails ? onToggle : undefined}
      style={{
        padding: '3px 10px',
        background: bg,
        borderBottom: '1px solid #1e293b',
        cursor: hasDetails ? 'pointer' : 'default',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ color: '#475569', flexShrink: 0 }}>{ts}</span>
        <span style={{ flexShrink: 0 }}>{icon}</span>
        <span style={{ color, lineHeight: 1.4 }}>{event.message}</span>
        {hasDetails && (
          <span style={{ color: '#475569', flexShrink: 0, marginLeft: 'auto' }}>
            {expanded ? '▲' : '▼'}
          </span>
        )}
      </div>

      {expanded && hasDetails && (
        <pre style={{
          margin: '4px 0 2px 20px',
          padding: '6px 8px',
          background: '#1e293b',
          borderRadius: 4,
          color: '#93c5fd',
          fontSize: 11,
          overflowX: 'auto',
          maxHeight: 200,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-all',
        }}>
          {JSON.stringify(
            Object.fromEntries(Object.entries(event.details).filter(([k]) => k !== 'category')),
            null, 2
          )}
        </pre>
      )}
    </div>
  )
}

function Chip({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span style={{
      background: color + '22', color, border: `1px solid ${color}55`,
      borderRadius: 10, padding: '1px 7px', fontSize: 11, whiteSpace: 'nowrap',
    }}>
      {children}
    </span>
  )
}

const btnStyle: React.CSSProperties = {
  padding: '2px 8px', borderRadius: 6, border: '1px solid #334155',
  background: '#1e293b', color: '#94a3b8', cursor: 'pointer',
  fontFamily: 'monospace', fontSize: 11,
}
