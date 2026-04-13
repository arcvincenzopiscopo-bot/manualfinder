/**
 * Componenti UI condivisi tra i tab del pannello admin.
 */
import type React from 'react'
import { COLORS, btn, badge } from './admin-shared'

export function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700, color: COLORS.text }}>{children}</h3>
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return <p style={{ fontSize: 13, color: COLORS.muted, textAlign: 'center', padding: '20px 0' }}>{children}</p>
}

export function LoadingSpinner() {
  return <p style={{ fontSize: 13, color: COLORS.muted, padding: '20px 0', textAlign: 'center' }}>Caricamento...</p>
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div style={{ background: '#fef2f2', border: `1px solid #fca5a5`, borderRadius: 8, padding: '12px 14px', marginBottom: 12 }}>
      <span style={{ color: COLORS.danger, fontSize: 13 }}>⚠ {message}</span>
      <button onClick={onRetry} style={{ ...btn('ghost', true), marginLeft: 12 }}>Riprova</button>
    </div>
  )
}

export function KpiCard({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <div style={{
      background: '#fff', border: `1px solid ${COLORS.border}`, borderRadius: 10,
      padding: '14px 16px', textAlign: 'center',
    }}>
      <div style={{ fontSize: 28, fontWeight: 800, color }}>{value}</div>
      <div style={{ fontSize: 12, color: COLORS.muted, marginTop: 2 }}>{label}</div>
    </div>
  )
}

export function Th({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return (
    <th style={{
      textAlign: right ? 'right' : 'left',
      padding: '6px 8px',
      fontSize: 11,
      fontWeight: 700,
      color: COLORS.muted,
      textTransform: 'uppercase',
    }}>
      {children}
    </th>
  )
}

export function Td({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return (
    <td style={{ padding: '7px 8px', textAlign: right ? 'right' : 'left', fontSize: 13, color: COLORS.text }}>
      {children}
    </td>
  )
}

export function YesBadge() {
  return <span style={badge(COLORS.success, '#f0fdf4')}>✓ sì</span>
}

export function NoBadge() {
  return <span style={badge(COLORS.muted, '#f1f5f9')}>— no</span>
}
