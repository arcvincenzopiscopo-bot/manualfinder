/**
 * Pannello amministratore — Catalogo Tipi Macchina
 * Accesso: /#admin
 *
 * Sezioni:
 *   1. Statistiche generali
 *   2. Proposte pending (approva / alias / rifiuta)
 *   3. Gestione alias per tipo
 *   4. Modifica flags normativi
 */
import { useState, useEffect, useCallback } from 'react'
import type { MachineType } from '../../types'

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '/api') as string

// ── API calls ────────────────────────────────────────────────────────────────

async function apiFetch(path: string, opts?: RequestInit) {
  const r = await fetch(`${BASE_URL}/machine-types${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!r.ok) {
    const t = await r.text().catch(() => r.statusText)
    throw new Error(`HTTP ${r.status}: ${t}`)
  }
  return r.json()
}

// ── Tipi locali ───────────────────────────────────────────────────────────────

interface Stats {
  total_types: number
  total_aliases: number
  pending_count: number
  top_types: Array<{ id: number; name: string; usage_count: number; requires_patentino: boolean; requires_verifiche: boolean }>
  stale_pending: Array<{ proposed_name: string; proposed_by: string | null; created_at: string }>
}

interface Pending {
  id: number
  proposed_name: string
  proposed_by: string | null
  resolution: string
  ai_similarity_score: number | null
  suggested_merge_name: string | null
  created_at: string
}

interface Alias {
  id: number
  alias_text: string
  source: string
  created_at: string
}

// ── Colori / stili condivisi ──────────────────────────────────────────────────

const COLORS = {
  bg: '#f8fafc',
  card: '#fff',
  border: '#e2e8f0',
  primary: '#1e40af',
  danger: '#dc2626',
  success: '#16a34a',
  warn: '#d97706',
  muted: '#64748b',
  text: '#1e293b',
}

const card: React.CSSProperties = {
  background: COLORS.card,
  border: `1px solid ${COLORS.border}`,
  borderRadius: 10,
  padding: '16px 18px',
  marginBottom: 16,
}

const btn = (variant: 'primary' | 'danger' | 'ghost' | 'success' | 'warn' = 'primary',
             small = false): React.CSSProperties => ({
  padding: small ? '4px 10px' : '8px 16px',
  borderRadius: 6,
  border: 'none',
  fontWeight: 600,
  fontSize: small ? 12 : 13,
  cursor: 'pointer',
  background: variant === 'primary' ? COLORS.primary
            : variant === 'danger'  ? COLORS.danger
            : variant === 'success' ? COLORS.success
            : variant === 'warn'    ? COLORS.warn
            : '#f1f5f9',
  color: variant === 'ghost' ? COLORS.text : '#fff',
})

const input: React.CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  border: `1px solid ${COLORS.border}`,
  borderRadius: 6,
  fontSize: 13,
  boxSizing: 'border-box',
  color: COLORS.text,
}

const badge = (color: string, bg: string): React.CSSProperties => ({
  display: 'inline-block',
  padding: '2px 8px',
  borderRadius: 20,
  fontSize: 11,
  fontWeight: 700,
  color,
  background: bg,
})

// ── Componente principale ─────────────────────────────────────────────────────

export function AdminPanel() {
  const [tab, setTab] = useState<'stats' | 'pending' | 'diskproposals' | 'aliases' | 'flags' | 'scans' | 'log'>('stats')

  return (
    <div style={{ background: COLORS.bg, minHeight: '100vh', padding: '0 0 40px' }}>
      {/* Header */}
      <div style={{
        background: '#1e293b',
        padding: '14px 20px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
      }}>
        <span style={{ fontSize: 22 }}>⚙️</span>
        <div>
          <div style={{ color: '#fff', fontWeight: 800, fontSize: 16 }}>Admin — Catalogo Tipi Macchina</div>
          <div style={{ color: '#94a3b8', fontSize: 12 }}>ManualFinder</div>
        </div>
        <a
          href="/"
          style={{ marginLeft: 'auto', color: '#94a3b8', fontSize: 13, textDecoration: 'none' }}
        >
          ← App
        </a>
      </div>

      {/* Tab bar */}
      <div style={{
        display: 'flex',
        borderBottom: `2px solid ${COLORS.border}`,
        background: '#fff',
        padding: '0 16px',
      }}>
        {([
          { id: 'stats',   label: '📊 Statistiche' },
          { id: 'pending',       label: '⏳ Proposte' },
          { id: 'diskproposals', label: '💾 Proposte disco' },
          { id: 'aliases',       label: '🔗 Alias' },
          { id: 'flags',   label: '⚖️ Flags normativi' },
          { id: 'scans',   label: '📨 Ricerche' },
          { id: 'log',     label: '🗂 Log scansioni' },
        ] as const).map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              background: 'none',
              border: 'none',
              borderBottom: tab === t.id ? `3px solid ${COLORS.primary}` : '3px solid transparent',
              padding: '12px 14px',
              fontWeight: tab === t.id ? 700 : 500,
              color: tab === t.id ? COLORS.primary : COLORS.muted,
              cursor: 'pointer',
              fontSize: 13,
              marginBottom: -2,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div style={{ padding: '16px' }}>
        {tab === 'stats'   && <TabStats />}
        {tab === 'pending'       && <TabPending />}
        {tab === 'diskproposals' && <TabDiskProposals />}
        {tab === 'aliases'       && <TabAliases />}
        {tab === 'flags'   && <TabFlags />}
        {tab === 'scans'   && <TabScans />}
        {tab === 'log'     && <TabLog />}
      </div>
    </div>
  )
}

// ── Tab 1: Statistiche ────────────────────────────────────────────────────────

function TabStats() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    apiFetch('/admin/stats')
      .then(setStats)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) return <LoadingSpinner />
  if (error) return <ErrorBox message={error} onRetry={load} />
  if (!stats) return null

  return (
    <div>
      {/* KPI row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12, marginBottom: 16 }}>
        <KpiCard value={stats.total_types} label="Tipi canonici" color={COLORS.primary} />
        <KpiCard value={stats.total_aliases} label="Alias totali" color={COLORS.success} />
        <KpiCard value={stats.pending_count} label="Proposte in attesa" color={stats.pending_count > 0 ? COLORS.warn : COLORS.muted} />
      </div>

      {/* Top 10 tipi */}
      <div style={card}>
        <SectionTitle>Top 10 tipi per utilizzo</SectionTitle>
        {stats.top_types.length === 0
          ? <EmptyState>Nessun utilizzo registrato.</EmptyState>
          : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${COLORS.border}` }}>
                <Th>Tipo macchina</Th>
                <Th right>Utilizzi</Th>
                <Th>Patentino</Th>
                <Th>Verifiche</Th>
              </tr>
            </thead>
            <tbody>
              {stats.top_types.map(t => (
                <tr key={t.id} style={{ borderBottom: `1px solid #f1f5f9` }}>
                  <Td>{t.name}</Td>
                  <Td right><strong>{t.usage_count}</strong></Td>
                  <Td>{t.requires_patentino ? <YesBadge /> : <NoBadge />}</Td>
                  <Td>{t.requires_verifiche ? <YesBadge /> : <NoBadge />}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Proposte stale */}
      {stats.stale_pending.length > 0 && (
        <div style={{ ...card, border: `1px solid #fde68a`, background: '#fffbeb' }}>
          <SectionTitle>⚠️ Proposte in attesa da più di 7 giorni</SectionTitle>
          {stats.stale_pending.map((p, i) => (
            <div key={i} style={{ fontSize: 13, padding: '4px 0', color: COLORS.text }}>
              <strong>"{p.proposed_name}"</strong>
              <span style={{ color: COLORS.muted, marginLeft: 8 }}>
                {p.proposed_by ? `da ${p.proposed_by} — ` : ''}{fmtDate(p.created_at)}
              </span>
            </div>
          ))}
          <p style={{ fontSize: 12, color: COLORS.warn, marginTop: 8 }}>
            Vai alla tab "Proposte" per risolverle.
          </p>
        </div>
      )}

      <button onClick={load} style={btn('ghost')}>↺ Aggiorna</button>
    </div>
  )
}

