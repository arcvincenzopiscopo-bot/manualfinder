import { useState, useRef } from 'react'
import type { PlateOCRResult } from '../../types'
import { inferMachineType } from '../../services/api'

interface Props {
  ocr: PlateOCRResult & { brightness_warning?: string }
  onConfirm: (brand: string, model: string, serial: string, year: string, machineType: string) => void
  onRetake: () => void
}

const CONFIDENCE_STYLE = {
  high:   { bg: '#f0fdf4', border: '#86efac', color: '#166534', label: 'Alta' },
  medium: { bg: '#fffbeb', border: '#fde68a', color: '#92400e', label: 'Media' },
  low:    { bg: '#fef2f2', border: '#fca5a5', color: '#991b1b', label: 'Bassa' },
}

export function OcrConfirmForm({ ocr, onConfirm, onRetake }: Props) {
  const [brand, setBrand] = useState(ocr.brand ?? '')
  const [model, setModel] = useState(ocr.model ?? '')
  const [machineType, setMachineType] = useState(ocr.machine_type ?? '')
  const [serial, setSerial] = useState(ocr.serial_number ?? '')
  const [year, setYear] = useState(ocr.year ?? '')
  const [inferring, setInferring] = useState(false)
  // Tiene traccia dell'ultima coppia brand+model per cui è stata fatta l'inferenza
  const lastInferred = useRef<string>('')

  const handleBrandModelBlur = async () => {
    const b = brand.trim()
    const m = model.trim()
    if (!b && !m) return
    const key = `${b}|${m}`
    if (key === lastInferred.current) return  // già aggiornato per questa coppia
    lastInferred.current = key
    setInferring(true)
    try {
      const result = await inferMachineType(b, m, machineType.trim() || undefined)
      if (result) setMachineType(result)
    } catch {
      // silenzioso — l'utente può inserire il tipo manualmente
    } finally {
      setInferring(false)
    }
  }

  const conf = CONFIDENCE_STYLE[ocr.confidence] ?? CONFIDENCE_STYLE.low
  const canConfirm = brand.trim().length > 0 || model.trim().length > 0

  return (
    <div style={{ padding: '16px' }}>

      {/* Tipo macchina - campo informativo */}
      {machineType && (
        <div style={{
          background: '#f0f9ff',
          border: '1px solid #7dd3fc',
          borderRadius: 8,
          padding: '10px 12px',
          marginBottom: 16,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}>
          <span style={{ fontSize: 16 }}>🏗️</span>
          <div>
            <p style={{ margin: 0, fontSize: 11, color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>
              Tipo di macchina
            </p>
            <p style={{ margin: '2px 0 0', fontSize: 14, color: '#0c4a6e', fontWeight: 600 }}>
              {machineType}
            </p>
          </div>
        </div>
      )}

      {/* Badge confidenza */}
      <div style={{
        background: conf.bg,
        border: `1px solid ${conf.border}`,
        borderRadius: 10,
        padding: '12px 14px',
        marginBottom: 16,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div>
          <p style={{ margin: 0, fontSize: 12, color: '#64748b', fontWeight: 600 }}>
            RISULTATO OCR — CONFIDENZA {conf.label.toUpperCase()}
          </p>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: conf.color }}>
            Verifica i dati estratti e correggili se necessario prima di procedere.
          </p>
        </div>
        <span style={{
          background: conf.border,
          color: conf.color,
          fontWeight: 800,
          fontSize: 12,
          padding: '4px 10px',
          borderRadius: 20,
        }}>
          {conf.label}
        </span>
      </div>

      {/* Avviso luminosità */}
      {(ocr.brightness_warning || ocr.notes) && (
        <div style={{
          background: '#fffbeb',
          border: '1px solid #fde68a',
          borderRadius: 8,
          padding: '10px 12px',
          marginBottom: 16,
          fontSize: 13,
          color: '#92400e',
        }}>
          ⚠️ {ocr.brightness_warning ?? ocr.notes}
        </div>
      )}

      {/* Campi modificabili */}
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>
          Marca (produttore)
        </label>
        <input
          type="text"
          value={brand}
          onChange={e => setBrand(e.target.value)}
          onBlur={handleBrandModelBlur}
          placeholder="es. Caterpillar"
          style={inputStyle(!!brand)}
          autoCapitalize="words"
        />

        <label style={{ ...labelStyle, marginTop: 12 }}>
          Modello
        </label>
        <input
          type="text"
          value={model}
          onChange={e => setModel(e.target.value)}
          onBlur={handleBrandModelBlur}
          placeholder="es. 320D"
          style={inputStyle(!!model)}
          autoCapitalize="characters"
        />

        <label style={{ ...labelStyle, marginTop: 12 }}>
          Tipo di macchina (per ricerca INAIL)
          {inferring && (
            <span style={{ marginLeft: 8, fontSize: 11, color: '#3b82f6', fontWeight: 400 }}>
              ⟳ Rilevamento...
            </span>
          )}
        </label>
        <input
          type="text"
          value={inferring ? '' : machineType}
          onChange={e => { if (!inferring) setMachineType(e.target.value) }}
          placeholder={inferring ? 'Rilevamento tipo in corso...' : 'es. piattaforma aerea, escavatore, gru'}
          style={{ ...inputStyle(!!machineType && !inferring), opacity: inferring ? 0.6 : 1 }}
          autoCapitalize="sentences"
          disabled={inferring}
        />

        <div style={{ display: 'flex', gap: 12, marginTop: 12 }}>
          <div style={{ flex: 2 }}>
            <label style={labelStyle}>N° serie / matricola</label>
            <input
              type="text"
              value={serial}
              onChange={e => setSerial(e.target.value)}
              placeholder="es. CAT0123456"
              style={inputStyle(!!serial)}
              autoCapitalize="characters"
            />
          </div>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>Anno</label>
            <input
              type="text"
              value={year}
              onChange={e => setYear(e.target.value)}
              placeholder="es. 2019"
              style={inputStyle(!!year)}
              inputMode="numeric"
            />
          </div>
        </div>

        {/* Testo grezzo OCR (collassabile) */}
        {ocr.raw_text && (
          <details style={{ marginTop: 10 }}>
            <summary style={{ fontSize: 12, color: '#94a3b8', cursor: 'pointer' }}>
              Testo grezzo OCR
            </summary>
            <pre style={{
              fontSize: 11,
              color: '#64748b',
              background: '#f8fafc',
              borderRadius: 6,
              padding: 8,
              marginTop: 6,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}>
              {ocr.raw_text}
            </pre>
          </details>
        )}
      </div>

      {/* Azioni */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <button
          onClick={() => onConfirm(brand.trim(), model.trim(), serial.trim(), year.trim(), machineType.trim())}
          disabled={!canConfirm}
          style={{
            padding: '14px',
            borderRadius: 8,
            border: 'none',
            background: canConfirm ? '#1e40af' : '#cbd5e1',
            color: '#fff',
            fontWeight: 700,
            fontSize: 16,
            cursor: canConfirm ? 'pointer' : 'not-allowed',
          }}
        >
          Conferma e cerca il manuale →
        </button>

        <button
          onClick={onRetake}
          style={{
            padding: '12px',
            borderRadius: 8,
            border: '1px solid #cbd5e1',
            background: '#fff',
            color: '#475569',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Riprendi la foto
        </button>
      </div>
    </div>
  )
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 13,
  fontWeight: 600,
  color: '#374151',
  marginBottom: 6,
}

const inputStyle = (hasValue: boolean): React.CSSProperties => ({
  width: '100%',
  padding: '12px 14px',
  border: `2px solid ${hasValue ? '#3b82f6' : '#e2e8f0'}`,
  borderRadius: 8,
  fontSize: 16,
  outline: 'none',
  boxSizing: 'border-box',
  background: hasValue ? '#eff6ff' : '#fff',
  color: '#1e293b',
  fontWeight: hasValue ? 600 : 400,
})

