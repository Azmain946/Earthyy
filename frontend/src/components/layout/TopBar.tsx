import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { alertService, searchService } from '../../services'
import type { SearchResult } from '../../lib/types'

interface TopBarProps {
  onLocate: (r: SearchResult) => void
  onToggleAlerts: () => void
  contextBadges?: React.ReactNode
  actions?: React.ReactNode
}

export default function TopBar({ onLocate, onToggleAlerts, contextBadges, actions }: TopBarProps) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [open, setOpen] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  const { data: alerts } = useQuery({
    queryKey: ['alerts', 'unread'],
    queryFn: () => alertService.list('unread'),
    refetchInterval: 30000,
  })

  useEffect(() => {
    if (q.length < 3) {
      setResults([])
      return
    }
    clearTimeout(timer.current)
    timer.current = setTimeout(async () => {
      try {
        const { results } = await searchService.query(q)
        setResults(results)
        setOpen(true)
      } catch {
        setResults([])
      }
    }, 400)
    return () => clearTimeout(timer.current)
  }, [q])

  return (
    <header className="fixed top-0 right-0 left-sidebar-width z-30 flex items-center justify-between px-3 h-12 bg-surface-container-low border-b border-outline-variant gap-2">
      <div className="flex items-center gap-3 min-w-0">
        {/* Geographic search */}
        <div className="relative">
          <span className="material-symbols-outlined absolute left-2 top-1/2 -translate-y-1/2 text-outline text-base pointer-events-none" aria-hidden>
            search
          </span>
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onFocus={() => results.length && setOpen(true)}
            onBlur={() => setTimeout(() => setOpen(false), 250)}
            placeholder="Search upazila, river, place, zone…"
            aria-label="Geographic search"
            className="h-7 w-64 pl-8 pr-3 bg-surface-container-lowest border border-outline-variant rounded text-xs text-on-surface placeholder:text-outline focus:outline-none focus:border-primary focus:ring-0"
          />
          {open && results.length > 0 && (
            <div className="absolute top-9 left-0 w-96 max-h-80 overflow-y-auto bg-surface-container-lowest border border-outline-variant rounded-lg shadow-xl z-50">
              {results.map((r, i) => (
                <button
                  key={i}
                  onMouseDown={() => {
                    onLocate(r)
                    setOpen(false)
                    setQ('')
                  }}
                  className="w-full text-left px-3 py-2 hover:bg-surface-container flex items-start gap-2 border-b border-outline-variant/50 last:border-0"
                >
                  <span className="material-symbols-outlined text-base text-primary mt-0.5" aria-hidden>
                    {r.kind === 'monitoring_zone' ? 'radar' : 'location_on'}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-xs text-on-surface truncate">{r.name}</span>
                    <span className="block text-label-coord font-mono text-outline">
                      {r.kind === 'monitoring_zone' ? `zone · ${r.zone_type}` : r.category} · {r.lat.toFixed(3)}°N{' '}
                      {r.lon.toFixed(3)}°E
                    </span>
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
        {/* Context telemetry badges */}
        <div className="hidden xl:flex items-center gap-1.5 min-w-0 overflow-hidden">{contextBadges}</div>
      </div>

      <div className="flex items-center gap-1.5">
        {actions}
        <button
          onClick={onToggleAlerts}
          className="relative flex items-center gap-1.5 h-7 px-2.5 bg-surface-container-lowest border border-outline-variant rounded text-telemetry font-mono text-on-surface hover:bg-surface-container transition-colors"
          aria-label={`Alerts (${alerts?.length ?? 0} unread)`}
        >
          {alerts && alerts.length > 0 && (
            <span className="relative flex h-2 w-2" aria-hidden>
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-tertiary-container opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-tertiary-container"></span>
            </span>
          )}
          <span className="material-symbols-outlined text-base" aria-hidden>notifications</span>
          <span>{alerts?.length ?? 0} Alerts</span>
        </button>
      </div>
    </header>
  )
}
