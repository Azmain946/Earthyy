import { useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import MapView from '../components/map/MapView'
import CompareMap from '../components/map/CompareMap'
import LayerPanel from '../components/map/LayerPanel'
import TopBar from '../components/layout/TopBar'
import JobProgress from '../components/JobProgress'
import ConfidenceBadge from '../components/ConfidenceBadge'
import EarthTime from '../components/EarthTime'
import MetricCard from '../components/MetricCard'
import ZoneModal from '../components/ZoneModal'
import AlertsDrawer from '../components/AlertsDrawer'
import { useJob } from '../hooks/useJob'
import { analysisService, reportService, zoneService } from '../services'
import { fmtDate, fmtNum, MODULE_META } from '../lib/format'
import type { Analysis, GeoJSONGeometry, ModuleKey, SearchResult, Zone } from '../lib/types'

// ---- module-specific metric card configuration ----
type CardDef = { label: string; key: string; unit?: string; digits?: number; tone?: 'default' | 'error' | 'secondary' | 'tertiary'; sub?: string }

const MODULE_CARDS: Record<ModuleKey, CardDef[]> = {
  river: [
    { label: 'Current Channel Area', key: 'river_area_current_km2', unit: 'km²', digits: 2 },
    { label: 'Net Surface Balance', key: 'area_difference_km2', unit: 'km²', digits: 2, tone: 'error' },
    { label: 'Bank Erosion', key: 'erosion_km2', unit: 'km²', digits: 2, tone: 'error', sub: 'land → water' },
    { label: 'Accretion / Char', key: 'accretion_km2', unit: 'km²', digits: 2, tone: 'secondary', sub: 'water → land' },
    { label: 'Mean Bank Movement', key: 'mean_bank_movement_m', unit: 'm', digits: 0 },
    { label: 'Movement Rate', key: 'movement_rate_m_per_year', unit: 'm/yr', digits: 0, tone: 'tertiary' },
  ],
  agriculture: [
    { label: 'Cultivated Area', key: 'cultivated_area_ha', unit: 'ha', digits: 0 },
    { label: 'Mean NDVI', key: 'mean_ndvi', digits: 2 },
    { label: 'NDVI vs Baseline', key: 'ndvi_change_pct', unit: '%', digits: 1, tone: 'tertiary' },
    { label: 'Condition Score', key: 'vegetation_condition_score', unit: '/100', digits: 0, tone: 'secondary' },
    { label: 'Stress Area', key: 'stress_area_ha', unit: 'ha', digits: 1, tone: 'error' },
    { label: 'Moisture (NDMI)', key: 'mean_ndmi', digits: 2 },
  ],
  forest: [
    { label: 'Canopy Area', key: 'forest_area_current_ha', unit: 'ha', digits: 0 },
    { label: 'Net Change', key: 'net_change_ha', unit: 'ha', digits: 1, tone: 'error' },
    { label: 'Canopy Loss', key: 'forest_loss_ha', unit: 'ha', digits: 1, tone: 'error' },
    { label: 'Canopy Gain', key: 'forest_gain_ha', unit: 'ha', digits: 1, tone: 'secondary' },
    { label: 'Loss Rate', key: 'loss_rate_ha_per_year', unit: 'ha/yr', digits: 1, tone: 'tertiary' },
    { label: 'Mean NDVI', key: 'mean_ndvi', digits: 2 },
  ],
  brick_kiln: [
    { label: 'Candidate Sites', key: 'candidate_count', digits: 0, tone: 'tertiary' },
    { label: 'New Candidates', key: 'new_candidate_count', digits: 0, tone: 'error', sub: 'vs baseline' },
    { label: 'Baseline Candidates', key: 'baseline_candidate_count', digits: 0 },
    { label: 'Candidate Footprint', key: 'candidate_total_area_ha', unit: 'ha', digits: 1 },
  ],
}

const MODULE_DEFAULT_DATES: Record<ModuleKey, { baseline: string; current: string }> = {
  river: { baseline: '2020-01-15', current: '2025-01-15' },
  agriculture: { baseline: '2023-02-15', current: '2025-02-15' },
  forest: { baseline: '2021-02-15', current: '2025-02-15' },
  brick_kiln: { baseline: '2021-12-15', current: '2024-12-15' },
}

export default function ModulePage({ module }: { module: ModuleKey }) {
  const meta = MODULE_META[module]
  const qc = useQueryClient()

  const [selectedZoneId, setSelectedZoneId] = useState<number | null>(null)
  const [drawMode, setDrawMode] = useState(false)
  const [drawnGeometry, setDrawnGeometry] = useState<GeoJSONGeometry | null>(null)
  const [baselineDate, setBaselineDate] = useState(MODULE_DEFAULT_DATES[module].baseline)
  const [currentDate, setCurrentDate] = useState(MODULE_DEFAULT_DATES[module].current)
  const [maxCloud, setMaxCloud] = useState(20)
  const [jobId, setJobId] = useState<string | null>(null)
  const [analysisId, setAnalysisId] = useState<number | null>(null)
  const [visibleKeys, setVisibleKeys] = useState<Record<string, boolean>>({})
  const [rasterOpacity, setRasterOpacity] = useState(0.85)
  const [basemap, setBasemap] = useState<'satellite' | 'streets'>('satellite')
  const [compareMode, setCompareMode] = useState(false)
  const [focusBounds, setFocusBounds] = useState<[number, number, number, number] | null>(null)
  const [zoneModalOpen, setZoneModalOpen] = useState(false)
  const [alertsOpen, setAlertsOpen] = useState(false)
  const [requestError, setRequestError] = useState<string | null>(null)
  const [selectedObsId, setSelectedObsId] = useState<number | null>(null)

  const { data: zones } = useQuery({
    queryKey: ['zones', module],
    queryFn: () => zoneService.list({ zone_type: module, status: 'active' }),
  })

  // Auto-select first zone of this module
  useEffect(() => {
    if (!selectedZoneId && zones && zones.length > 0) setSelectedZoneId(zones[0].id)
  }, [zones, selectedZoneId])

  const selectedZone: Zone | undefined = zones?.find((z) => z.id === selectedZoneId)

  // Latest stored analysis for the zone
  const { data: analyses } = useQuery({
    queryKey: ['analyses', module, selectedZoneId],
    queryFn: () => analysisService.list({ module, zone_id: selectedZoneId ?? undefined, limit: 5 }),
    enabled: selectedZoneId != null,
  })
  useEffect(() => {
    if (analysisId == null && analyses && analyses.length > 0) setAnalysisId(analyses[0].id)
  }, [analyses, analysisId])

  const { data: job } = useJob(jobId)
  useEffect(() => {
    if (job?.status === 'completed' && job.result_analysis_id) {
      setAnalysisId(job.result_analysis_id)
      qc.invalidateQueries({ queryKey: ['analyses'] })
      qc.invalidateQueries({ queryKey: ['alerts'] })
      qc.invalidateQueries({ queryKey: ['observations'] })
    }
  }, [job?.status, job?.result_analysis_id, qc])

  const { data: analysis } = useQuery<Analysis>({
    queryKey: ['analysis', analysisId],
    queryFn: () => analysisService.get(analysisId!),
    enabled: analysisId != null,
  })

  const { data: observations } = useQuery({
    queryKey: ['observations', selectedZoneId, module],
    queryFn: () => zoneService.observations(selectedZoneId!, module),
    enabled: selectedZoneId != null,
  })

  // Initialize layer visibility when a new analysis arrives
  useEffect(() => {
    if (!analysis) return
    const vis: Record<string, boolean> = {}
    for (const l of analysis.layers) {
      vis[l.key] = !l.key.startsWith('rgb_') || l.key === 'rgb_current' ? true : false
      if (l.key === 'rgb_baseline') vis[l.key] = false
      if (l.key === 'mndwi' || l.key === 'bsi') vis[l.key] = false
    }
    setVisibleKeys(vis)
  }, [analysis?.id])

  const runAnalysis = async () => {
    setRequestError(null)
    try {
      const j = await analysisService.request({
        module,
        zone_id: drawMode ? undefined : selectedZoneId ?? undefined,
        geometry: drawMode ? drawnGeometry ?? undefined : undefined,
        baseline_date: baselineDate,
        current_date: currentDate,
        max_cloud_cover: maxCloud,
      })
      setJobId(j.id)
    } catch (e) {
      setRequestError((e as Error).message)
    }
  }

  const exportReport = async (format: 'pdf' | 'csv' | 'geojson') => {
    if (!analysisId) return
    const r = await reportService.create(analysisId, format)
    window.open(r.download_url, '_blank')
  }

  const onLocate = (r: SearchResult) => {
    if (r.bbox && r.bbox.length === 4) {
      // Nominatim bbox: [south, north, west, east]
      setFocusBounds([r.bbox[2], r.bbox[0], r.bbox[3], r.bbox[1]])
    } else {
      setFocusBounds([r.lon - 0.05, r.lat - 0.05, r.lon + 0.05, r.lat + 0.05])
    }
    if (r.kind === 'monitoring_zone' && r.zone_id) setSelectedZoneId(r.zone_id)
  }

  const compareLayers = useMemo(() => {
    if (!analysis) return null
    const before = analysis.layers.find((l) => l.key === 'rgb_baseline' && l.path && l.bounds)
    const after = analysis.layers.find((l) => l.key === 'rgb_current' && l.path && l.bounds)
    return before && after ? { before, after } : null
  }, [analysis])

  const running = job && job.status !== 'completed' && job.status !== 'failed'
  const m = (analysis?.measurements ?? {}) as Record<string, number | null>

  const aoiForModal: GeoJSONGeometry | null = drawnGeometry ?? (selectedZone?.geometry as GeoJSONGeometry) ?? null

  return (
    <>
      <TopBar
        onLocate={onLocate}
        onToggleAlerts={() => setAlertsOpen((v) => !v)}
        contextBadges={
          <>
            <span className="px-2 py-0.5 rounded bg-surface-container border border-outline-variant text-label-coord font-mono text-on-surface flex items-center gap-1.5 whitespace-nowrap">
              <span className="w-1.5 h-1.5 rounded-full bg-secondary" aria-hidden></span>
              {analysis ? `${analysis.provenance.current?.sensor ?? 'Sentinel-2'} • 10m L2A` : 'Sentinel-2 MSI • 10m L2A'}
            </span>
            {analysis?.observed_at && (
              <span className="px-2 py-0.5 rounded bg-surface-container border border-outline-variant text-label-coord font-mono text-on-surface whitespace-nowrap">
                ACQ: {fmtDate(analysis.observed_at)}
              </span>
            )}
            {analysis?.provenance.current?.cloud_cover != null && (
              <span className="px-2 py-0.5 rounded bg-surface-container border border-outline-variant text-label-coord font-mono text-on-surface whitespace-nowrap">
                Cloud: {fmtNum(analysis.provenance.current.cloud_cover, 1)}%
              </span>
            )}
          </>
        }
        actions={
          <>
            <button
              onClick={() => setBasemap((b) => (b === 'satellite' ? 'streets' : 'satellite'))}
              className="hidden sm:flex items-center gap-1.5 h-7 px-2.5 bg-surface-container-lowest border border-outline-variant rounded text-telemetry font-mono text-on-surface hover:bg-surface-container transition-colors"
            >
              <span className="material-symbols-outlined text-base text-primary" aria-hidden>map</span>
              <span>{basemap === 'satellite' ? 'Satellite' : 'Streets'}</span>
            </button>
            <button
              onClick={() => setCompareMode((v) => !v)}
              disabled={!compareLayers}
              className={`hidden sm:flex items-center gap-1.5 h-7 px-2.5 border border-outline-variant rounded text-telemetry font-mono transition-colors disabled:opacity-40 ${
                compareMode ? 'bg-primary text-white' : 'bg-surface-container-lowest text-on-surface hover:bg-surface-container'
              }`}
              title={compareLayers ? 'Before / after comparison' : 'Run an analysis to enable comparison'}
            >
              <span className="material-symbols-outlined text-base" aria-hidden>splitscreen</span>
              <span>Split Compare</span>
            </button>
            <button
              onClick={() => exportReport('pdf')}
              disabled={!analysisId}
              className="flex items-center gap-1.5 h-7 px-3 bg-primary text-white rounded text-telemetry font-mono hover:bg-primary-container active:scale-95 transition-all disabled:opacity-40"
            >
              <span className="material-symbols-outlined text-[15px]" aria-hidden>file_download</span>
              <span>Export Report</span>
            </button>
          </>
        }
      />

      {/* Map viewport */}
      <main className="fixed top-12 bottom-7 left-sidebar-width right-inspector-width bg-inverse-surface" data-purpose="module-map">
        {compareMode && compareLayers ? (
          <CompareMap
            beforeLayer={compareLayers.before}
            afterLayer={compareLayers.after}
            beforeLabel={`${fmtDate(analysis?.baseline_at)} · ${analysis?.provenance.baseline?.scene_id ?? ''}`}
            afterLabel={`${fmtDate(analysis?.observed_at)} · ${analysis?.provenance.current?.scene_id ?? ''}`}
            bounds={compareLayers.after.bounds as [number, number, number, number]}
          />
        ) : (
          <>
            <MapView
              layers={analysis?.layers ?? []}
              visibleKeys={visibleKeys}
              rasterOpacity={rasterOpacity}
              zoneGeometry={drawMode ? null : (selectedZone?.geometry as GeoJSONGeometry | undefined)}
              focusBounds={focusBounds}
              basemap={basemap}
              drawEnabled={drawMode}
              onDrawn={setDrawnGeometry}
            />
            <LayerPanel
              layers={analysis?.layers ?? []}
              visibleKeys={visibleKeys}
              onToggle={(key) => setVisibleKeys((v) => ({ ...v, [key]: !v[key] }))}
              rasterOpacity={rasterOpacity}
              onOpacity={setRasterOpacity}
            />
            {drawMode && (
              <div className="absolute top-3 right-3 z-20 bg-inverse-surface/90 text-inverse-on-surface px-3 py-1.5 rounded-lg border border-outline/50 text-xs font-mono shadow-lg pointer-events-none">
                Draw a polygon with the tool (top-right), then Analyze or save it as a zone.
              </div>
            )}
          </>
        )}
      </main>

      {/* Right inspector */}
      <aside className="fixed top-12 right-0 bottom-7 z-20 w-inspector-width bg-surface-container-lowest border-l border-outline-variant flex flex-col overflow-hidden" aria-label={`${meta.label} inspector`}>
        <div className="p-3 border-b border-outline-variant bg-surface-container-low">
          <div className="flex items-center justify-between mb-1">
            <span className="text-label-badge font-semibold text-primary bg-primary-fixed px-1.5 py-0.5 rounded font-mono uppercase">
              {meta.label}
            </span>
            {analysis && (
              <span className="text-label-coord font-mono text-outline">ANALYSIS #{analysis.id}</span>
            )}
          </div>

          {/* Area selection */}
          <div className="flex items-center gap-1.5 mt-1.5">
            <select
              value={drawMode ? 'draw' : selectedZoneId ?? ''}
              onChange={(e) => {
                if (e.target.value === 'draw') {
                  setDrawMode(true)
                } else {
                  setDrawMode(false)
                  setSelectedZoneId(Number(e.target.value))
                  setAnalysisId(null)
                }
              }}
              className="flex-1 h-8 px-2 bg-surface-container-lowest border border-outline-variant rounded text-xs focus:outline-none focus:border-primary focus:ring-0"
              aria-label="Monitoring zone"
            >
              {zones?.map((z) => (
                <option key={z.id} value={z.id}>
                  {z.name} ({z.area_km2.toFixed(0)} km²)
                </option>
              ))}
              <option value="draw">✏️ Draw new area…</option>
            </select>
          </div>

          {/* Date window + cloud */}
          <div className="grid grid-cols-2 gap-1.5 mt-2">
            <label className="flex flex-col gap-0.5">
              <span className="text-label-coord font-mono text-outline uppercase">Baseline</span>
              <input type="date" value={baselineDate} onChange={(e) => setBaselineDate(e.target.value)}
                className="h-7 px-1.5 bg-surface-container-lowest border border-outline-variant rounded text-[11px] font-mono focus:outline-none focus:border-primary focus:ring-0" />
            </label>
            <label className="flex flex-col gap-0.5">
              <span className="text-label-coord font-mono text-outline uppercase">Current</span>
              <input type="date" value={currentDate} onChange={(e) => setCurrentDate(e.target.value)}
                className="h-7 px-1.5 bg-surface-container-lowest border border-outline-variant rounded text-[11px] font-mono focus:outline-none focus:border-primary focus:ring-0" />
            </label>
          </div>
          <label className="flex items-center gap-2 mt-2">
            <span className="text-label-coord font-mono text-outline whitespace-nowrap uppercase">Max cloud</span>
            <input type="range" min={5} max={90} value={maxCloud} onChange={(e) => setMaxCloud(Number(e.target.value))}
              className="w-full h-1 bg-outline-variant rounded appearance-none accent-primary cursor-pointer" />
            <span className="text-label-coord font-mono text-on-surface w-9 text-right">{maxCloud}%</span>
          </label>

          <button
            onClick={runAnalysis}
            disabled={!!running || (drawMode ? !drawnGeometry : !selectedZoneId)}
            className="w-full mt-2.5 py-2 bg-primary-container hover:bg-primary text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5 shadow-sm"
          >
            <span className="material-symbols-outlined text-base" aria-hidden>satellite_alt</span>
            {running ? 'Analyzing…' : 'Run Satellite Analysis'}
          </button>
          {requestError && (
            <div className="mt-2 p-2 bg-error-container/40 border border-error/40 rounded text-xs text-on-error-container" role="alert">
              {requestError}
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          {job && (job.status !== 'completed' || !analysis) && <JobProgress job={job} />}

          {analysis && (
            <>
              <div className="flex items-center justify-between">
                <span className="text-label-badge font-semibold text-outline uppercase tracking-wider">Measured Quantities</span>
                <ConfidenceBadge score={analysis.confidence_score} level={analysis.confidence_level} />
              </div>
              <div className="grid grid-cols-2 gap-2">
                {MODULE_CARDS[module].map((c) => (
                  <MetricCard
                    key={c.key}
                    label={c.label}
                    value={`${fmtNum(m[c.key], c.digits ?? 2)}${c.unit ? ` ${c.unit}` : ''}`}
                    sub={c.sub}
                    tone={c.tone}
                  />
                ))}
              </div>

              <div className="p-2.5 bg-surface-container-low border border-outline-variant rounded-lg text-label-coord font-mono text-on-surface-variant space-y-1">
                <div className="text-label-badge font-sans font-semibold text-outline uppercase tracking-wider">Data Provenance</div>
                {Object.entries(analysis.provenance).map(([role, p]) => (
                  <div key={role} className="flex flex-col">
                    <span className="text-on-surface">{role}: {p.scene_id}</span>
                    <span>{p.provider} · {p.collection} · {fmtDate(p.acquired_at)} · cloud {fmtNum(p.cloud_cover, 1)}%</span>
                  </div>
                ))}
                <div className="pt-1 border-t border-outline-variant/60">
                  method: {analysis.method}
                  <br />processing v{analysis.processing_version}
                </div>
              </div>

              {analysis.limitations && (
                <div className="p-2.5 bg-tertiary-fixed/40 border border-tertiary/20 rounded-lg">
                  <div className="text-label-badge font-semibold text-tertiary uppercase tracking-wider mb-0.5">Limitations</div>
                  <p className="text-xs text-on-surface-variant leading-relaxed">{analysis.limitations}</p>
                </div>
              )}
            </>
          )}

          {/* Earth Time */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-label-badge font-semibold text-outline uppercase tracking-wider">
                Earth Time — Historical Record
              </span>
              <span className="text-label-coord font-mono text-primary">{observations?.length ?? 0} obs</span>
            </div>
            <EarthTime
              observations={observations ?? []}
              selectedId={selectedObsId}
              onSelect={(o) => setSelectedObsId(o.id)}
            />
          </div>
        </div>

        {/* Actions */}
        <div className="p-3 border-t border-outline-variant bg-surface-container-low space-y-1.5">
          <div className="grid grid-cols-3 gap-1.5">
            {(['pdf', 'csv', 'geojson'] as const).map((f) => (
              <button
                key={f}
                onClick={() => exportReport(f)}
                disabled={!analysisId}
                className="py-1.5 px-2 bg-surface-container border border-outline-variant hover:bg-surface-container-high text-on-surface text-label-coord font-mono uppercase rounded transition-colors disabled:opacity-40"
              >
                {f}
              </button>
            ))}
          </div>
          <button
            onClick={() => setZoneModalOpen(true)}
            className="w-full py-1.5 px-2 bg-surface-container border border-outline-variant hover:bg-surface-container-high text-on-surface text-xs font-medium rounded transition-colors flex items-center justify-center gap-1"
          >
            <span className="material-symbols-outlined text-sm" aria-hidden>bookmark_add</span>
            Save AOI as Monitoring Zone
          </button>
        </div>
      </aside>

      {/* Bottom telemetry bar */}
      <footer className="fixed bottom-0 left-sidebar-width right-0 h-7 z-20 bg-surface-container-high border-t border-outline-variant flex items-center justify-between px-3 text-label-coord font-mono text-on-surface-variant">
        <div className="flex items-center gap-4 overflow-hidden">
          <span className="flex items-center gap-1.5 whitespace-nowrap">
            <span className="w-2 h-2 rounded-full bg-primary" aria-hidden></span>
            ZONE: <strong className="text-on-surface">{drawMode ? 'custom AOI' : selectedZone?.name ?? '—'}</strong>
          </span>
          {selectedZone && (
            <span className="whitespace-nowrap">AREA: <strong className="text-on-surface">{fmtNum(selectedZone.area_km2, 1)} km²</strong></span>
          )}
          {analysis?.baseline_at && (
            <span className="whitespace-nowrap hidden md:inline">
              WINDOW: {fmtDate(analysis.baseline_at)} → {fmtDate(analysis.observed_at)}
            </span>
          )}
        </div>
        <span className="flex items-center gap-1 whitespace-nowrap">
          <span className="material-symbols-outlined text-[13px] text-secondary" aria-hidden>satellite_alt</span>
          {analysis
            ? `${analysis.provenance.current?.provider ?? ''} · scene ${analysis.provenance.current?.scene_id?.slice(0, 24) ?? ''}`
            : 'No analysis yet — run satellite analysis'}
        </span>
      </footer>

      <ZoneModal
        open={zoneModalOpen}
        onClose={() => setZoneModalOpen(false)}
        geometry={aoiForModal}
        defaultType={module}
        onCreated={(id) => {
          setDrawMode(false)
          setSelectedZoneId(id)
        }}
      />
      <AlertsDrawer open={alertsOpen} onClose={() => setAlertsOpen(false)} />
    </>
  )
}
