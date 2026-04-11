/**
 * SourceBadgeBar: mostra la strategia fonte (A–F) con badge colorato e affidabilità %.
 * Sostituisce/integra il badge fonte generico della SafetyCard per le card con source_metadata.
 */
import type { SourceMetadata } from '../../types'

interface Props {
  source: SourceMetadata
}

export function SourceBadgeBar({ source }: Props) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
      {/* Badge strategia */}
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
    </div>
  )
}
