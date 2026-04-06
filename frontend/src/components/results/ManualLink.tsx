import { useState } from 'react'
import { saveManual } from '../../services/api'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

interface Props {
  url: string | null
  inailUrl?: string | null
  tipo: string | null
  brand?: string
  model?: string
  machineType?: string
}

function buildPublicUrl(url: string): string {
  if (url.startsWith('/manuals/local/')) {
    const filename = url.replace('/manuals/local/', '')
    return `${API_BASE}/manuals/local/file/${encodeURIComponent(filename)}`
  }
  return url
}

function PdfLink({ url, label, color }: { url: string; label: string; color: string }) {
  return (
    <a
      href={buildPublicUrl(url)}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        padding: '7px 12px',
        background: color,
        color: '#fff',
        borderRadius: 6,
        textDecoration: 'none',
        fontSize: 12,
        fontWeight: 600,
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </a>
  )
}

function SaveManualForm({
  defaultUrl,
  defaultBrand,
  defaultModel,
  defaultMachineType,
  searchBrand,
  searchModel,
  searchMachineType,
  onSaved,
  onCancel,
}: {
  defaultUrl: string
  defaultBrand: string
  defaultModel: string
  defaultMachineType: string
  searchBrand?: string
  searchModel?: string
  searchMachineType?: string
  onSaved: () => void
  onCancel: () => void
}) {
  const [isGeneric, setIsGeneric] = useState(false)
  const [brand, setBrand] = useState(defaultBrand)
  const [model, setModel] = useState(defaultModel)
  const [machineType, setMachineType] = useState(defaultMachineType)
  const [year, setYear] = useState('')
  const [language, setLanguage] = useState('en')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSave = async () => {
    if (!machineType.trim()) return
    setSaving(true)
    setError(null)
    try {
      await saveManual({
        search_brand: searchBrand,
        search_model: searchModel,
        search_machine_type: searchMachineType,
        manual_brand: isGeneric ? 'GENERICO' : brand.trim(),
        manual_model: isGeneric ? 'CATEGORIA' : model.trim(),
        manual_machine_type: machineType.trim(),
        manual_year: year.trim() || undefined,
        manual_language: language,
        url: defaultUrl,
        is_pdf: defaultUrl.toLowerCase().includes('.pdf') || defaultUrl.includes('/local/'),
        notes: [
          isGeneric ? 'Manuale generico di categoria — non riferito a marca/modello specifici' : '',
          notes.trim(),
        ].filter(Boolean).join(' | ') || undefined,
      })
      onSaved()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Errore sconosciuto')
    } finally {
      setSaving(false)
    }
  }

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '8px 10px',
    border: '1px solid #cbd5e1',
    borderRadius: 6,
    fontSize: 13,
    boxSizing: 'border-box',
    background: '#fff',
    color: '#1e293b',
  }
  const labelStyle: React.CSSProperties = {
    display: 'block',
    fontSize: 11,
    fontWeight: 600,
    color: '#64748b',
    marginBottom: 4,
    textTransform: 'uppercase',
  }
  const canSave = machineType.trim().length > 0 && (isGeneric || (brand.trim().length > 0 && model.trim().length > 0))

  return (
    <div style={{
      marginTop: 12,
      padding: '12px',
      background: '#f8fafc',
      border: '1px solid #e2e8f0',
      borderRadius: 8,
    }}>
      <p style={{ margin: '0 0 10px', fontSize: 13, fontWeight: 700, color: '#1e293b' }}>
        💾 Salva manuale nel database
      </p>

      {/* Toggle generico / specifico */}
      <label style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        marginBottom: 12,
        cursor: 'pointer',
        fontSize: 13,
        color: '#475569',
      }}>
        <input
          type="checkbox"
          checked={isGeneric}
          onChange={e => setIsGeneric(e.target.checked)}
          style={{ width: 16, height: 16, accentColor: '#1e40af' }}
        />
        <span>
          <strong>Manuale generico di categoria</strong>
          <span style={{ color: '#94a3b8', marginLeft: 4 }}>(es. manuale INAIL di terzi, guida di settore)</span>
        </span>
      </label>

      {!isGeneric && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>Marca manuale</label>
            <input style={inputStyle} value={brand} onChange={e => setBrand(e.target.value)} placeholder="es. JCB" />
          </div>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>Modello manuale</label>
            <input style={inputStyle} value={model} onChange={e => setModel(e.target.value)} placeholder="es. 3CX" />
          </div>
        </div>
      )}

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>Tipo di macchina {isGeneric && <span style={{ color: '#dc2626' }}>*</span>}</label>
        <input style={inputStyle} value={machineType} onChange={e => setMachineType(e.target.value)} placeholder="es. carrello elevatore" />
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Anno manuale</label>
          <input style={inputStyle} value={year} onChange={e => setYear(e.target.value)} placeholder="es. 2019" inputMode="numeric" />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Lingua</label>
          <select style={inputStyle} value={language} onChange={e => setLanguage(e.target.value)}>
            <option value="it">Italiano</option>
            <option value="en">English</option>
            <option value="de">Deutsch</option>
            <option value="fr">Français</option>
            <option value="es">Español</option>
          </select>
        </div>
      </div>

      <div style={{ marginBottom: 10 }}>
        <label style={labelStyle}>Note (opzionale)</label>
        <input style={inputStyle} value={notes} onChange={e => setNotes(e.target.value)} placeholder="es. valido anche per modello XYZ" />
      </div>

      {error && (
        <p style={{ margin: '0 0 8px', fontSize: 12, color: '#dc2626' }}>⚠ {error}</p>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={handleSave}
          disabled={saving || !canSave}
          style={{
            flex: 1,
            padding: '9px',
            background: (saving || !canSave) ? '#94a3b8' : '#1e40af',
            color: '#fff',
            border: 'none',
            borderRadius: 6,
            fontWeight: 700,
            fontSize: 13,
            cursor: (saving || !canSave) ? 'not-allowed' : 'pointer',
          }}
        >
          {saving ? 'Salvataggio...' : 'Salva'}
        </button>
        <button
          onClick={onCancel}
          style={{
            padding: '9px 14px',
            background: '#fff',
            color: '#64748b',
            border: '1px solid #cbd5e1',
            borderRadius: 6,
            fontWeight: 600,
            fontSize: 13,
            cursor: 'pointer',
          }}
        >
          Annulla
        </button>
      </div>
    </div>
  )
}

