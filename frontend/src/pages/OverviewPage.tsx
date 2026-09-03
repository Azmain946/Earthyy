import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import MapView from '../components/map/MapView'
import TopBar from '../components/layout/TopBar'
import AlertsDrawer from '../components/AlertsDrawer'
import ZoneModal from '../components/ZoneModal'
import { changeService, overviewService, zoneService } from '../services'
import { fmtAgo, fmtDate, fmtNum, MODULE_META } from '../lib/format'
import type { Detection, MapLayer, SearchResult } from '../lib/types'

const DET_COLORS: Record<string, string> = {
  erosion: '#ba1a1a',
  accretion: '#10b981',
  forest_loss: '#ba1a1a',
  forest_gain: '#10b981',
  vegetation_stress: '#c2410c',
  kiln_candidate: '#b53801',
}

const MODULE_ROUTE: Record<string, string> = {
  river: '/river',
  agriculture: '/agriculture',
  forest: '/forest',
  brick_kiln: '/brick-kilns',
}

export default function OverviewPage() {
  const navigate = useNavigate()
  const [alertsOpen, setAlertsOpen] = useState(false)
  const [zoneModalOpen, setZoneModalOpen] = useState(false)
  const [focusBounds, setFocusBounds] = useState<[number, number, number, number] | null>(null)

  const { data: overview } = useQuery({ queryKey: ['overview'], queryFn: overviewService.get, refetchInterval: 30000 })
  const { data: zones } = useQuery({ queryKey: ['zones'], queryFn: () => zoneService.list({ status: 'active' }) })
  const { data: changes } = useQuery({ queryKey: ['changes'], queryFn: () => changeService.recent({ limit: 200 }) })

  // Build overview map layers from real zone geometries + detections.
  const layers = useMemo<MapLayer[]>(() => {
    const out: MapLayer[] = []
    if (zones && zones.length) {
      out.push({
        key: 'zones',
        kind: 'geojson',
        title: 'Monitoring Zones',
        data: {
          type: 'FeatureCollection',
          features: zones.map((z) => ({
            type: 'Feature' as const,
            geometry: z.geometry as GeoJSON.Geometry,
            properties: { name: z.name, type: z.zone_type },
          })),
        },
        style: { color: '#94ccff', fill: false },
      })
    }
    if (changes && changes.length) {
      const byType = new Map<string, Detection[]>()
      for (const d of changes) {
        const list = byType.get(d.detection_type) ?? []
        list.push(d)
        byType.set(d.detection_type, list)
      }
      for (const [type, dets] of byType) {
        out.push({
          key: `det_${type}`,
          kind: 'geojson',
          title: `${type.replace(/_/g, ' ')} (${dets.length})`,
          data: {
            type: 'FeatureCollection',
            features: dets.map((d) => ({
              type: 'Feature' as const,
              geometry: d.geometry as GeoJSON.Geometry,
              properties: { area_m2: d.area_m2 },
            })),
          },
          style: {
            color: DET_COLORS[type] ?? '#0369a1',
            fill: type !== 'kiln_candidate',
            marker: type === 'kiln_candidate',
          },
        })
      }
    }
    return out
  }, [zones, changes])

  const visibleKeys = useMemo(() => Object.fromEntries(layers.map((l) => [l.key, true])), [layers])

  const onLocate = (r: SearchResult) => {
    if (r.bbox && r.bbox.length === 4) setFocusBounds([r.bbox[2], r.bbox[0], r.bbox[3], r.bbox[1]])
    else setFocusBounds([r.lon - 0.05, r.lat - 0.05, r.lon + 0.05, r.lat + 0.05])
  }

  const mods = overview?.modules ?? {}
  const riverM = mods.river?.measurements as Record<string, number> | undefined
  const agriM = mods.agriculture?.measurements as Record<string, number> | undefined
  const forestM = mods.forest?.measurements as Record<string, number> | undefined
  const kilnM = mods.brick_kiln?.measurements as Record<string, number> | undefined

  return (
    <>
      <TopBar
        onLocate={onLocate}
        onToggleAlerts={() => setAlertsOpen((v) => !v)}
        contextBadges={
          <>
            <span className="px-2 py-0.5 rounded bg-surface-container border border-outline-variant text-label-coord font-mono text-on-surface whitespace-nowrap">
              MONITORED: {fmtNum(overview?.zones.monitored_km2, 0)} km²
            </span>
            <span className="px-2 py-0.5 rounded bg-surface-container border border-outline-variant text-label-coord font-mono text-on-surface whitespace-nowrap">
              SCENES CACHED: {overview?.scenes.cached ?? '—'}
            </span>
            <span className="px-2 py-0.5 rounded bg-surface-container border border-outline-variant text-label-coord font-mono text-primary whitespace-nowrap">
              JOBS RUNNING: {overview?.jobs.running ?? 0}
            </span>
          </>
        }
        actions={
          <button
            onClick={() => setZoneModalOpen(true)}
            className="flex items-center gap-1.5 h-7 px-3 bg-primary text-white rounded text-telemetry font-mono hover:bg-primary-container transition-colors"
          >
            <span className="material-symbols-outlined text-[15px]" aria-hidden>add_location_alt</span>
            <span>New Zone</span>
          </button>
        }
      />

      <main className="fixed top-12 bottom-0 right-0 left-sidebar-width overflow-y-auto bg-surface">
        {/* Map section */}
        <section className="relative w-full h-[58vh] min-h-[420px] bg-inverse-surface border-b border-outline-variant">
          <MapView
            layers={layers}
            visibleKeys={visibleKeys}
            rasterOpacity={0.85}
            focusBounds={focusBounds}
            basemap="satellite"
            initialCenter={[89.9, 23.6]}
            initialZoom={7}
          />
          <div className="absolute top-3 left-3 z-10 bg-surface-container-lowest/95 backdrop-blur-sm border border-outline-variant rounded-lg shadow-sm px-3 py-2 pointer-events-none">
            <div className="text-telemetry font-mono font-semibold text-on-surface flex items-center gap-1.5">
              <span className="material-symbols-outlined text-sm text-primary" aria-hidden>public</span>
              Bangladesh Operational Theatre
            </div>
            <div className="text-label-coord font-mono text-outline mt-0.5">
              {overview?.zones.total ?? 0} active zones · {changes?.length ?? 0} stored detections
            </div>
          </div>
        </section>

        {/* Telemetry bento */}
        <section className="p-4 space-y-4 max-w-7xl mx-auto w-full">
          <div className="flex items-center justify-between border-b border-outline-variant pb-2">
            <div>
              <h2 className="text-lg font-semibold text-on-surface">Domain Intelligence & Terrestrial Telemetry</h2>
              <p className="text-xs text-on-surface-variant">
                Live measurements from the Earthyy analysis database — every value originates from a real satellite analysis run.
              </p>
            </div>
            <span className="text-label-coord font-mono text-outline whitespace-nowrap">
              LATEST ACQ: {overview?.scenes.latest_acquisition ? fmtDate(overview.scenes.latest_acquisition) : '—'}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
            {/* River card */}
            <ModuleCard
              title="RIVER DYNAMICS"
              color="text-primary"
              onClick={() => navigate('/river')}
              headline={riverM ? `${fmtNum(riverM.erosion_km2 + riverM.accretion_km2, 1)} km²` : '—'}
              headlineSub="channel change"
              confidence={mods.river?.confidence_score ?? null}
              rows={[
                ['Bank erosion', riverM ? `${fmtNum(riverM.erosion_km2, 2)} km²` : '—'],
                ['Sandbar accretion', riverM ? `${fmtNum(riverM.accretion_km2, 2)} km²` : '—'],
                ['Net terrestrial trend', riverM ? `${fmtNum(riverM.area_difference_km2, 2)} km²` : '—'],
              ]}
              footer={mods.river ? `Observed ${fmtDate(mods.river.observed_at)}` : 'No analysis yet'}
            />
            <ModuleCard
              title="CROP / AGRICULTURE"
              color="text-secondary"
              onClick={() => navigate('/agriculture')}
              headline={agriM ? `${fmtNum(agriM.cultivated_area_ha, 0)} ha` : '—'}
              headlineSub="vegetated area"
              confidence={mods.agriculture?.confidence_score ?? null}
              rows={[
                ['Condition score', agriM?.vegetation_condition_score != null ? `${agriM.vegetation_condition_score} / 100` : '—'],
                ['Mean NDVI', agriM ? fmtNum(agriM.mean_ndvi, 2) : '—'],
                ['Stress area', agriM ? `${fmtNum(agriM.stress_area_ha, 1)} ha` : '—'],
              ]}
              footer={mods.agriculture ? `Observed ${fmtDate(mods.agriculture.observed_at)}` : 'No analysis yet'}
            />
            <ModuleCard
              title="FOREST CANOPY"
              color="text-secondary"
              onClick={() => navigate('/forest')}
              headline={forestM ? `${fmtNum(forestM.forest_loss_ha, 1)} ha` : '—'}
              headlineSub="canopy loss"
              confidence={mods.forest?.confidence_score ?? null}
              rows={[
                ['Canopy area', forestM ? `${fmtNum(forestM.forest_area_current_ha, 0)} ha` : '—'],
                ['Gain / regrowth', forestM ? `${fmtNum(forestM.forest_gain_ha, 1)} ha` : '—'],
                ['Loss rate', forestM ? `${fmtNum(forestM.loss_rate_ha_per_year, 1)} ha/yr` : '—'],
              ]}
              footer={mods.forest ? `Observed ${fmtDate(mods.forest.observed_at)}` : 'No analysis yet'}
            />
            <ModuleCard
              title="BRICK KILN INVENTORY"
              color="text-tertiary"
              onClick={() => navigate('/brick-kilns')}
              headline={kilnM ? `${kilnM.candidate_count}` : '—'}
              headlineSub="candidate sites"
              confidence={mods.brick_kiln?.confidence_score ?? null}
              rows={[
                ['New candidates', kilnM != null ? `+${kilnM.new_candidate_count}` : '—'],
                ['Candidate footprint', kilnM ? `${fmtNum(kilnM.candidate_total_area_ha, 1)} ha` : '—'],
                ['Status', 'requires verification'],
              ]}
              footer={mods.brick_kiln ? `Observed ${fmtDate(mods.brick_kiln.observed_at)}` : 'No analysis yet'}
            />
          </div>

          {/* Recent changes + zones */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 pb-8">
            <div className="lg:col-span-2 bg-surface-container-lowest rounded-lg border border-outline-variant p-3">
              <div className="flex items-center justify-between pb-2 border-b border-outline-variant mb-2">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary text-lg" aria-hidden>notifications_active</span>
                  <h3 className="font-semibold text-on-surface text-sm">Recent Detected Physical Changes</h3>
                </div>
                <span className="text-label-coord font-mono text-outline">{changes?.length ?? 0} stored</span>
              </div>
              <div className="divide-y divide-outline-variant/60 max-h-96 overflow-y-auto">
                {(!changes || changes.length === 0) && (
                  <p className="py-6 text-center text-xs text-on-surface-variant">
                    No detections yet. Open a module and run a satellite analysis to populate the change record.
                  </p>
                )}
                {changes?.slice(0, 30).map((d) => (
                  <div key={d.id} className="py-2 flex items-center justify-between gap-3 hover:bg-surface-container-low px-2 rounded transition-colors">
                    <div className="flex items-start gap-2.5 min-w-0">
                      <span
                        className="w-7 h-7 rounded flex items-center justify-center mt-0.5 shrink-0"
                        style={{ background: `${DET_COLORS[d.detection_type] ?? '#0369a1'}22`, color: DET_COLORS[d.detection_type] ?? '#0369a1' }}
                        aria-hidden
                      >
                        <span className="material-symbols-outlined text-base">{MODULE_META[d.module]?.icon ?? 'radar'}</span>
                      </span>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-on-surface capitalize">{d.detection_type.replace(/_/g, ' ')}</span>
                          {d.confidence !== null && (
                            <span className="text-label-coord font-mono text-primary bg-primary-fixed/40 px-1 rounded text-[10px]">
                              {Math.round(d.confidence * 100)}% CONF
                            </span>
                          )}
                          <span className="text-label-coord font-mono text-outline text-[10px] uppercase">{d.status}</span>
                        </div>
                        <div className="text-label-coord font-mono text-outline mt-0.5">
                          {d.area_m2 ? `${fmtNum(d.area_m2 / 1e4, 2)} ha · ` : ''}
                          observed {fmtDate(d.observed_at)} · {fmtAgo(d.observed_at)}
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => navigate(MODULE_ROUTE[d.module] ?? '/')}
                      className="px-2 py-1 bg-surface-container border border-outline-variant rounded text-label-coord font-mono text-on-surface hover:bg-surface-container-high transition-colors shrink-0"
                    >
                      Open Module
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-surface-container-lowest rounded-lg border border-outline-variant p-3 flex flex-col">
              <div className="flex items-center justify-between pb-2 border-b border-outline-variant mb-2">
                <div className="flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-primary text-lg" aria-hidden>radar</span>
                  <h3 className="font-semibold text-on-surface text-sm">Active Monitoring Zones</h3>
                </div>
                <span className="text-label-coord font-mono text-outline">{zones?.length ?? 0} total</span>
              </div>
              <div className="space-y-2 overflow-y-auto flex-1">
                {zones?.map((z) => (
                  <button
                    key={z.id}
                    onClick={() => navigate(MODULE_ROUTE[z.zone_type] ?? '/')}
                    className="w-full text-left p-2.5 rounded border border-outline-variant bg-surface-container-low hover:border-primary transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-on-surface truncate">{z.name}</span>
                      <span className={`w-2 h-2 rounded-full shrink-0 ${z.latest_observation ? 'bg-secondary' : 'bg-outline-variant'}`} aria-hidden />
                    </div>
                    <div className="text-label-coord font-mono text-outline mt-1">
                      {fmtNum(z.area_km2, 0)} km² · {z.zone_type.replace('_', ' ')} ·{' '}
                      {z.latest_observation ? `observed ${fmtDate(z.latest_observation)}` : 'not yet observed'}
                    </div>
                    <div className="flex items-center justify-between mt-1.5 pt-1.5 border-t border-outline-variant text-[11px] text-on-surface-variant">
                      <span className="font-mono">
                        {Object.entries(z.thresholds).slice(0, 1).map(([k, v]) => `Threshold: ${k} > ${v}`)[0] ?? 'No thresholds'}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
              <button
                onClick={() => setZoneModalOpen(true)}
                className="w-full mt-3 flex items-center justify-center gap-1.5 py-2 bg-surface-container hover:bg-surface-container-high text-on-surface border border-outline-variant rounded text-telemetry font-mono transition-colors"
              >
                <span className="material-symbols-outlined text-base" aria-hidden>add_location_alt</span>
                Configure New Monitoring Zone
              </button>
            </div>
          </div>
        </section>

        <footer className="px-4 py-2 border-t border-outline-variant bg-surface-container-lowest flex flex-col sm:flex-row items-center justify-between text-label-coord font-mono text-outline">
          <span>Earthyy Observation Intelligence · Earth Search STAC · Planetary Computer · Copernicus Data Space</span>
          <span>WGS 84 · Sentinel-2 L2A surface reflectance</span>
        </footer>
      </main>

      <ZoneModal open={zoneModalOpen} onClose={() => setZoneModalOpen(false)} geometry={null} />
      <AlertsDrawer open={alertsOpen} onClose={() => setAlertsOpen(false)} />
    </>
  )
}

function ModuleCard({
  title,
  color,
  headline,
  headlineSub,
  rows,
  footer,
  confidence,
  onClick,
}: {
  title: string
  color: string
  headline: string
  headlineSub: string
  rows: Array<[string, string]>
  footer: string
  confidence: number | null
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="bg-surface-container-lowest p-3 rounded-lg border border-outline-variant flex flex-col justify-between hover:border-primary transition-colors text-left"
    >
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <span className={`text-label-badge font-semibold ${color} bg-surface-container-low px-2 py-0.5 rounded`}>{title}</span>
          <span className="text-label-coord font-mono text-outline">
            {confidence !== null ? `Conf: ${Math.round(confidence * 100)}%` : 'Conf: n/a'}
          </span>
        </div>
        <div>
          <span className="text-2xl font-bold text-on-surface">{headline}</span>
          <span className="text-xs text-outline ml-1.5">{headlineSub}</span>
        </div>
        <div className="mt-2.5 pt-2.5 border-t border-outline-variant space-y-1 text-label-coord font-mono">
          {rows.map(([k, v]) => (
            <div key={k} className="flex justify-between">
              <span className="text-outline">{k}:</span>
              <span className="text-on-surface font-medium">{v}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="mt-3 pt-2 border-t border-outline-variant text-label-coord font-mono text-outline">{footer}</div>
    </button>
  )
}
