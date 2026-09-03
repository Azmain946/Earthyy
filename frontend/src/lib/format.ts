import { format, formatDistanceToNow, parseISO } from 'date-fns'

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return format(parseISO(iso), 'yyyy-MM-dd')
  } catch {
    return iso
  }
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return format(parseISO(iso), 'yyyy-MM-dd HH:mm ')
  } catch {
    return iso
  }
}

export function fmtAgo(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return formatDistanceToNow(parseISO(iso), { addSuffix: true })
  } catch {
    return iso
  }
}

export function fmtNum(v: unknown, digits = 2): string {
  if (v === null || v === undefined || typeof v !== 'number' || !isFinite(v)) return '—'
  return v.toLocaleString(undefined, { maximumFractionDigits: digits })
}

export function fmtConfidence(score: number | null, level: string): string {
  if (score === null) return `unavailable`
  return `${Math.round(score * 100)}% (${level})`
}

export const MODULE_META: Record<
  string,
  { label: string; icon: string; color: string; navBadge: string }
> = {
  overview: { label: 'Overview', icon: 'dashboard', color: '#00507d', navBadge: '' },
  river: { label: 'River Hydrology', icon: 'waves', color: '#0369a1', navBadge: 'Padma' },
  agriculture: { label: 'Agriculture & Crop', icon: 'agriculture', color: '#006d30', navBadge: 'NDVI' },
  forest: { label: 'Forest Canopy', icon: 'forest', color: '#006d30', navBadge: 'Delta' },
  brick_kiln: { label: 'Brick Kilns', icon: 'factory', color: '#b53801', navBadge: '' },
}
