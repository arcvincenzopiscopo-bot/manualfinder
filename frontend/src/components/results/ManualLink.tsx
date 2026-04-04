const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

interface Props {
  url: string | null
  inailUrl?: string | null
  tipo: string | null
  brand?: string
  model?: string
}

/** Converte l'URL interno del backend in un link apribile nel browser. */
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

export function ManualLink({ url, inailUrl, tipo, brand, model }: Props) {
  const isFallback = tipo === 'fallback_ai'
  const isDual = tipo === 'inail+produttore'

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
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {!isFallback && inailUrl && (
            <PdfLink url={inailUrl} label="Scheda INAIL" color="#16a34a" />
          )}
          {!isFallback && url && (
            <PdfLink url={url} label={isDual ? 'Manuale produttore' : 'Apri PDF'} color="#1e40af" />
          )}
          {isFallback && manualsLibUrl && (
            <a
              href={manualsLibUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                padding: '7px 12px',
                background: '#92400e',
                color: '#fff',
                borderRadius: 6,
                textDecoration: 'none',
                fontSize: 12,
                fontWeight: 600,
                whiteSpace: 'nowrap',
              }}
            >
              Cerca su ManualsLib
            </a>
          )}
          {isFallback && safeManualUrl && (
            <a
              href={safeManualUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                padding: '7px 12px',
                background: '#78350f',
                color: '#fff',
                borderRadius: 6,
                textDecoration: 'none',
                fontSize: 12,
                fontWeight: 600,
                whiteSpace: 'nowrap',
              }}
            >
              Cerca su SafeManuals
            </a>
          )}
        </div>
      </div>
    </div>
  )
}
