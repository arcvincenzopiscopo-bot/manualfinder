/**
 * OcrFieldInput: input controllato con badge "⚠️ Verifica" quando il campo
 * è marcato come incerto dall'OCR multi-shot (accordo < 2/4 varianti).
 */
interface Props {
  label: string
  value: string
  onChange: (value: string) => void
  uncertain?: boolean
  placeholder?: string
  disabled?: boolean
}

export function OcrFieldInput({ label, value, onChange, uncertain, placeholder, disabled }: Props) {
  const inputId = `ocr-field-${label.toLowerCase().replace(/\s+/g, '-')}`
  return (
    <div style={{ marginBottom: 10 }}>
      <label htmlFor={inputId} style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        fontSize: 12,
        fontWeight: 600,
        color: '#475569',
        marginBottom: 4,
      }}>
        {label}
        {uncertain && (
          <span style={{
            fontSize: 10,
            fontWeight: 700,
            padding: '1px 6px',
            borderRadius: 4,
            background: '#fef9c3',
            color: '#92400e',
            border: '1px solid #fcd34d',
          }}>
            ⚠️ Verifica
          </span>
        )}
      </label>
      <input
        id={inputId}
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        style={{
          width: '100%',
          padding: '7px 10px',
          borderRadius: 6,
          border: uncertain ? '1.5px solid #fcd34d' : '1px solid #e2e8f0',
          background: uncertain ? '#fffbeb' : disabled ? '#f8fafc' : '#fff',
          fontSize: 13,
          color: '#1e293b',
          outline: 'none',
          boxSizing: 'border-box',
          transition: 'border-color 0.15s',
        }}
      />
      {uncertain && (
        <div style={{ fontSize: 10, color: '#d97706', marginTop: 3 }}>
          Le varianti OCR hanno dato risultati discordanti su questo campo — verificare in campo.
        </div>
      )}
    </div>
  )
}
