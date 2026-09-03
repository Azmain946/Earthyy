import { fmtDate, fmtNum } from '../lib/format'
import { fileUrl } from '../lib/api'
import type { Observation } from '../lib/types'

interface EarthTimeProps {
  observations: Observation[]
  selectedId: number | null
  onSelect: (obs: Observation) => void
}

/** Earth Time: scrub through actual stored observations (no fabricated frames). */
export default function EarthTime({ observations, selectedId, onSelect }: EarthTimeProps) {
  if (observations.length === 0) {
    return (
      <div className="p-3 text-xs text-on-surface-variant bg-surface-container-low rounded border border-outline-variant">
        No historical observations stored yet for this zone. Run an analysis to build the Earth record.
      </div>
    )
  }
  const primaryMetric = (o: Observation): string => {
    const m = o.measurements as Record<string, number>
    if (m.water_area_km2 !== undefined) return `${fmtNum(m.water_area_km2, 1)} km² water`
    if (m.mean_ndvi !== undefined) return `NDVI ${fmtNum(m.mean_ndvi, 2)}`
    if (m.forest_area_ha !== undefined) return `${fmtNum(m.forest_area_ha, 0)} ha canopy`
    if (m.candidate_count !== undefined) return `${m.candidate_count} candidates`
    return ''
  }
  return (
    <div className="space-y-1.5" aria-label="Earth Time observation timeline">
      {observations.map((o) => {
        const selected = o.id === selectedId
        return (
          <button
            key={o.id}
            onClick={() => onSelect(o)}
            className={`w-full flex items-center justify-between p-1.5 rounded border transition-colors text-left ${
              selected
                ? 'border-primary border-2 bg-surface-container'
                : 'border-outline-variant hover:bg-surface-container'
            }`}
          >
            <span className="flex items-center gap-2.5 min-w-0">
              {o.preview_path ? (
                <img
                  src={fileUrl(o.preview_path)}
                  alt={`Satellite preview ${fmtDate(o.observed_at)}`}
                  className="w-10 h-8 rounded object-cover border border-outline-variant bg-inverse-surface"
                  loading="lazy"
                />
              ) : (
                <span className="w-10 h-8 rounded bg-surface-container-highest border border-outline-variant flex items-center justify-center text-label-coord font-mono text-outline">
                  '{fmtDate(o.observed_at).slice(2, 4)}
                </span>
              )}
              <span className="flex flex-col min-w-0">
                <span className="text-xs font-semibold text-on-surface">{fmtDate(o.observed_at)}</span>
                <span className="text-label-coord font-mono text-outline truncate">{primaryMetric(o)}</span>
              </span>
            </span>
            <span className={`w-2 h-2 rounded-full shrink-0 ${selected ? 'bg-primary animate-pulse' : 'bg-secondary'}`} aria-hidden />
          </button>
        )
      })}
    </div>
  )
}
