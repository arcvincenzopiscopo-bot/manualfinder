import { useState, useEffect, useCallback } from 'react'
import { apiFetch, BASE_URL, COLORS, card, btn, input, badge } from '../admin-shared'
import type { MachineType, Alias } from '../admin-shared'
import { SectionTitle, EmptyState } from '../admin-ui'

interface ManualResult {
  url: string
  title: string
  source_type: string
  language: string
  is_pdf: boolean
}

export function TabAiTools() {
  const [types, setTypes] = useState<MachineType[]>([])
  const [selectedType, setSelectedType] = useState<MachineType | null>(null)
  const [typeSearch, setTypeSearch] = useState('')

  // ── Ricerca manuale ──
  const [searchBrand, setSearchBrand] = useState('')
  const [searchModel, setSearchModel] = useState('')
  const [searchResults, setSearchResults] = useState<ManualResult[]>([])
  const [searching, setSearching] = useState(false)
  const [searchMsg, setSearchMsg] = useState<string | null>(null)

  // ── Configurazione guidata tipo ──
  const [configStatus, setConfigStatus] = useState<Record<string, 'idle' | 'running' | 'ok' | 'err'>>({})
  const [configMsgs, setConfigMsgs]     = useState<Record<string, string>>({})
  const [globalMsg, setGlobalMsg]       = useState<string | null>(null)

  // ── Alias AI ──
  const [generatingAlias, setGeneratingAlias] = useState(false)
  const [aliasMsg, setAliasMsg] = useState<string | null>(null)
  const [manualAlias, setManualAlias] = useState('')
  const [addingAlias, setAddingAlias] = useState(false)
  const [aliases, setAliases] = useState<Alias[]>([])

  useEffect(() => {
    apiFetch('').then(setTypes).catch(() => {})
  }, [])

  const loadAliases = useCallback((id: number) => {
    apiFetch(`/${id}/aliases`).then(setAliases).catch(() => {})
  }, [])

  const handleSelectType = (t: MachineType) => {
    setSelectedType(t)
    setConfigStatus({})
    setConfigMsgs({})
    setGlobalMsg(null)
    setAliasMsg(null)
    setManualAlias('')
    loadAliases(t.id)
  }

  // ── Ricerca manuale automatica ──
  const handleSearch = async () => {
    const b = searchBrand.trim()
    const m = searchModel.trim()
    if (!b && !m) return
    setSearching(true)
    setSearchMsg(null)
    setSearchResults([])
    try {
      const r = await fetch(`${BASE_URL}/manual/search?brand=${encodeURIComponent(b)}&model=${encodeURIComponent(m)}`)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const data: ManualResult[] = await r.json()
      setSearchResults(data)
      setSearchMsg(data.length === 0 ? '⚠️ Nessun manuale trovato.' : null)
    } catch (e: unknown) {
      setSearchMsg(`Errore: ${(e as Error).message}`)
    } finally {
      setSearching(false)
    }
  }

  // ── Run singolo step AI su tipo selezionato ──
  const runStep = async (key: string, path: string, body?: object) => {
    setConfigStatus(s => ({ ...s, [key]: 'running' }))
    try {
      const r = await apiFetch(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined })
      const detail = r.populated != null
        ? `${r.populated} aggiornati, ${r.skipped ?? 0} saltati`
        : r.inserted != null
          ? `${r.inserted} nuovi alias, ${r.skipped_existing ?? 0} già presenti`
          : 'OK'
      setConfigStatus(s => ({ ...s, [key]: 'ok' }))
      setConfigMsgs(m => ({ ...m, [key]: detail }))
      return true
    } catch (e: unknown) {
      setConfigStatus(s => ({ ...s, [key]: 'err' }))
      setConfigMsgs(m => ({ ...m, [key]: (e as Error).message }))
      return false
    }
  }

  // ── Configura tutto (AI bulk per tipo selezionato) ──
  const handleConfigureAll = async () => {
    if (!selectedType) return
    setGlobalMsg(null)
    setConfigStatus({})
    setConfigMsgs({})
    await runStep('alias', `/${selectedType.id}/autopopulate-aliases`)
    await runStep('vita',   '/admin/populate-vita-utile')
    await runStep('hazard', '/admin/populate-hazard')
    await runStep('inail',  '/admin/populate-inail-hint')
    loadAliases(selectedType.id)
    setGlobalMsg('✅ Configurazione AI completata.')
  }

  // ── Aggiungi alias manuale ──
  const handleAddAlias = async () => {
    if (!selectedType || !manualAlias.trim()) return
    setAddingAlias(true)
    try {
      await apiFetch(`/${selectedType.id}/aliases`, {
        method: 'POST',
        body: JSON.stringify({ alias_text: manualAlias.trim() }),
      })
      setManualAlias('')
      setAliasMsg('✅ Alias aggiunto.')
      loadAliases(selectedType.id)
    } catch (e: unknown) {
      const msg = (e as Error).message
      setAliasMsg(msg.includes('409') ? '⚠️ Alias già esistente.' : `Errore: ${msg}`)
    } finally {
      setAddingAlias(false)
    }
  }

  const handleGenerateAliases = async () => {
    if (!selectedType) return
    setGeneratingAlias(true)
    setAliasMsg(null)
    try {
      const r = await apiFetch(`/${selectedType.id}/autopopulate-aliases`, { method: 'POST' })
      setAliasMsg(r.status === 'empty' ? '⚠️ AI non ha prodotto alias.' : `✅ Inseriti ${r.inserted} alias (${r.skipped_existing} già presenti).`)
      loadAliases(selectedType.id)
    } catch (e: unknown) {
      setAliasMsg(`Errore: ${(e as Error).message}`)
    } finally {
      setGeneratingAlias(false)
    }
  }

  const handleDeleteAlias = async (aliasId: number, text: string) => {
    if (!confirm(`Eliminare alias "${text}"?`)) return
    try {
      await apiFetch(`/aliases/${aliasId}`, { method: 'DELETE' })
      if (selectedType) loadAliases(selectedType.id)
    } catch (e: unknown) {
      setAliasMsg(`Errore: ${(e as Error).message}`)
    }
  }

  const filteredTypes = typeSearch.trim()
    ? types.filter(t => typeof t.name === 'string' && t.name.toLowerCase().includes(typeSearch.toLowerCase()))
    : types

  const stepIcon = (key: string) => {
    const s = configStatus[key]
    if (s === 'running') return '⏳'
    if (s === 'ok') return '✅'
    if (s === 'err') return '❌'
    return '○'
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 16, alignItems: 'start' }}>

      {/* ── Colonna sinistra: lista tipi ── */}
      <div style={{ ...card, maxHeight: '80vh', overflowY: 'auto' }}>
        <SectionTitle>Tipo macchina</SectionTitle>
        <input
          style={{ ...input, marginBottom: 8 }}
          placeholder="Filtra..."
          value={typeSearch}
          onChange={e => setTypeSearch(e.target.value)}
        />
        {filteredTypes.map(t => (
          <div
            key={t.id}
            onClick={() => handleSelectType(t)}
            style={{
              padding: '7px 10px',
              borderRadius: 6,
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: selectedType?.id === t.id ? 700 : 400,
              background: selectedType?.id === t.id ? '#eff6ff' : 'transparent',
              border: selectedType?.id === t.id ? `1px solid #bfdbfe` : '1px solid transparent',
              marginBottom: 2,
              color: COLORS.text,
            }}
          >
            {t.name}
          </div>
        ))}
      </div>

      {/* ── Colonna destra: strumenti ── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* 1. Ricerca manuale automatica */}
        <div style={card}>
          <SectionTitle>🔍 Ricerca manuale automatica</SectionTitle>
          <p style={{ fontSize: 12, color: COLORS.muted, margin: '0 0 12px' }}>
            Cerca manuali PDF disponibili online per marca e modello.
          </p>
          <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
            <input
              style={{ ...input, flex: '1 1 130px' }}
              placeholder="Marca (es. Caterpillar)"
              value={searchBrand}
              onChange={e => setSearchBrand(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
            />
            <input
              style={{ ...input, flex: '1 1 130px' }}
              placeholder="Modello (es. 320D)"
              value={searchModel}
              onChange={e => setSearchModel(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
            />
            <button
              onClick={handleSearch}
              disabled={searching || (!searchBrand.trim() && !searchModel.trim())}
              style={{ ...btn('primary'), whiteSpace: 'nowrap' }}
            >
              {searching ? '⏳ Ricerca...' : '🔍 Cerca'}
            </button>
          </div>
          {searchMsg && <p style={{ fontSize: 12, color: COLORS.muted, margin: '0 0 8px' }}>{searchMsg}</p>}
          {searchResults.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {searchResults.map((r, i) => (
                <div key={`${i}_${r.url}`} style={{
                  background: '#f8fafc',
                  border: `1px solid ${COLORS.border}`,
                  borderRadius: 6,
                  padding: '8px 10px',
                  fontSize: 12,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                    <span style={{
                      ...badge(
                        r.source_type === 'inail' ? COLORS.success : r.source_type === 'manufacturer' ? COLORS.primary : COLORS.muted,
                        r.source_type === 'inail' ? '#f0fdf4' : r.source_type === 'manufacturer' ? '#eff6ff' : '#f1f5f9',
                      ),
                      fontSize: 10,
                    }}>
                      {r.source_type}
                    </span>
                    {r.is_pdf && <span style={badge('#6b21a8', '#f3e8ff')}>PDF</span>}
                    <span style={{ color: COLORS.muted }}>{r.language.toUpperCase()}</span>
                  </div>
                  <div style={{ fontWeight: 600, color: COLORS.text, marginBottom: 2 }}>{r.title || '(senza titolo)'}</div>
                  <a
                    href={r.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: COLORS.primary, wordBreak: 'break-all' }}
                  >
                    {r.url}
                  </a>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 2. Configurazione guidata tipo macchina */}
        <div style={card}>
          <SectionTitle>🤖 Configurazione guidata tipo macchina</SectionTitle>
          {!selectedType ? (
            <EmptyState>Seleziona un tipo macchina dalla lista per configurarlo con l'AI.</EmptyState>
          ) : (
            <>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14,
                background: '#eff6ff', borderRadius: 6, padding: '8px 12px',
              }}>
                <span style={{ fontWeight: 700, color: COLORS.primary, fontSize: 14 }}>{selectedType.name}</span>
              </div>

              {/* Bottone "Configura tutto" */}
              <button
                onClick={handleConfigureAll}
                disabled={Object.values(configStatus).some(s => s === 'running')}
                style={{ ...btn('primary'), marginBottom: 14, width: '100%' }}
              >
                {Object.values(configStatus).some(s => s === 'running')
                  ? '⏳ Configurazione in corso...'
                  : '🚀 Configura tutto con AI'}
              </button>

              {/* Step status */}
              {Object.keys(configStatus).length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
                  {[
                    { key: 'alias',  label: 'Alias multilingua (EN/DE/FR/ES)' },
                    { key: 'vita',   label: 'Vita utile stimata (anni)' },
                    { key: 'hazard', label: 'Hazard INAIL e categoria' },
                    { key: 'inail',  label: 'Quaderno INAIL associato' },
                  ].map(({ key, label }) => configStatus[key] != null && (
                    <div key={key} style={{
                      display: 'flex', alignItems: 'flex-start', gap: 8,
                      fontSize: 12, padding: '5px 0',
                      borderBottom: `1px solid ${COLORS.border}`,
                    }}>
                      <span style={{ fontSize: 14, lineHeight: 1.2 }}>{stepIcon(key)}</span>
                      <div>
                        <strong>{label}</strong>
                        {configMsgs[key] && (
                          <div style={{ color: COLORS.muted, marginTop: 2 }}>{configMsgs[key]}</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {globalMsg && <div style={{ fontSize: 13, color: COLORS.success, marginBottom: 8 }}>{globalMsg}</div>}

              {/* Step individuali */}
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <button
                  onClick={() => { runStep('alias', `/${selectedType.id}/autopopulate-aliases`).then(() => loadAliases(selectedType.id)) }}
                  disabled={configStatus['alias'] === 'running'}
                  style={btn('ghost', true)}
                >
                  🌍 Solo alias
                </button>
                <button
                  onClick={() => runStep('vita', '/admin/populate-vita-utile')}
                  disabled={configStatus['vita'] === 'running'}
                  style={btn('ghost', true)}
                >
                  ⏳ Solo vita utile
                </button>
                <button
                  onClick={() => runStep('hazard', '/admin/populate-hazard')}
                  disabled={configStatus['hazard'] === 'running'}
                  style={btn('ghost', true)}
                >
                  📊 Solo hazard
                </button>
                <button
                  onClick={() => runStep('inail', '/admin/populate-inail-hint')}
                  disabled={configStatus['inail'] === 'running'}
                  style={btn('ghost', true)}
                >
                  📋 Solo quaderno INAIL
                </button>
              </div>
            </>
          )}
        </div>

        {/* 3. Gestione alias con AI */}
        <div style={card}>
          <SectionTitle>🔗 Gestione alias con AI</SectionTitle>
          {!selectedType ? (
            <EmptyState>Seleziona un tipo macchina dalla lista.</EmptyState>
          ) : (
            <>
              <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
                <button
                  onClick={handleGenerateAliases}
                  disabled={generatingAlias}
                  style={btn('primary', true)}
                >
                  {generatingAlias ? '⏳ Generazione...' : '🤖 Genera alias EN/DE/FR/ES'}
                </button>
              </div>
              {aliasMsg && <div style={{ fontSize: 12, color: COLORS.success, marginBottom: 8 }}>{aliasMsg}</div>}

              {/* Aggiunta alias manuale */}
              <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                <input
                  style={{ ...input, flex: 1 }}
                  placeholder="Alias manuale (es. escavatore, bagger, excavator...)"
                  value={manualAlias}
                  onChange={e => setManualAlias(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleAddAlias()}
                />
                <button
                  onClick={handleAddAlias}
                  disabled={addingAlias || !manualAlias.trim()}
                  style={{ ...btn('success', true), whiteSpace: 'nowrap' }}
                >
                  + Aggiungi
                </button>
              </div>

              {/* Lista alias correnti */}
              {aliases.length > 0 ? (
                <div>
                  <div style={{ fontSize: 11, color: COLORS.muted, fontWeight: 600, marginBottom: 4 }}>
                    ALIAS CORRENTI ({aliases.length})
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {aliases.map(a => (
                      <div key={a.id} style={{
                        display: 'flex', alignItems: 'center', gap: 4,
                        background: '#f8fafc', border: `1px solid ${COLORS.border}`,
                        borderRadius: 16, padding: '3px 8px 3px 10px', fontSize: 12,
                      }}>
                        <span>{a.alias_text}</span>
                        <span style={{ fontSize: 10, color: COLORS.muted }}>({a.source})</span>
                        <button
                          onClick={() => handleDeleteAlias(a.id, a.alias_text)}
                          style={{
                            background: 'none', border: 'none', cursor: 'pointer',
                            color: COLORS.danger, fontSize: 13, lineHeight: 1, padding: '0 2px',
                          }}
                        >×</button>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <EmptyState>Nessun alias. Genera con AI o aggiungine uno manualmente.</EmptyState>
              )}
            </>
          )}
        </div>

      </div>
    </div>
  )
}
