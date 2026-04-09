import { useState, useEffect, useRef } from 'react'
import type { MachineType } from '../../types'
import { getMachineTypes, suggestMachineType } from '../../services/api'

interface Props {
  value: string
  valueId: number | null
  onChange: (name: string, id: number | null) => void
  disabled?: boolean
  loading?: boolean   // mostra spinner "Rilevamento..." durante inferenza AI
}

export function MachineTypeSelector({ value, valueId, onChange, disabled, loading }: Props) {
  const [types, setTypes] = useState<MachineType[]>([])
  const [query, setQuery] = useState(value)
  const [showList, setShowList] = useState(false)
  const [suggestionSent, setSuggestionSent] = useState(false)
  const [loadingCatalog, setLoadingCatalog] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  // Carica catalogo al mount (una volta sola)
  useEffect(() => {
    setLoadingCatalog(true)
    getMachineTypes().then(data => {
      setTypes(data)
      setLoadingCatalog(false)
    })
  }, [])

  // Sincronizza il testo quando il valore cambia esternamente (OCR inference)
  useEffect(() => {
    setQuery(value)
  }, [value])

  // Filtra la lista in base al testo digitato
  const filtered = query.trim().length === 0
    ? types
    : types.filter(t =>
        t.name.toLowerCase().includes(query.toLowerCase().trim())
      )

  // Reset "proposta inviata" se l'utente cambia il testo
  useEffect(() => {
    setSuggestionSent(false)
  }, [query])

  // Calcola badge confidenza da valueId
  const matchedType = valueId != null ? types.find(t => t.id === valueId) : null

  // Mostra il suggerimento "Non trovi?" ogni volta che c'è testo libero non nel catalogo,
  // incluso quando il valore è pre-compilato dall'OCR (senza bisogno di focus)
  const showSuggest = !matchedType && !loadingCatalog && query.trim().length > 2 && !showList
  const confidenceColor = matchedType
    ? '#166534'   // verde — match DB confermato
    : value.trim()
      ? '#92400e'  // giallo — testo libero non nel catalogo
      : '#94a3b8'  // grigio — vuoto

  const confidenceBg = matchedType ? '#f0fdf4' : value.trim() ? '#fffbeb' : '#f8fafc'
  const confidenceBorder = matchedType ? '#86efac' : value.trim() ? '#fde68a' : '#e2e8f0'
  const confidenceLabel = matchedType ? 'Catalogo' : value.trim() ? 'Testo libero' : 'Non impostato'

  const handleSelect = (type: MachineType) => {
    setQuery(type.name)
    setShowList(false)
    onChange(type.name, type.id)
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value
    setQuery(v)
    setShowList(true)
    // Se l'utente cancella o scrive qualcosa che non è nel catalogo, resetta l'ID
    const exact = types.find(t => t.name.toLowerCase() === v.toLowerCase().trim())
    if (exact) {
      onChange(exact.name, exact.id)
    } else {
      onChange(v, null)
    }
  }

  const handleBlur = () => {
    // Piccolo delay per permettere il click sulla lista prima di chiuderla
    setTimeout(() => setShowList(false), 150)
  }

  const handleSuggest = async () => {
    if (!query.trim()) return
    await suggestMachineType(query.trim())
    setSuggestionSent(true)
  }

  return (
    <div style={{ position: 'relative' }}>
      {/* Label con badge confidenza */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <label style={labelStyle}>
          Tipo di macchina (per ricerca INAIL)
          {loading && (
            <span style={{ marginLeft: 8, fontSize: 11, color: '#3b82f6', fontWeight: 400 }}>
              ⟳ Rilevamento...
            </span>
          )}
          {loadingCatalog && !loading && (
            <span style={{ marginLeft: 8, fontSize: 11, color: '#94a3b8', fontWeight: 400 }}>
              caricamento catalogo...
            </span>
          )}
        </label>
        <span style={{
          fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 20,
          color: confidenceColor, background: confidenceBg, border: `1px solid ${confidenceBorder}`,
        }}>
          {confidenceLabel}
        </span>
      </div>

      {/* Input con dropdown */}
      <input
        ref={inputRef}
        type="text"
        value={loading ? '' : query}
        onChange={handleInputChange}
        onFocus={() => setShowList(true)}
        onBlur={handleBlur}
        placeholder={loading ? 'Rilevamento tipo in corso...' : 'Cerca o seleziona un tipo...'}
        style={{
          ...inputStyle(!!matchedType),
          opacity: (loading || disabled) ? 0.6 : 1,
          paddingRight: matchedType ? '36px' : '12px',
        }}
        autoCapitalize="sentences"
        disabled={disabled || loading}
      />

      {/* Check verde se tipo dal catalogo */}
      {matchedType && !loading && (
        <span style={{
          position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
          fontSize: 16, color: '#16a34a', pointerEvents: 'none',
          marginTop: '14px', // compensa la label sopra
        }}>✓</span>
      )}

      {/* Dropdown lista tipi */}
      {showList && !loading && filtered.length > 0 && (
        <div
          ref={listRef}
          style={{
            position: 'absolute', zIndex: 50,
            top: '100%', left: 0, right: 0,
            background: '#fff',
            border: '1.5px solid #3b82f6',
            borderRadius: 8,
            boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
            maxHeight: 220,
            overflowY: 'auto',
          }}
        >
          {filtered.map(type => (
            <div
              key={type.id}
              onMouseDown={() => handleSelect(type)}
              style={{
                padding: '10px 14px',
                cursor: 'pointer',
                fontSize: 14,
                color: '#1e293b',
                fontWeight: type.id === valueId ? 700 : 400,
                background: type.id === valueId ? '#eff6ff' : 'transparent',
                borderBottom: '1px solid #f1f5f9',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
              onMouseEnter={e => (e.currentTarget.style.background = '#f8fafc')}
              onMouseLeave={e => (e.currentTarget.style.background = type.id === valueId ? '#eff6ff' : 'transparent')}
            >
              <span>{type.name}</span>
              {type.id === valueId && (
                <span style={{ color: '#16a34a', fontSize: 13 }}>✓</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* "Non trovi la tua macchina?" */}
      {showSuggest && !suggestionSent && (
        <div style={{
          marginTop: 6,
          padding: '10px 12px',
          background: '#f0f9ff',
          border: '1px solid #7dd3fc',
          borderRadius: 8,
          fontSize: 13,
          color: '#0c4a6e',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
        }}>
          <span>Non trovi "<strong>{query}</strong>" nel catalogo?</span>
          <button
            onMouseDown={handleSuggest}
            style={{
              background: '#0ea5e9', color: '#fff', border: 'none',
              borderRadius: 6, padding: '4px 10px', fontSize: 12, fontWeight: 700,
              cursor: 'pointer', whiteSpace: 'nowrap',
            }}
          >
            Proponi
          </button>
        </div>
      )}

      {suggestionSent && (
        <div style={{
          marginTop: 6,
          padding: '8px 12px',
          background: '#f0fdf4',
          border: '1px solid #86efac',
          borderRadius: 8,
          fontSize: 12,
          color: '#166534',
        }}>
          ✓ Tipo proposto — sarà aggiunto al catalogo dopo revisione.
        </div>
      )}
    </div>
  )
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 13,
  fontWeight: 600,
  color: '#374151',
}

const inputStyle = (fromCatalog: boolean): React.CSSProperties => ({
  width: '100%',
  padding: '12px 14px',
  border: `2px solid ${fromCatalog ? '#16a34a' : '#e2e8f0'}`,
  borderRadius: 8,
  fontSize: 16,
  outline: 'none',
  boxSizing: 'border-box',
  background: fromCatalog ? '#f0fdf4' : '#fff',
  color: '#1e293b',
  fontWeight: fromCatalog ? 600 : 400,
})
