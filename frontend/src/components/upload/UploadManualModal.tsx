import { useState, useRef } from 'react'
import { uploadManual } from '../../services/api'
import { MachineTypeSelector } from '../ocr/MachineTypeSelector'

interface Props {
  onClose: () => void
  /** Pre-compila i campi se aperto dalla scheda sicurezza */
  defaultBrand?: string
  defaultModel?: string
  defaultMachineType?: string
  defaultMachineTypeId?: number | null
}

type ModalState = 'form' | 'uploading' | 'mismatch' | 'success' | 'error'

interface Suggestions {
  brand: string
  model: string
  machine_type: string
  reason: string
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '9px 11px',
  border: '1px solid #cbd5e1',
  borderRadius: 6,
  fontSize: 14,
  boxSizing: 'border-box',
  background: '#fff',
  color: '#1e293b',
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 12,
  fontWeight: 600,
  color: '#64748b',
  marginBottom: 4,
  textTransform: 'uppercase',
  letterSpacing: '0.03em',
}

export function UploadManualModal({ onClose, defaultBrand = '', defaultModel = '', defaultMachineType = '', defaultMachineTypeId = null }: Props) {
  const [uiState, setUiState] = useState<ModalState>('form')
  const [file, setFile] = useState<File | null>(null)
  const [brand, setBrand] = useState(defaultBrand)
  const [model, setModel] = useState(defaultModel)
  const [machineType, setMachineType] = useState(defaultMachineType)
  const [machineTypeId, setMachineTypeId] = useState<number | null>(defaultMachineTypeId)
  const [year, setYear] = useState('')
  const [language, setLanguage] = useState('it')
  const [isGeneric, setIsGeneric] = useState(false)
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const [suggestions, setSuggestions] = useState<Suggestions | null>(null)
  const [successUrl, setSuccessUrl] = useState('')
  const [storageWarning, setStorageWarning] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Il tipo macchina deve essere selezionato dal catalogo (machineTypeId != null)
  const canSubmit = !!file && machineTypeId != null && (isGeneric || (brand.trim().length > 0 && model.trim().length > 0))

  const doUpload = async (force: boolean, overrides?: Partial<{ brand: string; model: string; machine_type: string }>) => {
    if (!file || uiState === 'uploading') return
    setUiState('uploading')
    try {
      const result = await uploadManual(file, {
        brand: overrides?.brand ?? brand,
        model: overrides?.model ?? model,
        machine_type: overrides?.machine_type ?? machineType,
        machine_type_id: machineTypeId,
        manual_year: year || undefined,
        manual_language: language,
        is_generic: isGeneric,
        notes: notes || undefined,
        force,
      })
      if (result.status === 'mismatch' && result.suggestions) {
        setSuggestions(result.suggestions)
        setUiState('mismatch')
      } else {
        setSuccessUrl(result.url ?? '')
        setStorageWarning(result.storage_warning ?? null)
        setUiState('success')
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Errore sconosciuto')
      setUiState('error')
    }
  }

  const isUploading = uiState === 'uploading'

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'flex-end',
    }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div style={{
        width: '100%', maxWidth: 480, margin: '0 auto',
        background: '#fff',
        borderRadius: '16px 16px 0 0',
        padding: '20px 16px 32px',
        maxHeight: '92dvh',
        overflowY: 'auto',
      }}>
        {/* Handle bar */}
        <div style={{ width: 40, height: 4, background: '#e2e8f0', borderRadius: 2, margin: '0 auto 16px' }} />

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: '#1e293b' }}>
            📤 Carica manuale PDF
          </h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 22, cursor: 'pointer', color: '#94a3b8' }}>×</button>
        </div>

        {/* ── FORM ── */}
        {uiState === 'form' && (
          <>
            {/* File picker */}
            <div style={{
              border: '2px dashed #93c5fd', borderRadius: 10, padding: '20px',
              textAlign: 'center', marginBottom: 16, cursor: 'pointer',
              background: file ? '#eff6ff' : '#f8fafc',
            }}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf,.pdf"
                style={{ display: 'none' }}
                onChange={e => setFile(e.target.files?.[0] ?? null)}
              />
              {file ? (
                <>
                  <p style={{ margin: '0 0 4px', fontSize: 16 }}>📄</p>
                  <p style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#1e40af' }}>{file.name}</p>
                  <p style={{ margin: '2px 0 0', fontSize: 12, color: '#64748b' }}>
                    {(file.size / 1024 / 1024).toFixed(1)} MB
                  </p>
                </>
              ) : (
                <>
                  <p style={{ margin: '0 0 6px', fontSize: 24 }}>📁</p>
                  <p style={{ margin: 0, fontSize: 14, fontWeight: 600, color: '#1e40af' }}>Seleziona un PDF</p>
                  <p style={{ margin: '4px 0 0', fontSize: 12, color: '#94a3b8' }}>Solo PDF con testo nativo (non scansioni)</p>
                </>
              )}
            </div>

            {/* Checkbox generico */}
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14, cursor: 'pointer', fontSize: 13, color: '#475569' }}>
              <input
                type="checkbox" checked={isGeneric}
                onChange={e => setIsGeneric(e.target.checked)}
                style={{ width: 16, height: 16, accentColor: '#1e40af' }}
              />
              <span>
                <strong>Manuale generico di categoria</strong>
                <span style={{ color: '#94a3b8', marginLeft: 4 }}>(non legato a marca/modello specifici)</span>
              </span>
            </label>

            {/* Campi dati */}
            {!isGeneric && (
              <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                <div style={{ flex: 1 }}>
                  <label style={labelStyle}>Marca *</label>
                  <input style={inputStyle} value={brand} onChange={e => setBrand(e.target.value)} placeholder="es. JCB" />
                </div>
                <div style={{ flex: 1 }}>
                  <label style={labelStyle}>Modello *</label>
                  <input style={inputStyle} value={model} onChange={e => setModel(e.target.value)} placeholder="es. 3CX" />
                </div>
              </div>
            )}

            <div style={{ marginBottom: 10 }}>
              <MachineTypeSelector
                value={machineType}
                valueId={machineTypeId}
                onChange={(name, id) => { setMachineType(name); setMachineTypeId(id) }}
              />
              {machineType.trim().length > 0 && machineTypeId == null && (
                <div style={{
                  marginTop: 6, padding: '8px 10px',
                  background: '#fff7ed', border: '1px solid #fed7aa',
                  borderRadius: 6, fontSize: 12, color: '#9a3412',
                }}>
                  ⚠ Seleziona un tipo dal catalogo per poter caricare. Se il tipo non è presente, usa il pulsante <strong>Proponi</strong> e attendi l'approvazione dell'admin.
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
              <div style={{ flex: 1 }}>
                <label style={labelStyle}>Anno manuale</label>
                <input style={inputStyle} value={year} onChange={e => setYear(e.target.value)} placeholder="es. 2021" inputMode="numeric" />
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

            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>Note (opzionale)</label>
              <input style={inputStyle} value={notes} onChange={e => setNotes(e.target.value)} placeholder="es. valido anche per modello XYZ" />
            </div>

            <button
              onClick={() => doUpload(false)}
              disabled={!canSubmit || isUploading}
              style={{
                width: '100%', padding: '14px',
                background: canSubmit && !isUploading ? '#1e40af' : '#cbd5e1',
                color: '#fff', border: 'none', borderRadius: 8,
                fontSize: 16, fontWeight: 700,
                cursor: canSubmit ? 'pointer' : 'not-allowed',
              }}
            >
              Carica e valida
            </button>
          </>
        )}

        {/* ── UPLOADING ── */}
        {uiState === 'uploading' && (
          <div style={{ textAlign: 'center', padding: '32px 0' }}>
            <p style={{ fontSize: 32, margin: '0 0 12px' }}>⏳</p>
            <p style={{ fontSize: 15, fontWeight: 700, color: '#1e40af' }}>Validazione in corso…</p>
            <p style={{ fontSize: 13, color: '#64748b', margin: '6px 0 0' }}>
              Controllo testo nativo e verifica congruenza con AI
            </p>
          </div>
        )}

        {/* ── MISMATCH ── */}
        {uiState === 'mismatch' && suggestions && (
          <>
            <div style={{
              background: '#fffbeb', border: '1px solid #fde68a',
              borderRadius: 8, padding: '12px 14px', marginBottom: 16,
            }}>
              <p style={{ margin: '0 0 6px', fontSize: 14, fontWeight: 700, color: '#92400e' }}>
                ⚠ L'AI ha trovato dati diversi nel PDF
              </p>
              <p style={{ margin: '0 0 10px', fontSize: 13, color: '#78350f' }}>{suggestions.reason}</p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 12px', fontSize: 13 }}>
                {[
                  { label: 'Marca', yours: brand, ai: suggestions.brand },
                  { label: 'Modello', yours: model, ai: suggestions.model },
                  { label: 'Tipo macchina', yours: machineType, ai: suggestions.machine_type },
                ].map(row => (
                  <div key={row.label} style={{ gridColumn: '1 / -1', display: 'flex', gap: 8, alignItems: 'baseline' }}>
                    <span style={{ fontWeight: 600, color: '#64748b', minWidth: 90 }}>{row.label}:</span>
                    <span style={{ color: '#dc2626', textDecoration: 'line-through', marginRight: 4 }}>{row.yours}</span>
                    <span style={{ color: '#16a34a', fontWeight: 700 }}>→ {row.ai}</span>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <button
                onClick={() => {
                  setBrand(suggestions.brand)
                  setModel(suggestions.model)
                  setMachineType(suggestions.machine_type)
                  doUpload(true, { brand: suggestions.brand, model: suggestions.model, machine_type: suggestions.machine_type })
                }}
                style={{
                  padding: '13px', background: '#16a34a', color: '#fff',
                  border: 'none', borderRadius: 8, fontSize: 15, fontWeight: 700, cursor: 'pointer',
                }}
              >
                ✓ Usa dati suggeriti dall'AI
              </button>
              <button
                onClick={() => doUpload(true)}
                style={{
                  padding: '13px', background: '#fff', color: '#475569',
                  border: '1px solid #cbd5e1', borderRadius: 8, fontSize: 15, fontWeight: 600, cursor: 'pointer',
                }}
              >
                Carica comunque con i dati originali
              </button>
              <button
                onClick={() => setUiState('form')}
                style={{
                  padding: '10px', background: 'none', color: '#94a3b8',
                  border: 'none', fontSize: 13, cursor: 'pointer',
                }}
              >
                ← Torna al form
              </button>
            </div>
          </>
        )}

        {/* ── SUCCESS ── */}
        {uiState === 'success' && (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <p style={{ fontSize: 40, margin: '0 0 12px' }}>✅</p>
            <p style={{ fontSize: 16, fontWeight: 800, color: '#16a34a', margin: '0 0 8px' }}>
              Manuale salvato con successo
            </p>
            {storageWarning ? (
              <div style={{
                margin: '0 0 16px', padding: '10px 12px', textAlign: 'left',
                background: '#fef3c7', border: '1px solid #f59e0b',
                borderRadius: 8, fontSize: 12, color: '#92400e', lineHeight: 1.5,
              }}>
                ⚠ <strong>Storage non persistente:</strong> {storageWarning}
              </div>
            ) : (
              <p style={{ fontSize: 12, color: '#16a34a', margin: '0 0 12px' }}>
                ☁ Salvato su Supabase Storage — sopravvive ai redeploy
              </p>
            )}
            <p style={{ fontSize: 13, color: '#475569', margin: '0 0 20px', lineHeight: 1.5 }}>
              Il manuale è ora disponibile nelle future ricerche per questo tipo di macchina.
            </p>
            <button
              onClick={onClose}
              style={{
                padding: '12px 24px', background: '#1e40af', color: '#fff',
                border: 'none', borderRadius: 8, fontSize: 15, fontWeight: 700, cursor: 'pointer',
              }}
            >
              Chiudi
            </button>
          </div>
        )}

        {/* ── ERROR ── */}
        {uiState === 'error' && (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <p style={{ fontSize: 36, margin: '0 0 12px' }}>❌</p>
            <p style={{ fontSize: 15, fontWeight: 700, color: '#dc2626', margin: '0 0 8px' }}>
              Caricamento fallito
            </p>
            <p style={{ fontSize: 13, color: '#475569', margin: '0 0 20px', lineHeight: 1.5 }}>
              {error}
            </p>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
              <button
                onClick={() => setUiState('form')}
                style={{
                  padding: '10px 18px', background: '#1e40af', color: '#fff',
                  border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 700, cursor: 'pointer',
                }}
              >
                Riprova
              </button>
              <button
                onClick={onClose}
                style={{
                  padding: '10px 18px', background: '#fff', color: '#64748b',
                  border: '1px solid #cbd5e1', borderRadius: 8, fontSize: 14, cursor: 'pointer',
                }}
              >
                Chiudi
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