// ── Tab 2: Proposte pending ───────────────────────────────────────────────────

function TabPending() {
  const [pending, setPending] = useState<Pending[]>([])
  const [types, setTypes]     = useState<MachineType[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)
  const [working, setWorking] = useState<number | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    Promise.all([
      apiFetch('/admin/pending'),
      apiFetch(''),
    ])
      .then(([p, t]) => { setPending(p); setTypes(t) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const resolve = async (id: number, body: object) => {
    setWorking(id)
    try {
      await apiFetch(`/admin/pending/${id}/resolve`, {
        method: 'POST',
        body: JSON.stringify(body),
      })
      load()
    } catch (e: any) {
      alert(`Errore: ${e.message}`)
    } finally {
      setWorking(null)
    }
  }

  if (loading) return <LoadingSpinner />
  if (error)   return <ErrorBox message={error} onRetry={load} />

  if (pending.length === 0) {
    return (
      <div style={card}>
        <EmptyState>✅ Nessuna proposta in attesa.</EmptyState>
      </div>
    )
  }

  return (
    <div>
      <p style={{ fontSize: 13, color: COLORS.muted, marginBottom: 12 }}>
        {pending.length} proposta{pending.length !== 1 ? 'e' : ''} in attesa. Per ognuna scegli come risolverla.
      </p>
      {pending.map(p => (
        <PendingCard
          key={p.id}
          pending={p}
          types={types}
          working={working === p.id}
          onAlias={(mergeId)  => resolve(p.id, { action: 'alias', merge_into_id: mergeId })}
          onPromote={(name, pat, ver) => resolve(p.id, {
            action: 'promote',
            new_type_name: name,
            new_requires_patentino: pat,
            new_requires_verifiche: ver,
          })}
          onReject={() => resolve(p.id, { action: 'reject' })}
        />
      ))}
    </div>
  )
}

// ── Tab: Proposte da disco ────────────────────────────────────────────────────

type DiskProposal = { id: number; proposed_name: string; inail_hint: string | null; created_at: string }

function TabDiskProposals() {
  const [proposals, setProposals] = useState<DiskProposal[]>([])
  const [loading, setLoading]     = useState(true)
  const [scanning, setScanning]   = useState(false)
  const [working, setWorking]     = useState<number | null>(null)
  const [editNames, setEditNames] = useState<Record<number, string>>({})
  const [msg, setMsg]             = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    apiFetch('/admin/disk-proposals')
      .then(setProposals)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const scan = async () => {
    setScanning(true)
    setMsg(null)
    try {
      const res = await apiFetch('/admin/propose-from-disk', { method: 'POST' })
      setMsg(`✅ ${res.proposed} nuove proposte create, ${res.already_exists ?? 0} già presenti.`)
      load()
    } catch (e: any) {
      setMsg(`❌ ${e.message}`)
    } finally {
      setScanning(false)
    }
  }

  const resolve = async (id: number, action: 'approve' | 'reject') => {
    setWorking(id)
    try {
      const final_name = editNames[id]?.trim() || undefined
      await apiFetch(`/admin/disk-proposals/${id}/resolve`, {
        method: 'POST',
        body: JSON.stringify({ action, final_name }),
      })
      load()
    } catch (e: any) {
      alert(`Errore: ${e.message}`)
    } finally {
      setWorking(null)
    }
  }

  return (
    <div>
      {/* Azioni globali */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 16, flexWrap: 'wrap' }}>
        <button
          onClick={scan}
          disabled={scanning}
          style={{ background: COLORS.primary, color: '#fff', border: 'none', borderRadius: 6,
            padding: '8px 16px', fontWeight: 700, cursor: scanning ? 'default' : 'pointer', fontSize: 13 }}
        >
          {scanning ? '⏳ Scansiono...' : '🔍 Scansiona nuovi file su disco'}
        </button>
        <button onClick={load} style={{ background: 'none', border: `1px solid ${COLORS.border}`,
          borderRadius: 6, padding: '7px 12px', cursor: 'pointer', fontSize: 13, color: COLORS.muted }}>
          🔄 Ricarica
        </button>
        {msg && <span style={{ fontSize: 13, color: msg.startsWith('✅') ? '#16a34a' : '#dc2626' }}>{msg}</span>}
      </div>

      {loading ? <LoadingSpinner /> : proposals.length === 0 ? (
        <div style={card}>
          <EmptyState>
            Nessuna proposta in attesa.<br />
            <span style={{ fontSize: 12, color: COLORS.muted }}>
              Aggiungi file PDF nella cartella <code>pdf manuali</code> e clicca "Scansiona".
            </span>
          </EmptyState>
        </div>
      ) : (
        <div>
          <p style={{ fontSize: 13, color: COLORS.muted, marginBottom: 12 }}>
            {proposals.length} proposta{proposals.length !== 1 ? 'e' : ''} da file rilevati su disco.
            Approva per creare una nuova categoria, rifiuta per ignorare il file.
          </p>
          {proposals.map(p => (
            <div key={p.id} style={{ ...card, marginBottom: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
                <div style={{ flex: 1, minWidth: 200 }}>
                  <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 2 }}>
                    {p.proposed_name}
                  </div>
                  {p.inail_hint && (
                    <div style={{ fontSize: 12, color: COLORS.muted }}>
                      📄 {p.inail_hint}
                    </div>
                  )}
                  <div style={{ fontSize: 11, color: COLORS.muted, marginTop: 2 }}>
                    Rilevato il {fmtDate(p.created_at)}
                  </div>
                </div>
                {/* Nome editabile */}
                <input
                  value={editNames[p.id] ?? p.proposed_name}
                  onChange={e => setEditNames(n => ({ ...n, [p.id]: e.target.value }))}
                  placeholder="Nome categoria finale..."
                  style={{ ...input, width: 220, marginBottom: 0 }}
                />
                <button
                  disabled={working === p.id}
                  onClick={() => resolve(p.id, 'approve')}
                  style={{ background: '#16a34a', color: '#fff', border: 'none', borderRadius: 6,
                    padding: '7px 14px', fontWeight: 700, cursor: 'pointer', fontSize: 13 }}
                >
                  ✅ Approva
                </button>
                <button
                  disabled={working === p.id}
                  onClick={() => resolve(p.id, 'reject')}
                  style={{ background: 'none', border: `1px solid #dc2626`, color: '#dc2626',
                    borderRadius: 6, padding: '7px 14px', fontWeight: 600, cursor: 'pointer', fontSize: 13 }}
                >
                  ✗ Rifiuta
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}


function PendingCard({ pending, types, working, onAlias, onPromote, onReject }: {
  pending: Pending
  types: MachineType[]
  working: boolean
  onAlias: (mergeId: number) => void
  onPromote: (name: string, pat: boolean, ver: boolean) => void
  onReject: () => void
}) {
  const [action, setAction] = useState<'alias' | 'promote' | 'reject' | null>(null)
  const [mergeId, setMergeId] = useState<number | ''>('')
  const [promoteName, setPromoteName] = useState(pending.proposed_name)
  const [pat, setPat] = useState(true)
  const [ver, setVer] = useState(true)

  const daysOld = Math.floor((Date.now() - new Date(pending.created_at).getTime()) / 86400000)

  return (
    <div style={{ ...card, borderLeft: `4px solid ${daysOld > 7 ? COLORS.warn : COLORS.primary}` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div>
          <span style={{ fontWeight: 700, fontSize: 15, color: COLORS.text }}>
            "{pending.proposed_name}"
          </span>
          {pending.proposed_by && (
            <span style={{ marginLeft: 8, fontSize: 12, color: COLORS.muted }}>
              da {pending.proposed_by}
            </span>
          )}
        </div>
        <span style={{ fontSize: 11, color: COLORS.muted }}>{fmtDate(pending.created_at)}</span>
      </div>

      {pending.suggested_merge_name && (
        <div style={{ fontSize: 12, color: COLORS.warn, marginBottom: 8 }}>
          💡 Simile a: <strong>{pending.suggested_merge_name}</strong>
          {pending.ai_similarity_score != null && ` (score: ${(pending.ai_similarity_score * 100).toFixed(0)}%)`}
        </div>
      )}

      {/* Pulsanti azione */}
      {!action && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button onClick={() => setAction('alias')}   style={btn('primary', true)}>🔗 Salva come alias</button>
          <button onClick={() => setAction('promote')} style={btn('success', true)}>✅ Nuovo tipo canonico</button>
          <button onClick={() => setAction('reject')}  style={btn('danger', true)}>🗑 Rifiuta</button>
        </div>
      )}

      {/* Form alias */}
      {action === 'alias' && (
        <div style={{ marginTop: 10, background: '#f0f9ff', borderRadius: 8, padding: 12 }}>
          <label style={labelStyle}>Tipo esistente a cui aggiungere come alias:</label>
          <select
            value={mergeId}
            onChange={e => setMergeId(Number(e.target.value))}
            style={{ ...input, marginBottom: 10 }}
          >
            <option value="">— seleziona tipo —</option>
            {types.map(t => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              disabled={!mergeId || working}
              onClick={() => mergeId && onAlias(mergeId as number)}
              style={btn('primary', true)}
            >
              {working ? '...' : 'Conferma alias'}
            </button>
            <button onClick={() => setAction(null)} style={btn('ghost', true)}>Annulla</button>
          </div>
        </div>
      )}

      {/* Form promote */}
      {action === 'promote' && (
        <div style={{ marginTop: 10, background: '#f0fdf4', borderRadius: 8, padding: 12 }}>
          <label style={labelStyle}>Nome canonico (modifica se necessario):</label>
          <input
            style={{ ...input, marginBottom: 10 }}
            value={promoteName}
            onChange={e => setPromoteName(e.target.value)}
          />
          <div style={{ display: 'flex', gap: 16, marginBottom: 10 }}>
            <CheckLabel
              checked={pat}
              onChange={setPat}
              label="Richiede patentino / abilitazione"
            />
            <CheckLabel
              checked={ver}
              onChange={setVer}
              label="Richiede verifiche periodiche"
            />
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              disabled={!promoteName.trim() || working}
              onClick={() => onPromote(promoteName.trim(), pat, ver)}
              style={btn('success', true)}
            >
              {working ? '...' : 'Crea tipo canonico'}
            </button>
            <button onClick={() => setAction(null)} style={btn('ghost', true)}>Annulla</button>
          </div>
        </div>
      )}

      {/* Confirm reject */}
      {action === 'reject' && (
        <div style={{ marginTop: 10, background: '#fef2f2', borderRadius: 8, padding: 12 }}>
          <p style={{ fontSize: 13, color: COLORS.danger, margin: '0 0 8px' }}>
            Confermi il rifiuto di "{pending.proposed_name}"?
          </p>
          <div style={{ display: 'flex', gap: 8 }}>
            <button disabled={working} onClick={onReject} style={btn('danger', true)}>
              {working ? '...' : 'Sì, rifiuta'}
            </button>
            <button onClick={() => setAction(null)} style={btn('ghost', true)}>Annulla</button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Tab 3: Alias ──────────────────────────────────────────────────────────────

function TabAliases() {
  const [types, setTypes]     = useState<MachineType[]>([])
  const [selectedId, setSelectedId] = useState<number | ''>('')
  const [aliases, setAliases] = useState<Alias[]>([])
  const [newAlias, setNewAlias] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving]   = useState(false)
  const [error, setError]     = useState<string | null>(null)
  const [msg, setMsg]         = useState<string | null>(null)

  useEffect(() => {
    apiFetch('').then(setTypes).catch(e => setError(e.message))
  }, [])

  const loadAliases = useCallback((id: number) => {
    setLoading(true)
    setMsg(null)
    apiFetch(`/${id}/aliases`)
      .then(setAliases)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const handleSelectType = (id: number) => {
    setSelectedId(id)
    setAliases([])
    setNewAlias('')
    loadAliases(id)
  }

  const handleAdd = async () => {
    if (!selectedId || !newAlias.trim()) return
    setSaving(true)
    setMsg(null)
    try {
      await apiFetch(`/${selectedId}/aliases`, {
        method: 'POST',
        body: JSON.stringify({ alias_text: newAlias.trim() }),
      })
      setNewAlias('')
      setMsg('✅ Alias aggiunto.')
      loadAliases(selectedId as number)
    } catch (e: any) {
      if (e.message.includes('409')) setMsg('⚠️ Alias già esistente.')
      else setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (aliasId: number, text: string) => {
    if (!confirm(`Eliminare l'alias "${text}"?`)) return
    try {
      await apiFetch(`/aliases/${aliasId}`, { method: 'DELETE' })
      setMsg('✅ Alias eliminato.')
      if (selectedId) loadAliases(selectedId as number)
    } catch (e: any) {
      setError(e.message)
    }
  }

  return (
    <div>
      {error && <ErrorBox message={error} onRetry={() => setError(null)} />}

      <div style={card}>
        <SectionTitle>Seleziona tipo macchina</SectionTitle>
        <select
          value={selectedId}
          onChange={e => e.target.value && handleSelectType(Number(e.target.value))}
          style={{ ...input, marginBottom: 0 }}
        >
          <option value="">— scegli un tipo —</option>
          {types.map(t => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>
      </div>

      {selectedId !== '' && (
        <div style={card}>
          <SectionTitle>Alias di "{types.find(t => t.id === selectedId)?.name}"</SectionTitle>

          {/* Aggiungi alias */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
            <input
              style={{ ...input }}
              placeholder="Nuovo alias (es. muletto, forklift…)"
              value={newAlias}
              onChange={e => setNewAlias(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleAdd()}
            />
            <button
              onClick={handleAdd}
              disabled={saving || !newAlias.trim()}
              style={{ ...btn('primary'), whiteSpace: 'nowrap' }}
            >
              {saving ? '...' : '+ Aggiungi'}
            </button>
          </div>

          {msg && <div style={{ fontSize: 13, color: COLORS.success, marginBottom: 10 }}>{msg}</div>}

          {/* Lista alias */}
          {loading
            ? <LoadingSpinner />
            : aliases.length === 0
              ? <EmptyState>Nessun alias per questo tipo.</EmptyState>
              : (
                <div>
                  {aliases.map(a => (
                    <div key={a.id} style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '7px 0', borderBottom: `1px solid ${COLORS.border}`,
                    }}>
                      <div>
                        <span style={{ fontSize: 14, color: COLORS.text }}>{a.alias_text}</span>
                        <span style={{
                          ...badge(COLORS.muted, '#f1f5f9'),
                          marginLeft: 8,
                        }}>{a.source}</span>
                      </div>
                      <button
                        onClick={() => handleDelete(a.id, a.alias_text)}
                        style={btn('danger', true)}
                        title="Elimina alias"
                      >
                        🗑
                      </button>
                    </div>
                  ))}
                </div>
              )
          }
        </div>
      )}
    </div>
  )
}

// ── Tab 4: Flags normativi ────────────────────────────────────────────────────

type InailFile = { filename: string; title: string; exists: boolean }

function TabFlags() {
  const [types, setTypes]           = useState<MachineType[]>([])
  const [selected, setSelected]     = useState<MachineType | null>(null)
  const [pat, setPat]               = useState(true)
  const [ver, setVer]               = useState(true)
  const [hint, setHint]             = useState('')
  const [vitaUtile, setVitaUtile]   = useState<string>('')
  const [saving, setSaving]         = useState(false)
  const [msg, setMsg]               = useState<string | null>(null)
  const [error, setError]           = useState<string | null>(null)
  const [searchQ, setSearchQ]       = useState('')
  const [inailFiles, setInailFiles] = useState<InailFile[]>([])
  // Hazard state
  const [hazardCat, setHazardCat]   = useState('')
  const [hazardTesto, setHazardTesto] = useState('')
  const [hazardLastUpdated, setHazardLastUpdated] = useState<string | null>(null)
  const [hazardBy, setHazardBy]     = useState<string | null>(null)
  const [savingHazard, setSavingHazard] = useState(false)
  const [hazardMsg, setHazardMsg]   = useState<string | null>(null)
  const [populatingVita, setPopulatingVita] = useState(false)
  const [populatingHazard, setPopulatingHazard] = useState(false)
  const [populatingInailHint, setPopulatingInailHint] = useState(false)

  const loadTypes = useCallback(() => {
    apiFetch('').then(setTypes).catch(e => setError(e.message))
    apiFetch('/inail-local-files').then(setInailFiles).catch(() => {})
  }, [])

  useEffect(() => { loadTypes() }, [loadTypes])

  const handleSelect = (t: MachineType) => {
    setSelected(t)
    setPat(t.requires_patentino)
    setVer(t.requires_verifiche)
    setHint((t as any).inail_search_hint ?? '')
    setVitaUtile(t.vita_utile_anni != null ? String(t.vita_utile_anni) : '')
    setMsg(null)
    setHazardCat('')
    setHazardTesto('')
    setHazardLastUpdated(null)
    setHazardBy(null)
    setHazardMsg(null)
    // Carica hazard
    apiFetch(`/${t.id}/hazard`).then((h: any) => {
      setHazardCat(h.categoria_inail ?? '')
      setHazardTesto(h.focus_testo ?? '')
      setHazardLastUpdated(h.last_updated ?? null)
      setHazardBy(h.aggiornato_da ?? null)
    }).catch(() => {})
  }

  const handleSave = async () => {
    if (!selected) return
    setSaving(true)
    setMsg(null)
    try {
      await apiFetch(`/${selected.id}/flags`, {
        method: 'PATCH',
        body: JSON.stringify({
          requires_patentino: pat,
          requires_verifiche: ver,
          inail_search_hint: hint || null,
          vita_utile_anni: vitaUtile ? parseInt(vitaUtile, 10) : null,
        }),
      })
      const updated = { ...selected, requires_patentino: pat, requires_verifiche: ver, vita_utile_anni: vitaUtile ? parseInt(vitaUtile, 10) : null, inail_search_hint: hint || null }
      setTypes(prev => prev.map(t => t.id === selected.id ? updated as MachineType : t))
      setSelected(updated as MachineType)
      setMsg('✅ Salvato.')
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleSaveHazard = async () => {
    if (!selected) return
    setSavingHazard(true)
    setHazardMsg(null)
    try {
      await apiFetch(`/${selected.id}/hazard`, {
        method: 'POST',
        body: JSON.stringify({ categoria_inail: hazardCat, focus_testo: hazardTesto }),
      })
      setHazardBy('admin')
      setHazardLastUpdated(new Date().toISOString())
      setHazardMsg('✅ Hazard salvato.')
    } catch (e: any) {
      setHazardMsg(`Errore: ${e.message}`)
    } finally {
      setSavingHazard(false)
    }
  }

  const handlePopulateVita = async () => {
    setPopulatingVita(true)
    try {
      const res = await apiFetch('/admin/populate-vita-utile', { method: 'POST' })
      setMsg(`✅ Vita utile: ${res.populated} tipi aggiornati, ${res.skipped} saltati.`)
      loadTypes()
    } catch (e: any) {
      setMsg(`Errore: ${e.message}`)
    } finally {
      setPopulatingVita(false)
    }
  }

  const handlePopulateHazard = async () => {
    setPopulatingHazard(true)
    try {
      const res = await apiFetch('/admin/populate-hazard', { method: 'POST' })
      setMsg(`✅ Hazard: ${res.populated} tipi aggiornati, ${res.skipped} saltati.`)
      if (selected) {
        apiFetch(`/${selected.id}/hazard`).then((h: any) => {
          setHazardCat(h.categoria_inail ?? '')
          setHazardTesto(h.focus_testo ?? '')
          setHazardLastUpdated(h.last_updated ?? null)
          setHazardBy(h.aggiornato_da ?? null)
        }).catch(() => {})
      }
    } catch (e: any) {
      setMsg(`Errore: ${e.message}`)
    } finally {
      setPopulatingHazard(false)
    }
  }

  const handlePopulateInailHint = async () => {
    setPopulatingInailHint(true)
    try {
      const res = await apiFetch('/admin/populate-inail-hint', { method: 'POST' })
      setMsg(`✅ Quaderni INAIL: ${res.populated} associati, ${res.skipped} senza corrispondenza.`)
      loadTypes()
    } catch (e: any) {
      setMsg(`Errore: ${e.message}`)
    } finally {
      setPopulatingInailHint(false)
    }
  }

  const filtered = searchQ.trim()
    ? types.filter(t => t.name.toLowerCase().includes(searchQ.toLowerCase()))
    : types

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      {error && <div style={{ gridColumn: '1/-1' }}><ErrorBox message={error} onRetry={() => setError(null)} /></div>}

      {/* Bottoni AI globali */}
      <div style={{ gridColumn: '1/-1', display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <button onClick={handlePopulateVita} disabled={populatingVita} style={btn('ghost')}>
          {populatingVita ? '⏳ Popolo vita utile...' : '🤖 Popola vita utile (AI, solo NULL)'}
        </button>
        <button onClick={handlePopulateHazard} disabled={populatingHazard} style={btn('ghost')}>
          {populatingHazard ? '⏳ Popolo hazard...' : '🤖 Popola hazard INAIL (AI, solo mancanti/old)'}
        </button>
        <button onClick={handlePopulateInailHint} disabled={populatingInailHint} style={btn('ghost')}>
          {populatingInailHint ? '⏳ Associo quaderni...' : '🤖 Associa quaderni INAIL (AI, solo NULL)'}
        </button>
        {msg && <span style={{ fontSize: 13, color: COLORS.success, alignSelf: 'center' }}>{msg}</span>}
      </div>

      {/* Lista tipi */}
      <div style={{ ...card, maxHeight: '70vh', overflowY: 'auto' }}>
        <SectionTitle>Tipi macchina ({types.length})</SectionTitle>
        <input
          style={{ ...input, marginBottom: 10 }}
          placeholder="Cerca tipo..."
          value={searchQ}
          onChange={e => setSearchQ(e.target.value)}
        />
        {filtered.map(t => (
          <div
            key={t.id}
            onClick={() => handleSelect(t)}
            style={{
              padding: '8px 10px',
              borderRadius: 6,
              cursor: 'pointer',
              background: selected?.id === t.id ? '#eff6ff' : 'transparent',
              border: selected?.id === t.id ? `1px solid #bfdbfe` : '1px solid transparent',
              marginBottom: 4,
            }}
          >
            <div style={{ fontWeight: 600, fontSize: 13, color: COLORS.text }}>{t.name}</div>
            <div style={{ display: 'flex', gap: 6, marginTop: 3, flexWrap: 'wrap' }}>
              <span style={badge(t.requires_patentino ? COLORS.success : COLORS.muted,
                                  t.requires_patentino ? '#f0fdf4' : '#f1f5f9')}>
                {t.requires_patentino ? '✓ patentino' : '— no patentino'}
              </span>
              <span style={badge(t.requires_verifiche ? '#1d4ed8' : COLORS.muted,
                                  t.requires_verifiche ? '#eff6ff' : '#f1f5f9')}>
                {t.requires_verifiche ? '✓ verifiche' : '— no verifiche'}
              </span>
              {t.vita_utile_anni != null && (
                <span style={badge('#6b7280', '#f9fafb')}>⏳ {t.vita_utile_anni}aa</span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Editor */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {!selected ? (
          <div style={card}>
            <EmptyState>Seleziona un tipo dalla lista per modificarne i flag.</EmptyState>
          </div>
        ) : (
          <>
            {/* --- Flag normativi + vita utile --- */}
            <div style={card}>
              <SectionTitle>Modifica: {selected.name}</SectionTitle>

              <p style={{ fontSize: 12, color: COLORS.muted, marginBottom: 8 }}>
                Questi flag determinano se la scheda riporta l'obbligo di patentino e verifiche periodiche.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', fontSize: 14 }}>
                  <input type="checkbox" checked={pat} onChange={e => setPat(e.target.checked)} style={{ width: 16, height: 16 }} />
                  <span>
                    <strong>Patentino / abilitazione obbligatoria</strong>
                    <br />
                    <span style={{ fontSize: 12, color: COLORS.muted }}>Accordo Stato-Regioni 22/02/2012 — PLE, carrelli, gru, ecc.</span>
                  </span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', fontSize: 14 }}>
                  <input type="checkbox" checked={ver} onChange={e => setVer(e.target.checked)} style={{ width: 16, height: 16 }} />
                  <span>
                    <strong>Verifiche periodiche INAIL</strong>
                    <br />
                    <span style={{ fontSize: 12, color: COLORS.muted }}>Art. 71 c.11 D.Lgs. 81/08 — Allegato VII</span>
                  </span>
                </label>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <label style={{ ...labelStyle, marginBottom: 0 }}>Quaderno INAIL locale associato (opzionale)</label>
                <button
                  type="button"
                  title="Ricarica lista file dalla cartella"
                  onClick={() => apiFetch('/inail-local-files').then(setInailFiles).catch(() => {})}
                  style={{ background: 'none', border: '1px solid #cbd5e1', borderRadius: 4, cursor: 'pointer', padding: '2px 6px', fontSize: 13, color: '#64748b' }}
                >
                  🔄
                </button>
              </div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 12 }}>
                <select style={{ ...input, marginBottom: 0, background: '#fff', flex: 1 }} value={hint} onChange={e => setHint(e.target.value)}>
                  <option value="">— Nessun file associato</option>
                  {inailFiles.map(f => (
                    <option key={f.filename} value={f.filename} disabled={!f.exists}>
                      {f.title}{!f.exists ? ' ⚠ file mancante' : ''}
                    </option>
                  ))}
                </select>
                {hint && (
                  <button
                    type="button"
                    title="Rimuovi associazione quaderno INAIL"
                    onClick={() => setHint('')}
                    style={{ background: 'none', border: '1px solid #dc2626', borderRadius: 4,
                      cursor: 'pointer', padding: '6px 10px', fontSize: 13, color: '#dc2626',
                      whiteSpace: 'nowrap', flexShrink: 0 }}
                  >
                    ✕ Rimuovi
                  </button>
                )}
              </div>

              <label style={{ ...labelStyle, marginBottom: 4 }}>Vita utile stimata (anni)</label>
              <input
                type="number"
                min="1" max="100"
                style={{ ...input, marginBottom: 4, width: 100 }}
                placeholder="es. 15"
                value={vitaUtile}
                onChange={e => setVitaUtile(e.target.value)}
              />
              <p style={{ fontSize: 11, color: COLORS.muted, margin: '0 0 14px' }}>
                Verrà mostrata nella scheda di sicurezza come indicazione per l'ispettore.
              </p>

              {msg && <div style={{ fontSize: 13, color: COLORS.success, marginBottom: 10 }}>{msg}</div>}
              <button onClick={handleSave} disabled={saving} style={btn('primary')}>
                {saving ? 'Salvataggio...' : '💾 Salva modifiche'}
              </button>
            </div>

            {/* --- Hazard Intelligence --- */}
            <div style={card}>
              <SectionTitle>📊 Hazard Intelligence</SectionTitle>
              {hazardLastUpdated && (
                <p style={{ fontSize: 11, color: COLORS.muted, marginBottom: 8 }}>
                  Ultimo aggiornamento: {new Date(hazardLastUpdated).toLocaleDateString('it-IT')}
                  {hazardBy && ` — da ${hazardBy}`}
                </p>
              )}
              <label style={{ ...labelStyle, marginBottom: 4 }}>Categoria INAIL (agente materiale)</label>
              <input
                style={{ ...input, marginBottom: 10 }}
                placeholder="es. Apparecchi di sollevamento"
                value={hazardCat}
                onChange={e => setHazardCat(e.target.value)}
              />
              <label style={{ ...labelStyle, marginBottom: 4 }}>Focus rischi di categoria</label>
              <textarea
                style={{ ...input, height: 90, resize: 'vertical', marginBottom: 10 }}
                placeholder="2-3 frasi sui rischi statisticamente più frequenti secondo INAIL..."
                value={hazardTesto}
                onChange={e => setHazardTesto(e.target.value)}
              />
              {hazardMsg && <div style={{ fontSize: 13, color: COLORS.success, marginBottom: 8 }}>{hazardMsg}</div>}
              <button onClick={handleSaveHazard} disabled={savingHazard} style={btn('primary')}>
                {savingHazard ? 'Salvataggio...' : '💾 Salva hazard'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// ── Componenti di supporto ────────────────────────────────────────────────────

// ── Tab 5: Ricerche (scan_log) ────────────────────────────────────────────────

type ScanRow = {
  id: number
  ts: string
  brand: string
  model: string
  machine_type: string | null
  serial_number: string | null
  machine_year: string | null
  fonte_tipo: string | null
  has_image: boolean
}

function buildScanEmailDraft(row: ScanRow, toEmail?: string): string {
  const serial = row.serial_number ? `\nMatricola / N° serie: ${row.serial_number}` : ''
  const year = row.machine_year ? `\nAnno di fabbricazione: ${row.machine_year}` : ''
  const type = row.machine_type ? `\nTipo macchina: ${row.machine_type}` : ''
  const subject = encodeURIComponent(`Richiesta manuale d'uso e dichiarazione CE — ${row.brand} ${row.model}`)
  const body = encodeURIComponent(
`Spett.le ${row.brand},

in qualità di ispettore della sicurezza sul lavoro, nell'ambito di un accesso ispettivo ai sensi del D.Lgs. 81/2008, si richiede cortesemente la trasmissione della seguente documentazione relativa al macchinario:

Marca: ${row.brand}
Modello: ${row.model}${type}${serial}${year}

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

function TabScans() {
  const [scans, setScans] = useState<ScanRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [loadingEmail, setLoadingEmail] = useState<number | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    apiFetch('/admin/scan-log?exclude_exact=1&limit=200')
      .then(rows => setScans(rows))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  async function handleSend(row: ScanRow) {
    setLoadingEmail(row.id)
    try {
      const res = await apiFetch(
        `/manufacturer-email?brand=${encodeURIComponent(row.brand)}&model=${encodeURIComponent(row.model ?? '')}`
      )
      const mailto = buildScanEmailDraft(row, res.email ?? undefined)
      window.open(mailto, '_blank')
    } catch {
      window.open(buildScanEmailDraft(row), '_blank')
    } finally {
      setLoadingEmail(null)
    }
  }

  async function handleDismiss(id: number) {
    try {
      await apiFetch(`/admin/scan-log/${id}/dismiss`, { method: 'POST' })
      setScans(prev => prev.filter(s => s.id !== id))
    } catch (e: any) {
      alert(`Errore: ${e.message}`)
    }
  }

  if (loading) return <LoadingSpinner />
  if (error) return <ErrorBox message={error} onRetry={load} />

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <SectionTitle>Ricerche da inviare al produttore</SectionTitle>
        <button onClick={load} style={btn('ghost', true)}>↺ Aggiorna</button>
      </div>
      <p style={{ fontSize: 12, color: COLORS.muted, marginBottom: 12 }}>
        Ricerche per cui non è disponibile il manuale specifico della marca e modello cercati. Clicca <strong>✉ Invia ricerca</strong> per
        aprire il client email con il messaggio precompilato e l'indirizzo del produttore scoperto automaticamente.
        Clicca <strong>✗</strong> per nascondere la riga senza cancellarla.
      </p>
      {scans.length === 0
        ? <EmptyState>Nessuna ricerca da inviare.</EmptyState>
        : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f8fafc' }}>
                  <Th>Foto</Th>
                  <Th>Data</Th>
                  <Th>Marca</Th>
                  <Th>Modello</Th>
                  <Th>Tipo macchina</Th>
                  <Th>Matricola</Th>
                  <Th>Anno</Th>
                  <Th>Fonte</Th>
                  <Th right>Azioni</Th>
                </tr>
              </thead>
              <tbody>
                {scans.map(row => (
                  <tr key={row.id} style={{ borderBottom: `1px solid #f1f5f9` }}>
                    <td style={{ padding: '6px 8px', textAlign: 'center' }}>
                      {row.has_image ? (
                        <a
                          href={`${BASE_URL}/machine-types/admin/scan-log/${row.id}/image`}
                          target="_blank"
                          rel="noreferrer"
                          title="Apri foto etichetta"
                        >
                          <img
                            src={`${BASE_URL}/machine-types/admin/scan-log/${row.id}/image`}
                            alt="etichetta"
                            style={{ width: 48, height: 36, objectFit: 'cover', borderRadius: 4, border: `1px solid ${COLORS.border}`, display: 'block' }}
                          />
                        </a>
                      ) : (
                        <span style={{ color: COLORS.muted, fontSize: 16 }}>—</span>
                      )}
                    </td>
                    <Td>{fmtDate(row.ts)}</Td>
                    <Td><strong>{row.brand}</strong></Td>
                    <Td>{row.model}</Td>
                    <Td>{row.machine_type ?? <span style={{ color: COLORS.muted }}>—</span>}</Td>
                    <Td>{row.serial_number ?? <span style={{ color: COLORS.muted }}>—</span>}</Td>
                    <Td>{row.machine_year ?? <span style={{ color: COLORS.muted }}>—</span>}</Td>
                    <Td><FonteBadge fonte={row.fonte_tipo} /></Td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <button
                        onClick={() => handleSend(row)}
                        disabled={loadingEmail === row.id}
                        style={btn('primary', true)}
                        title="Cerca email produttore e apri client email"
                      >
                        {loadingEmail === row.id ? '⏳' : '✉ Invia ricerca'}
                      </button>
                      {' '}
                      {row.has_image && (
                        <>
                          <a
                            href={`${BASE_URL}/machine-types/admin/scan-log/${row.id}/image`}
                            download={`etichetta_${row.brand}_${row.model}_${row.id}.jpg`}
                            style={{ ...btn('ghost', true), textDecoration: 'none', display: 'inline-block' }}
                            title="Scarica foto etichetta"
                          >
                            📎
                          </a>
                          {' '}
                        </>
                      )}
                      <button
                        onClick={() => handleDismiss(row.id)}
                        style={btn('ghost', true)}
                        title="Nascondi questa riga (non cancella dal log)"
                      >
                        ✗
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      }
    </div>
  )
}

// ── Tab 6: Log scansioni (tutte) ─────────────────────────────────────────────

const FONTE_COLORS: Record<string, string> = {
  'pdf':             '#166534',
  'inail+produttore':'#1d4ed8',
  'inail':           '#0369a1',
  'inail+categoria': '#7c3aed',
  'datasheet':       '#92400e',
  'fallback_ai':     '#dc2626',
}

function FonteBadge({ fonte }: { fonte: string | null }) {
  if (!fonte) return <span style={{ color: COLORS.muted }}>—</span>
  const color = FONTE_COLORS[fonte] ?? COLORS.muted
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 10,
      background: color + '18', color, border: `1px solid ${color}40`,
    }}>
      {fonte}
    </span>
  )
}

function TabLog() {
  const [rows, setRows] = useState<ScanRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [fonteFilter, setFonteFilter] = useState<string>('')
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    const params = new URLSearchParams({ limit: '200' })
    if (fonteFilter) params.set('fonte', fonteFilter)
    apiFetch(`/admin/scan-log?${params}`)
      .then(setRows)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [fonteFilter])

  useEffect(() => { load() }, [load])

  const imgUrl = (id: number) => `${BASE_URL}/machine-types/admin/scan-log/${id}/image`

  return (
    <div>
      {/* Lightbox */}
      {lightboxUrl && (
        <div
          onClick={() => setLightboxUrl(null)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
            zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'zoom-out',
          }}
        >
          <img
            src={lightboxUrl}
            alt="etichetta"
            style={{ maxWidth: '90vw', maxHeight: '90vh', borderRadius: 8, boxShadow: '0 8px 40px rgba(0,0,0,0.5)' }}
            onClick={e => e.stopPropagation()}
          />
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
        <SectionTitle>Log scansioni ({rows.length})</SectionTitle>
        <select
          value={fonteFilter}
          onChange={e => setFonteFilter(e.target.value)}
          style={{ ...input, width: 'auto', minWidth: 160 }}
        >
          <option value="">Tutte le fonti</option>
          <option value="fallback_ai">Solo senza manuale (fallback AI)</option>
          <option value="pdf">PDF produttore</option>
          <option value="inail">Solo INAIL</option>
          <option value="inail+produttore">INAIL + produttore</option>
        </select>
        <button onClick={load} style={btn('ghost', true)}>↺ Aggiorna</button>
      </div>

      {loading && <LoadingSpinner />}
      {error && <ErrorBox message={error} onRetry={load} />}
      {!loading && !error && rows.length === 0 && (
        <EmptyState>Nessuna scansione nel log.</EmptyState>
      )}
      {!loading && rows.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: `2px solid ${COLORS.border}` }}>
                <Th>Foto</Th>
                <Th>Data</Th>
                <Th>Marca</Th>
                <Th>Modello</Th>
                <Th>Tipo macchina</Th>
                <Th>Matricola</Th>
                <Th>Anno</Th>
                <Th>Fonte</Th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.id} style={{ borderBottom: `1px solid #f1f5f9` }}>
                  <td style={{ padding: '4px 8px', textAlign: 'center' }}>
                    {row.has_image ? (
                      <img
                        src={imgUrl(row.id)}
                        alt="etichetta"
                        onClick={() => setLightboxUrl(imgUrl(row.id))}
                        style={{
                          width: 52, height: 38, objectFit: 'cover', borderRadius: 4,
                          border: `1px solid ${COLORS.border}`, cursor: 'zoom-in', display: 'block',
                        }}
                        title="Clicca per ingrandire"
                      />
                    ) : (
                      <span style={{ color: COLORS.muted, fontSize: 14 }}>—</span>
                    )}
                  </td>
                  <Td><span style={{ fontSize: 11 }}>{fmtDate(row.ts)}</span></Td>
                  <Td><strong>{row.brand}</strong></Td>
                  <Td>{row.model}</Td>
                  <Td>{row.machine_type ?? <span style={{ color: COLORS.muted }}>—</span>}</Td>
                  <Td><span style={{ fontFamily: 'monospace', fontSize: 11 }}>{row.serial_number ?? '—'}</span></Td>
                  <Td>{row.machine_year ?? '—'}</Td>
                  <Td><FonteBadge fonte={row.fonte_tipo} /></Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function KpiCard({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <div style={{
      background: '#fff', border: `1px solid ${COLORS.border}`, borderRadius: 10,
      padding: '14px 16px', textAlign: 'center',
    }}>
      <div style={{ fontSize: 28, fontWeight: 800, color }}>{value}</div>
      <div style={{ fontSize: 12, color: COLORS.muted, marginTop: 2 }}>{label}</div>
    </div>
  )
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700, color: COLORS.text }}>{children}</h3>
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return <p style={{ fontSize: 13, color: COLORS.muted, textAlign: 'center', padding: '20px 0' }}>{children}</p>
}

function LoadingSpinner() {
  return <p style={{ fontSize: 13, color: COLORS.muted, padding: '20px 0', textAlign: 'center' }}>Caricamento...</p>
}

function ErrorBox({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div style={{ background: '#fef2f2', border: `1px solid #fca5a5`, borderRadius: 8, padding: '12px 14px', marginBottom: 12 }}>
      <span style={{ color: COLORS.danger, fontSize: 13 }}>⚠ {message}</span>
      <button onClick={onRetry} style={{ ...btn('ghost', true), marginLeft: 12 }}>Riprova</button>
    </div>
  )
}

function Th({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return (
    <th style={{
      textAlign: right ? 'right' : 'left',
      padding: '6px 8px',
      fontSize: 11,
      fontWeight: 700,
      color: COLORS.muted,
      textTransform: 'uppercase',
    }}>
      {children}
    </th>
  )
}

function Td({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return (
    <td style={{ padding: '7px 8px', textAlign: right ? 'right' : 'left', fontSize: 13, color: COLORS.text }}>
      {children}
    </td>
  )
}

function YesBadge() {
  return <span style={badge(COLORS.success, '#f0fdf4')}>✓ sì</span>
}
function NoBadge() {
  return <span style={badge(COLORS.muted, '#f1f5f9')}>— no</span>
}

function CheckLabel({ checked, onChange, label }: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
}) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 13 }}>
      <input
        type="checkbox"
        checked={checked}
        onChange={e => onChange(e.target.checked)}
        style={{ width: 14, height: 14 }}
      />
      {label}
    </label>
  )
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 13,
  fontWeight: 600,
  color: COLORS.text,
}

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric' })
  } catch {
    return iso
  }
}