export function ManualLink({ url, inailUrl, tipo, brand, model, machineType }: Props) {
  const [showForm, setShowForm] = useState(false)
  const [saved, setSaved] = useState(false)

  const isFallback = tipo === 'fallback_ai'
  const isInailOnly = tipo === 'inail'   // solo scheda INAIL locale — non ha senso salvare
  const isDual = tipo === 'inail+produttore'

  // Il salvataggio ha senso solo quando c'è un manuale produttore (non INAIL locale)
  const canSave = !isFallback && !isInailOnly && url && url.length > 0

  const manualsLibUrl = brand && model
    ? `https://www.manualslib.com/search/?q=${encodeURIComponent(brand + ' ' + model)}`
    : null
  const safeManualUrl = brand && model
    ? `https://www.safemanuals.com/?s=${encodeURIComponent(brand + ' ' + model)}`
    : null

  const labelMap: Record<string, string> = {
    pdf:              'Manuale PDF',
    inail:            'Scheda INAIL',
    'inail+produttore': 'INAIL + Manuale produttore',
    fallback_ai:      'Conoscenza AI (nessun manuale ufficiale trovato)',
  }
  const label = tipo ? (labelMap[tipo] ?? tipo) : 'Fonte sconosciuta'

  return (
    <div style={{
      background: isFallback ? '#fffbeb' : '#f0fdf4',
      border: `1px solid ${isFallback ? '#fde68a' : '#bbf7d0'}`,
      borderRadius: 8,
      padding: '12px 14px',
      marginBottom: 12,
    }}>
      <p style={{ margin: '0 0 8px', fontSize: 12, color: '#64748b', fontWeight: 600 }}>FONTE</p>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <p style={{ margin: 0, fontSize: 13, color: isFallback ? '#92400e' : '#166534', fontWeight: 600 }}>
          {label}
        </p>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          {!isFallback && inailUrl && (
            <PdfLink url={inailUrl} label="Scheda INAIL" color="#16a34a" />
          )}
          {!isFallback && url && (
            <PdfLink url={url} label={isDual ? 'Manuale produttore' : 'Apri PDF'} color="#1e40af" />
          )}
          {isFallback && manualsLibUrl && (
            <a href={manualsLibUrl} target="_blank" rel="noopener noreferrer" style={{
              padding: '7px 12px', background: '#92400e', color: '#fff',
              borderRadius: 6, textDecoration: 'none', fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap',
            }}>
              Cerca su ManualsLib
            </a>
          )}
          {isFallback && safeManualUrl && (
            <a href={safeManualUrl} target="_blank" rel="noopener noreferrer" style={{
              padding: '7px 12px', background: '#78350f', color: '#fff',
              borderRadius: 6, textDecoration: 'none', fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap',
            }}>
              Cerca su SafeManuals
            </a>
          )}
        </div>
      </div>

      {/* Banner invito al salvataggio — visibile quando c'è un manuale produttore */}
      {canSave && !saved && (
        <div style={{
          marginTop: 10,
          padding: '10px 12px',
          background: '#eff6ff',
          border: '1px solid #bfdbfe',
          borderRadius: 6,
          fontSize: 12,
          color: '#1e40af',
        }}>
          <p style={{ margin: '0 0 6px', fontWeight: 700 }}>
            📚 Hai trovato un manuale di qualità?
          </p>
          <p style={{ margin: '0 0 8px', lineHeight: 1.5, color: '#1e3a8a' }}>
            Salvarlo nel database aiuta te e i colleghi nelle prossime ispezioni.
            Puoi salvarlo come manuale specifico di questo modello oppure come
            riferimento generico per tutta la categoria di macchine.
          </p>
          {!showForm && (
            <button
              onClick={() => setShowForm(true)}
              style={{
                padding: '7px 14px',
                background: '#1e40af',
                color: '#fff',
                border: 'none',
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              💾 Salva nel database
            </button>
          )}
        </div>
      )}

      {saved && (
        <p style={{ margin: '8px 0 0', fontSize: 12, color: '#16a34a', fontWeight: 700 }}>
          ✓ Manuale salvato nel database
        </p>
      )}

      {showForm && url && (
        <SaveManualForm
          defaultUrl={url}
          defaultBrand={brand ?? ''}
          defaultModel={model ?? ''}
          defaultMachineType={machineType ?? ''}
          searchBrand={brand}
          searchModel={model}
          searchMachineType={machineType}
          onSaved={() => { setSaved(true); setShowForm(false) }}
          onCancel={() => setShowForm(false)}
        />
      )}
    </div>
  )
}
