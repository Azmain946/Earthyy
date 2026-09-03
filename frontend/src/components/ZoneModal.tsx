import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { zoneService } from '../services'
import type { GeoJSONGeometry, ZoneType } from '../lib/types'

interface ZoneModalProps {
  open: boolean
  onClose: () => void
  geometry?: GeoJSONGeometry | null
  defaultType?: ZoneType
  onCreated?: (zoneId: number) => void
}

const TYPE_OPTIONS: Array<{ value: ZoneType; label: string }> = [
  { value: 'river', label: 'River Hydrology & Morphometry' },
  { value: 'agriculture', label: 'Agricultural Crop Condition' },
  { value: 'forest', label: 'Forest Canopy Continuity' },
  { value: 'brick_kiln', label: 'Brick Kiln Cluster' },
  { value: 'general', label: 'General Observation' },
]

const DEFAULT_THRESHOLDS: Record<string, Record<string, number>> = {
  river: { erosion_km2: 0.05, movement_m_per_year: 25 },
  agriculture: { ndvi_drop_pct: 15, stress_area_ha: 5 },
  forest: { forest_loss_ha: 1 },
  brick_kiln: { new_candidates: 1 },
  general: {},
}

export default function ZoneModal({ open, onClose, geometry, defaultType = 'general', onCreated }: ZoneModalProps) {
  const [name, setName] = useState('')
  const [zoneType, setZoneType] = useState<ZoneType>(defaultType)
  const [baselineDate, setBaselineDate] = useState('2022-01-15')
  const [description, setDescription] = useState('')
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: () =>
      zoneService.create({
        name,
        zone_type: zoneType,
        geometry: geometry!,
        baseline_date: baselineDate || undefined,
        thresholds: DEFAULT_THRESHOLDS[zoneType],
        description,
      }),
    onSuccess: (zone) => {
      qc.invalidateQueries({ queryKey: ['zones'] })
      onCreated?.(zone.id)
      onClose()
      setName('')
    },
  })

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-inverse-surface/60 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Create monitoring zone">
      <div className="w-full max-w-lg bg-surface-container-lowest rounded-xl border border-outline-variant shadow-2xl p-5">
        <div className="flex items-center justify-between pb-2.5 border-b border-outline-variant mb-3">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-xl" aria-hidden>add_location_alt</span>
            <h3 className="font-semibold text-on-surface">Create Monitoring Zone</h3>
          </div>
          <button onClick={onClose} className="text-outline hover:text-on-surface" aria-label="Close">
            <span className="material-symbols-outlined" aria-hidden>close</span>
          </button>
        </div>

        {!geometry ? (
          <div className="p-3 bg-surface-container-low rounded border border-outline-variant text-xs text-on-surface-variant">
            <span className="font-semibold text-on-surface">No geometry drawn.</span> Close this dialog, use the polygon
            tool on the map (top-right) to draw the area you want to monitor, then click “Monitoring Zones” again.
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <label className="block text-telemetry font-mono text-on-surface mb-1" htmlFor="zone-name">Zone Identifier Name</label>
              <input
                id="zone-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Lower Meghna Riverbank Erosion Sector"
                className="w-full h-8 px-2.5 bg-surface-container-low border border-outline-variant rounded text-xs focus:outline-none focus:border-primary focus:ring-0"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-telemetry font-mono text-on-surface mb-1" htmlFor="zone-type">Observable Domain</label>
                <select
                  id="zone-type"
                  value={zoneType}
                  onChange={(e) => setZoneType(e.target.value as ZoneType)}
                  className="w-full h-8 px-2 bg-surface-container-low border border-outline-variant rounded text-xs focus:outline-none focus:border-primary focus:ring-0"
                >
                  {TYPE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-telemetry font-mono text-on-surface mb-1" htmlFor="zone-baseline">Baseline Date</label>
                <input
                  id="zone-baseline"
                  type="date"
                  value={baselineDate}
                  onChange={(e) => setBaselineDate(e.target.value)}
                  className="w-full h-8 px-2 bg-surface-container-low border border-outline-variant rounded text-xs focus:outline-none focus:border-primary focus:ring-0"
                />
              </div>
            </div>
            <div>
              <label className="block text-telemetry font-mono text-on-surface mb-1" htmlFor="zone-desc">Description (optional)</label>
              <input
                id="zone-desc"
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full h-8 px-2.5 bg-surface-container-low border border-outline-variant rounded text-xs focus:outline-none focus:border-primary focus:ring-0"
              />
            </div>
            <div className="p-2.5 bg-surface-container-low rounded border border-outline-variant text-label-coord font-mono text-on-surface-variant">
              <span className="font-bold text-on-surface">Alert thresholds:</span>{' '}
              {Object.entries(DEFAULT_THRESHOLDS[zoneType]).map(([k, v]) => `${k}=${v}`).join(' · ') || 'none'}
              <span className="block mt-0.5">Editable later per zone.</span>
            </div>
            {mutation.isError && (
              <div className="p-2 bg-error-container/40 border border-error/40 rounded text-xs text-on-error-container" role="alert">
                {(mutation.error as Error).message}
              </div>
            )}
          </div>
        )}

        <div className="mt-4 pt-3 border-t border-outline-variant flex items-center justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1.5 border border-outline-variant rounded text-telemetry font-mono text-on-surface hover:bg-surface-container transition-colors">
            Cancel
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!geometry || !name || mutation.isPending}
            className="px-4 py-1.5 bg-primary text-white rounded text-telemetry font-mono hover:bg-primary-container transition-colors disabled:opacity-50"
          >
            {mutation.isPending ? 'Creating…' : 'Activate Monitoring Zone'}
          </button>
        </div>
      </div>
    </div>
  )
}
