/**
 * SourceBadgeBar: mostra la strategia fonte (A–F) con badge colorato, affidabilità %,
 * e pill aggiuntivi per indicare se il PDF INAIL è locale e/o se il corpus RAG era disponibile.
 */
import type { SourceMetadata } from '../../types'

interface Props {
  source: SourceMetadata
}

const _pill = (color: string, bg: string, border: string, text: string) => (
  <span style={{
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    fontSize: 11,
    fontWeight: 600,
    padding: '3px 9px',
    borderRadius: 12,
    background: bg,
    color: color,
    border: `1px solid ${border}`,
    letterSpacing: '0.02em',
    whiteSpace: 'nowrap' as const,
  }}>
    {text}
  </span>
)

export function SourceBadgeBar({ source }: Props) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>

      {/* Badge strategia principale */}
      <span style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        fontSize: 11,
        fontWeight: 700,
        padding: '3px 10px',
        borderRadius: 12,
        background: source.badge_color + '1a',
        color: source.badge_color,
        border: `1px solid ${source.badge_color}40`,
        letterSpacing: '0.02em',
      }}>
        📄 {source.badge_label}
      </span>

      {/* Affidabilità % */}
      <span style={{
        fontSize: 11,
        color: '#64748b',
        display: 'flex',
        alignItems: 'center',
        gap: 4,
      }}>
        <span style={{
          display: 'inline-block',
          width: 60,
          height: 5,
          borderRadius: 3,
          background: '#e2e8f0',
          overflow: 'hidden',
        }}>
          <span style={{
            display: 'block',
            width: `${source.affidabilita}%`,
            height: '100%',
            background: source.badge_color,
            borderRadius: 3,
            transition: 'width 0.4s ease',
          }} />
        </span>
        {source.affidabilita}% affidabilità
      </span>

      {/* Pill: quaderno INAIL locale (prevalidato dall'admin) */}
      {source.inail_is_local &&
        _pill('#065f46', '#ecfdf5', '#6ee7b7', '📂 INAIL locale')
      }

      {/* Pill: corpus RAG con quaderni INAIL indicizzati */}
      {source.rag_has_inail &&
        _pill('#1e40af', '#eff6ff', '#93c5fd', '📚 Corpus INAIL')
      }

    </div>
  )
}
