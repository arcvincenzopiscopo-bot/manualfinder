/**
 * Stili, costanti e fetch helper condivisi tra i tab del pannello admin.
 */
import type { MachineType } from '../../types'

export const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '/api') as string

export type { MachineType }

// ── API calls ────────────────────────────────────────────────────────────────

export async function apiFetch(path: string, opts?: RequestInit) {
  const r = await fetch(`${BASE_URL}/machine-types${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!r.ok) {
    const t = await r.text().catch(() => r.statusText)
    throw new Error(`HTTP ${r.status}: ${t}`)
  }
  return r.json()
}

export async function rawFetch(path: string, opts?: RequestInit) {
  const token = localStorage.getItem('admin_token') || ''
  const r = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', 'X-Admin-Token': token },
    ...opts,
  })
  if (!r.ok) {
    const t = await r.text().catch(() => r.statusText)
    throw new Error(`HTTP ${r.status}: ${t}`)
  }
  return r.json()
}

// ── Colori / stili condivisi ──────────────────────────────────────────────────

export const COLORS = {
  bg: '#f8fafc',
  card: '#fff',
  border: '#e2e8f0',
  primary: '#1e40af',
  danger: '#dc2626',
  success: '#16a34a',
  warn: '#d97706',
  muted: '#64748b',
  text: '#1e293b',
}

export const card: React.CSSProperties = {
  background: COLORS.card,
  border: `1px solid ${COLORS.border}`,
  borderRadius: 10,
  padding: '16px 18px',
  marginBottom: 16,
}

export const btn = (
  variant: 'primary' | 'danger' | 'ghost' | 'success' | 'warn' = 'primary',
  small = false,
): React.CSSProperties => ({
  padding: small ? '4px 10px' : '8px 16px',
  borderRadius: 6,
  border: 'none',
  fontWeight: 600,
  fontSize: small ? 12 : 13,
  cursor: 'pointer',
  background:
    variant === 'primary' ? COLORS.primary
    : variant === 'danger'  ? COLORS.danger
    : variant === 'success' ? COLORS.success
    : variant === 'warn'    ? COLORS.warn
    : '#f1f5f9',
  color: variant === 'ghost' ? COLORS.text : '#fff',
})

export const input: React.CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  border: `1px solid ${COLORS.border}`,
  borderRadius: 6,
  fontSize: 13,
  boxSizing: 'border-box',
  color: COLORS.text,
}

export const badge = (color: string, bg: string): React.CSSProperties => ({
  display: 'inline-block',
  padding: '2px 8px',
  borderRadius: 20,
  fontSize: 11,
  fontWeight: 700,
  color,
  background: bg,
})

// ── Tipi locali condivisi ─────────────────────────────────────────────────────

export interface Stats {
  total_types: number
  total_aliases: number
  pending_count: number
  top_types: Array<{ id: number; name: string; usage_count: number; requires_patentino: boolean; requires_verifiche: boolean }>
  stale_pending: Array<{ proposed_name: string; proposed_by: string | null; created_at: string }>
}

export interface Pending {
  id: number
  proposed_name: string
  proposed_by: string | null
  resolution: string
  ai_similarity_score: number | null
  suggested_merge_name: string | null
  created_at: string
}

export interface Alias {
  id: number
  alias_text: string
  source: string
  created_at: string
}
