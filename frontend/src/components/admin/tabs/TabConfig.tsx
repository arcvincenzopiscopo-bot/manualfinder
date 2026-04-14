import { useState, useEffect, useCallback } from 'react'
import { rawFetch, COLORS, card, btn, input } from '../admin-shared'
import { SectionTitle, EmptyState, ErrorBox } from '../admin-ui'

// ── Tipi per sezione AI ───────────────────────────────────────────────────────

interface ProviderUsage {
  usage: number
  limit: number
  available: boolean
}

const TASK_LABELS: Record<string, string> = {
  ocr:           'OCR / Vision (targhe)',
  pdf_analysis:  'Analisi PDF diretto',
  text_analysis: 'Analisi testo manuale',
  machine_type:  'Inferenza tipo macchina',
  url_rule:      'Classificazione URL feedback',
  prompt_rule:   'Generazione regole prompt',
  quality_check: 'Controllo qualità PDF',
}

const PROVIDER_LABELS: Record<string, string> = {
  gemini:    'Gemini',
  groq1:     'Groq 1',
  groq2:     'Groq 2',
  tesseract: 'Tesseract (locale)',
}

function SectionAi({ cfgFetch }: { cfgFetch: (p: string, o?: RequestInit) => Promise<unknown> }) {
  const [usage, setUsage] = useState<Record<string, ProviderUsage>>({})
  const [order, setOrder] = useState<Record<string, string[]>>({})
  const [saving, setSaving] = useState<Record<string, boolean>>({})
  const [msgs, setMsgs] = useState<Record<string, string>>({})
  const [loadingUsage, setLoadingUsage] = useState(true)

  const loadUsage = useCallback(() => {
    cfgFetch('/ai-usage')
      .then(r => setUsage(r as Record<string, ProviderUsage>))
      .catch(() => {})
      .finally(() => setLoadingUsage(false))
  }, [cfgFetch])

  const loadOrder = useCallback(() => {
    cfgFetch('/ai-provider-order')
      .then(r => setOrder(r as Record<string, string[]>))
      .catch(() => {})
  }, [cfgFetch])

  useEffect(() => {
    loadUsage()
    loadOrder()
    // Auto-refresh utilizzo ogni 30s
    const id = setInterval(loadUsage, 30000)
    return () => clearInterval(id)
  }, [loadUsage, loadOrder])

  const moveProvider = (taskType: string, idx: number, dir: -1 | 1) => {
    const newOrder = [...(order[taskType] || [])]
    const swapIdx = idx + dir
    if (swapIdx < 0 || swapIdx >= newOrder.length) return
    ;[newOrder[idx], newOrder[swapIdx]] = [newOrder[swapIdx], newOrder[idx]]
    setOrder(prev => ({ ...prev, [taskType]: newOrder }))
  }

  const saveOrder = async (taskType: string) => {
    setSaving(prev => ({ ...prev, [taskType]: true }))
    setMsgs(prev => ({ ...prev, [taskType]: '' }))
    try {
      await cfgFetch(`/ai-provider-order/${taskType}`, {
        method: 'PUT',
        body: JSON.stringify({ order: order[taskType] }),
      })
      setMsgs(prev => ({ ...prev, [taskType]: '✅ Salvato' }))
    } catch (e: unknown) {
      setMsgs(prev => ({ ...prev, [taskType]: `❌ ${(e as Error).message}` }))
    } finally {
      setSaving(prev => ({ ...prev, [taskType]: false }))
    }
  }

  const LIMIT_COLORS: Record<string, string> = { gemini: '#0284c7', groq1: '#7c3aed', groq2: '#be185d' }

  return (
    <div>
      {/* Utilizzo oggi */}
      <div style={card}>
        <SectionTitle>Utilizzo oggi {loadingUsage ? '(caricamento...)' : ''}</SectionTitle>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {Object.entries(usage).map(([provider, data]) => {
            const pct = Math.round((data.usage / data.limit) * 100)
            const color = LIMIT_COLORS[provider] || '#64748b'
            return (
              <div key={provider} style={{
                border: `2px solid ${color}`, borderRadius: 10, padding: '12px 18px',
                minWidth: 180, background: data.available ? '#f0fdf4' : '#fef2f2',
              }}>
                <div style={{ fontWeight: 700, color, fontSize: 15 }}>
                  {PROVIDER_LABELS[provider] || provider}
                </div>
                <div style={{ fontSize: 24, fontWeight: 800, color: data.available ? '#16a34a' : '#dc2626', margin: '4px 0' }}>
                  {data.usage} <span style={{ fontSize: 14, fontWeight: 400, color: '#64748b' }}>/ {data.limit}</span>
                </div>
                <div style={{ height: 6, borderRadius: 3, background: '#e2e8f0', overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${Math.min(pct, 100)}%`, background: pct > 85 ? '#dc2626' : pct > 60 ? '#d97706' : color }} />
                </div>
                <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
                  {pct}% — {data.available ? '✓ Disponibile' : '✗ Esaurito'}
                </div>
              </div>
            )
          })}
        </div>
        {Object.keys(usage).length === 0 && !loadingUsage && (
          <EmptyState>Nessun dato disponibile — verifica che la tabella ai_usage esista.</EmptyState>
        )}
        <button onClick={loadUsage} style={{ ...btn('ghost', true), marginTop: 10 }}>🔄 Aggiorna</button>
      </div>

      {/* Ordine provider per funzione */}
      <div style={card}>
        <SectionTitle>Ordine provider per funzione AI</SectionTitle>
        <div style={{ fontSize: 12, color: COLORS.muted, marginBottom: 12 }}>
          Il primo provider disponibile sotto la quota giornaliera viene usato. Usa le frecce per riordinare.
        </div>
        {Object.entries(TASK_LABELS).map(([taskType, label]) => {
          const providers = order[taskType] || []
          return (
            <div key={taskType} style={{ marginBottom: 12, padding: '10px 12px', border: `1px solid ${COLORS.border}`, borderRadius: 8, background: '#fafafa' }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>{label}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                {providers.map((p, i) => (
                  <div key={p} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span style={{
                      padding: '3px 10px', borderRadius: 14, fontSize: 12, fontWeight: 600,
                      background: i === 0 ? '#dbeafe' : '#f1f5f9',
                      color: i === 0 ? '#1e40af' : '#475569',
                      border: `1px solid ${i === 0 ? '#93c5fd' : '#e2e8f0'}`,
                    }}>
                      {i + 1}. {PROVIDER_LABELS[p] || p}
                    </span>
                    <button onClick={() => moveProvider(taskType, i, -1)} disabled={i === 0} style={{ ...btn('ghost', true), padding: '2px 6px', fontSize: 11 }} title="Sposta su">↑</button>
                    <button onClick={() => moveProvider(taskType, i, 1)} disabled={i === providers.length - 1} style={{ ...btn('ghost', true), padding: '2px 6px', fontSize: 11 }} title="Sposta giù">↓</button>
                  </div>
                ))}
                <button
                  onClick={() => saveOrder(taskType)}
                  disabled={saving[taskType]}
                  style={{ ...btn('primary', true), marginLeft: 8 }}
                >
                  {saving[taskType] ? '...' : '💾 Salva'}
                </button>
                {msgs[taskType] && <span style={{ fontSize: 12, color: msgs[taskType].startsWith('✅') ? COLORS.success : COLORS.danger }}>{msgs[taskType]}</span>}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function TabConfig() {
  const [section, setSection] = useState<'ai'|'lists'|'maps'|'domains'|'brands'>('ai')
  const [listKeys, setListKeys]     = useState<string[]>([])
  const [mapKeys, setMapKeys]       = useState<string[]>([])
  const [selListKey, setSelListKey] = useState('')
  const [selMapKey, setSelMapKey]   = useState('')
  const [listItems, setListItems]   = useState<{item:string,meta:unknown}[]>([])
  const [mapEntries, setMapEntries] = useState<{k:string,v:unknown}[]>([])
  const [domains, setDomains]       = useState<{id:number,domain:string,kind:string,brand:string|null,active:boolean}[]>([])
  const [domainKinds, setDomainKinds] = useState<string[]>([])
  const [selDomainKind, setSelDomainKind] = useState('')
  const [brandHints, setBrandHints] = useState<{id:number,brand:string,model_prefix:string|null,machine_type_text:string,active:boolean}[]>([])
  const [newItem, setNewItem]       = useState('')
  const [newMapK, setNewMapK]       = useState('')
  const [newMapV, setNewMapV]       = useState('')
  const [newDomain, setNewDomain]   = useState('')
  const [newDomainKind, setNewDomainKind] = useState('')
  const [newDomainBrand, setNewDomainBrand] = useState('')
  const [newBrand, setNewBrand]     = useState('')
  const [newBrandType, setNewBrandType] = useState('')
  const [newBrandPrefix, setNewBrandPrefix] = useState('')
  const [saving, setSaving]         = useState(false)
  const [msg, setMsg]               = useState<string|null>(null)
  const [error, setError]           = useState<string|null>(null)

  const cfgFetch = (path: string, opts?: RequestInit) =>
    rawFetch('/admin/config' + path, opts)

  useEffect(() => {
    cfgFetch('/lists').then(r => setListKeys(r.keys || []))
    cfgFetch('/maps').then(r => setMapKeys(r.keys || []))
    cfgFetch('/domains').then(r => { setDomains(r.domains || []); setDomainKinds(r.kinds || []) })
    cfgFetch('/brand-hints').then(r => setBrandHints(r.hints || []))
  }, [])

  const loadList = (k: string) => {
    setSelListKey(k)
    cfgFetch(`/lists/${k}`).then(r => setListItems(r.items || []))
  }

  const loadMap = (k: string) => {
    setSelMapKey(k)
    cfgFetch(`/maps/${k}`).then(r => setMapEntries(r.entries || []))
  }

  const loadDomains = (kind: string) => {
    setSelDomainKind(kind)
    cfgFetch(`/domains?kind=${encodeURIComponent(kind)}`).then(r => setDomains(r.domains || []))
  }

  const addListItem = async () => {
    if (!selListKey || !newItem.trim()) return
    setSaving(true); setMsg(null)
    try {
      await cfgFetch(`/lists/${selListKey}`, { method: 'POST', body: JSON.stringify({ item: newItem.trim() }) })
      setNewItem(''); setMsg('✅ Aggiunto.')
      loadList(selListKey)
    } catch(e: unknown) { setError((e as Error).message) } finally { setSaving(false) }
  }

  const delListItem = async (item: string) => {
    await cfgFetch(`/lists/${selListKey}/${encodeURIComponent(item)}`, { method: 'DELETE' })
    loadList(selListKey)
  }

  const addMapEntry = async () => {
    if (!selMapKey || !newMapK.trim()) return
    let parsed: unknown = newMapV
    try { parsed = JSON.parse(newMapV) } catch { /* keep string */ }
    setSaving(true); setMsg(null)
    try {
      await cfgFetch(`/maps/${selMapKey}`, { method: 'POST', body: JSON.stringify({ k: newMapK.trim(), v: parsed }) })
      setNewMapK(''); setNewMapV(''); setMsg('✅ Aggiunto.')
      loadMap(selMapKey)
    } catch(e: unknown) { setError((e as Error).message) } finally { setSaving(false) }
  }

  const delMapEntry = async (k: string) => {
    await cfgFetch(`/maps/${selMapKey}/${encodeURIComponent(k)}`, { method: 'DELETE' })
    loadMap(selMapKey)
  }

  const addDomain = async () => {
    if (!newDomain.trim() || !newDomainKind.trim()) return
    setSaving(true); setMsg(null)
    try {
      await cfgFetch('/domains', { method: 'POST', body: JSON.stringify({ domain: newDomain.trim(), kind: newDomainKind.trim(), brand: newDomainBrand.trim() || null }) })
      setNewDomain(''); setNewDomainBrand(''); setMsg('✅ Aggiunto.')
      cfgFetch('/domains').then(r => { setDomains(r.domains || []); setDomainKinds(r.kinds || []) })
    } catch(e: unknown) { setError((e as Error).message) } finally { setSaving(false) }
  }

  const delDomain = async (id: number) => {
    await cfgFetch(`/domains/${id}`, { method: 'DELETE' })
    cfgFetch('/domains').then(r => { setDomains(r.domains || []); setDomainKinds(r.kinds || []) })
  }

  const addBrandHint = async () => {
    if (!newBrand.trim() || !newBrandType.trim()) return
    setSaving(true); setMsg(null)
    try {
      await cfgFetch('/brand-hints', { method: 'POST', body: JSON.stringify({ brand: newBrand.trim(), machine_type_text: newBrandType.trim(), model_prefix: newBrandPrefix.trim() || null }) })
      setNewBrand(''); setNewBrandType(''); setNewBrandPrefix(''); setMsg('✅ Aggiunto.')
      cfgFetch('/brand-hints').then(r => setBrandHints(r.hints || []))
    } catch(e: unknown) { setError((e as Error).message) } finally { setSaving(false) }
  }

  const delBrandHint = async (id: number) => {
    await cfgFetch(`/brand-hints/${id}`, { method: 'DELETE' })
    cfgFetch('/brand-hints').then(r => setBrandHints(r.hints || []))
  }

  const sectionBtns: {id: 'ai'|'lists'|'maps'|'domains'|'brands', label: string}[] = [
    { id: 'ai',     label: '🤖 Provider AI' },
    { id: 'lists',   label: 'Liste' },
    { id: 'maps',    label: 'Mappe' },
    { id: 'domains', label: 'Domini' },
    { id: 'brands',  label: 'Brand→Tipo' },
  ]

  return (
    <div>
      {error && <ErrorBox message={error} onRetry={() => setError(null)} />}
      {msg && <div style={{ fontSize: 13, color: COLORS.success, marginBottom: 10 }}>{msg}</div>}

      {/* Sub-navigation */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, borderBottom: `1px solid ${COLORS.border}`, paddingBottom: 8 }}>
        {sectionBtns.map(s => (
          <button key={s.id} onClick={() => setSection(s.id)}
            style={{ ...btn(section === s.id ? 'primary' : 'ghost', true) }}>
            {s.label}
          </button>
        ))}
        <button onClick={async () => { await cfgFetch('/cache-clear', { method: 'POST' }); setMsg('✅ Cache config invalidata.') }}
          style={{ ...btn('warn', true), marginLeft: 'auto' }}>
          🔄 Invalida cache
        </button>
      </div>

      {/* SECTION: AI Provider */}
      {section === 'ai' && <SectionAi cfgFetch={cfgFetch} />}

      {/* SECTION: Liste */}
      {section === 'lists' && (
        <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 16 }}>
          <div style={card}>
            <SectionTitle>Chiavi lista</SectionTitle>
            {listKeys.map(k => (
              <div key={k} onClick={() => loadList(k)}
                style={{ padding: '6px 8px', borderRadius: 5, cursor: 'pointer', fontSize: 13,
                  background: selListKey === k ? '#eff6ff' : 'transparent',
                  fontWeight: selListKey === k ? 700 : 400 }}>
                {k}
              </div>
            ))}
          </div>
          <div style={card}>
            {selListKey
              ? <>
                  <SectionTitle>Lista: {selListKey}</SectionTitle>
                  <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                    <input style={input} placeholder="Nuovo item..." value={newItem} onChange={e => setNewItem(e.target.value)} onKeyDown={e => e.key === 'Enter' && addListItem()} />
                    <button onClick={addListItem} disabled={saving || !newItem.trim()} style={{ ...btn('primary'), whiteSpace: 'nowrap' }}>+ Aggiungi</button>
                  </div>
                  <div>
                    {listItems.map(it => (
                      <div key={it.item} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderBottom: `1px solid ${COLORS.border}` }}>
                        <span style={{ fontSize: 13 }}>{it.item}</span>
                        <button onClick={() => delListItem(it.item)} style={btn('danger', true)}>✕</button>
                      </div>
                    ))}
                    {listItems.length === 0 && <EmptyState>Lista vuota.</EmptyState>}
                  </div>
                </>
              : <EmptyState>Seleziona una chiave lista a sinistra.</EmptyState>
            }
          </div>
        </div>
      )}

      {/* SECTION: Mappe */}
      {section === 'maps' && (
        <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 16 }}>
          <div style={card}>
            <SectionTitle>Chiavi mappa</SectionTitle>
            {mapKeys.map(k => (
              <div key={k} onClick={() => loadMap(k)}
                style={{ padding: '6px 8px', borderRadius: 5, cursor: 'pointer', fontSize: 13,
                  background: selMapKey === k ? '#eff6ff' : 'transparent',
                  fontWeight: selMapKey === k ? 700 : 400 }}>
                {k}
              </div>
            ))}
          </div>
          <div style={card}>
            {selMapKey
              ? <>
                  <SectionTitle>Mappa: {selMapKey}</SectionTitle>
                  <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
                    <input style={{ ...input, flex: '1 1 160px' }} placeholder="Chiave" value={newMapK} onChange={e => setNewMapK(e.target.value)} />
                    <input style={{ ...input, flex: '2 1 220px' }} placeholder="Valore (JSON o stringa)" value={newMapV} onChange={e => setNewMapV(e.target.value)} />
                    <button onClick={addMapEntry} disabled={saving || !newMapK.trim()} style={{ ...btn('primary'), whiteSpace: 'nowrap' }}>+ Aggiungi</button>
                  </div>
                  <div>
                    {mapEntries.map(e => (
                      <div key={e.k} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderBottom: `1px solid ${COLORS.border}` }}>
                        <div>
                          <span style={{ fontWeight: 600, fontSize: 13 }}>{e.k}</span>
                          <span style={{ color: COLORS.muted, fontSize: 12, marginLeft: 8 }}>{JSON.stringify(e.v)}</span>
                        </div>
                        <button onClick={() => delMapEntry(e.k)} style={btn('danger', true)}>✕</button>
                      </div>
                    ))}
                    {mapEntries.length === 0 && <EmptyState>Mappa vuota.</EmptyState>}
                  </div>
                </>
              : <EmptyState>Seleziona una chiave mappa a sinistra.</EmptyState>
            }
          </div>
        </div>
      )}

      {/* SECTION: Domini */}
      {section === 'domains' && (
        <div style={card}>
          <SectionTitle>Domini classificati ({domains.length})</SectionTitle>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
            <input style={{ ...input, flex: '2 1 200px' }} placeholder="Dominio (es. inail.it)" value={newDomain} onChange={e => setNewDomain(e.target.value)} />
            <input style={{ ...input, flex: '1 1 150px' }} placeholder="Tipo (es. institutional)" value={newDomainKind} onChange={e => setNewDomainKind(e.target.value)} />
            <input style={{ ...input, flex: '1 1 150px' }} placeholder="Brand (opz.)" value={newDomainBrand} onChange={e => setNewDomainBrand(e.target.value)} />
            <button onClick={addDomain} disabled={saving || !newDomain.trim() || !newDomainKind.trim()} style={{ ...btn('primary'), whiteSpace: 'nowrap' }}>+ Aggiungi</button>
          </div>
          <div style={{ display: 'flex', gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
            <button onClick={() => { setSelDomainKind(''); cfgFetch('/domains').then(r => setDomains(r.domains||[])) }}
              style={btn(selDomainKind==='' ? 'primary' : 'ghost', true)}>Tutti</button>
            {domainKinds.map(k => (
              <button key={k} onClick={() => loadDomains(k)} style={btn(selDomainKind===k ? 'primary' : 'ghost', true)}>{k}</button>
            ))}
          </div>
          <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
            <thead><tr style={{ background: '#f8fafc' }}>
              {['Dominio','Tipo','Brand',''].map(h => <th key={h} style={{ textAlign:'left', padding:'6px 8px', fontWeight:600 }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {domains.map(d => (
                <tr key={d.id} style={{ borderBottom: `1px solid ${COLORS.border}` }}>
                  <td style={{ padding:'5px 8px' }}>{d.domain}</td>
                  <td style={{ padding:'5px 8px', color: COLORS.muted }}>{d.kind}</td>
                  <td style={{ padding:'5px 8px', color: COLORS.muted }}>{d.brand || '—'}</td>
                  <td style={{ padding:'5px 8px' }}><button onClick={() => delDomain(d.id)} style={btn('danger', true)}>✕</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {domains.length === 0 && <EmptyState>Nessun dominio — seed eseguito all'avvio.</EmptyState>}
        </div>
      )}

      {/* SECTION: Brand hints */}
      {section === 'brands' && (
        <div style={card}>
          <SectionTitle>Brand → Tipo macchina ({brandHints.length})</SectionTitle>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
            <input style={{ ...input, flex: '1 1 160px' }} placeholder="Brand (es. caterpillar)" value={newBrand} onChange={e => setNewBrand(e.target.value)} />
            <input style={{ ...input, flex: '1 1 120px' }} placeholder="Prefisso modello (opz.)" value={newBrandPrefix} onChange={e => setNewBrandPrefix(e.target.value)} />
            <input style={{ ...input, flex: '2 1 200px' }} placeholder="Tipo macchina (es. escavatore)" value={newBrandType} onChange={e => setNewBrandType(e.target.value)} />
            <button onClick={addBrandHint} disabled={saving || !newBrand.trim() || !newBrandType.trim()} style={{ ...btn('primary'), whiteSpace: 'nowrap' }}>+ Aggiungi</button>
          </div>
          <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
            <thead><tr style={{ background: '#f8fafc' }}>
              {['Brand','Prefisso mod.','Tipo macchina',''].map(h => <th key={h} style={{ textAlign:'left', padding:'6px 8px', fontWeight:600 }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {brandHints.map(h => (
                <tr key={h.id} style={{ borderBottom: `1px solid ${COLORS.border}` }}>
                  <td style={{ padding:'5px 8px', fontWeight:600 }}>{h.brand}</td>
                  <td style={{ padding:'5px 8px', color: COLORS.muted }}>{h.model_prefix || '—'}</td>
                  <td style={{ padding:'5px 8px' }}>{h.machine_type_text}</td>
                  <td style={{ padding:'5px 8px' }}><button onClick={() => delBrandHint(h.id)} style={btn('danger', true)}>✕</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {brandHints.length === 0 && <EmptyState>Nessun hint — seed eseguito all'avvio.</EmptyState>}
        </div>
      )}
    </div>
  )
}
