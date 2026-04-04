import type { PipelineStep } from '../../types'

interface Props {
  steps: PipelineStep[]
  progress: number
}

const STATUS_ICON: Record<PipelineStep['status'], string> = {
  idle: '○',
  running: '⟳',
  done: '✓',
  error: '✗',
}

const STATUS_COLOR: Record<PipelineStep['status'], string> = {
  idle: '#94a3b8',
  running: '#2563eb',
  done: '#16a34a',
  error: '#dc2626',
}

export function PipelineProgress({ steps, progress }: Props) {
  return (
    <div style={{ padding: '16px' }}>
      {/* Barra progresso */}
      <div style={{
        height: 6,
        background: '#e2e8f0',
        borderRadius: 3,
        marginBottom: 20,
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${progress}%`,
          background: '#1e40af',
          borderRadius: 3,
          transition: 'width 0.4s ease',
        }} />
      </div>

      {/* Steps */}
      {steps.map((step) => (
        <div
          key={step.id}
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 12,
            marginBottom: 16,
            opacity: step.status === 'idle' ? 0.4 : 1,
            transition: 'opacity 0.3s',
          }}
        >
          <div style={{
            width: 28,
            height: 28,
            borderRadius: '50%',
            background: step.status === 'idle' ? '#f1f5f9' : STATUS_COLOR[step.status] + '20',
            border: `2px solid ${STATUS_COLOR[step.status]}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 14,
            color: STATUS_COLOR[step.status],
            fontWeight: 700,
            flexShrink: 0,
            animation: step.status === 'running' ? 'spin 1s linear infinite' : 'none',
          }}>
            {STATUS_ICON[step.status]}
          </div>
          <div style={{ flex: 1 }}>
            <p style={{
              margin: 0,
              fontWeight: 600,
              fontSize: 14,
              color: STATUS_COLOR[step.status],
            }}>
              {step.label}
            </p>
            {step.message && (
              <p style={{
                margin: '2px 0 0',
                fontSize: 12,
                color: '#64748b',
                lineHeight: 1.4,
              }}>
                {step.message}
              </p>
            )}
          </div>
        </div>
      ))}

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}
