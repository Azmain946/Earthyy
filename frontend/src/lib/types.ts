// Shared API types mirroring backend schemas.

export type ModuleKey = 'river' | 'agriculture' | 'forest' | 'brick_kiln'
export type ZoneType = ModuleKey | 'general'

export interface GeoJSONGeometry {
  type: string
  coordinates: unknown
}

export interface User {
  id: number
  email: string
  full_name: string
  role: string
}

export interface Zone {
  id: number
  name: string
  zone_type: ZoneType
  geometry: GeoJSONGeometry
  area_km2: number
  baseline_date: string | null
  latest_observation: string | null
  status: string
  thresholds: Record<string, number>
  alert_configuration: Record<string, unknown>
  description: string
  created_at: string
}

export interface MapLayer {
  key: string
  kind: 'geojson' | 'raster'
  title: string
  path?: string
  data?: GeoJSON.FeatureCollection
  bounds?: [number, number, number, number]
  style?: { color?: string; fill?: boolean; dash?: boolean; marker?: boolean }
}

export interface Analysis {
  id: number
  zone_id: number | null
  module: ModuleKey
  status: string
  baseline_at: string | null
  observed_at: string | null
  provenance: Record<string, SceneProvenance>
  measurements: Record<string, unknown>
  layers: MapLayer[]
  confidence_score: number | null
  confidence_level: string
  method: string
  processing_version: string
  limitations: string
  created_at: string
}

export interface SceneProvenance {
  provider: string
  scene_id: string
  collection: string
  sensor: string
  acquired_at: string
  cloud_cover: number | null
}

export interface Job {
  id: string
  zone_id: number | null
  module: ModuleKey
  job_type: string
  status: string
  stage: string
  stage_label: string
  progress: number
  error: string | null
  result_analysis_id: number | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface Detection {
  id: number
  analysis_id: number | null
  zone_id: number | null
  module: ModuleKey
  detection_type: string
  geometry: GeoJSONGeometry
  area_m2: number | null
  confidence: number | null
  status: string
  observed_at: string | null
  properties: Record<string, unknown>
}

export interface Alert {
  id: number
  zone_id: number | null
  analysis_id: number | null
  alert_type: string
  severity: 'info' | 'warning' | 'critical'
  title: string
  message: string
  location: GeoJSONGeometry | null
  measurement: Record<string, unknown>
  threshold: Record<string, unknown>
  status: 'unread' | 'acknowledged' | 'resolved'
  created_at: string
}

export interface Observation {
  id: number
  zone_id: number
  module: ModuleKey
  observed_at: string
  measurements: Record<string, unknown>
  preview_path: string | null
}

export interface Scene {
  id: number
  provider: string
  external_id: string
  collection: string
  sensor: string
  acquired_at: string
  cloud_cover: number | null
  geometry?: GeoJSONGeometry | null
}

export interface SearchResult {
  kind: 'monitoring_zone' | 'place'
  name: string
  lat: number
  lon: number
  zone_id?: number
  zone_type?: string
  category?: string
  bbox?: number[] | null
}

export interface OverviewData {
  zones: { total: number; by_type: Record<string, number>; monitored_km2: number }
  detections: { by_type: Record<string, number>; kiln_candidates: number }
  alerts: { unread: number }
  analyses: { total: number }
  jobs: { running: number }
  scenes: { cached: number; latest_acquisition: string | null }
  modules: Record<
    string,
    {
      analysis_id: number
      zone_id: number | null
      observed_at: string | null
      baseline_at: string | null
      measurements: Record<string, unknown>
      confidence_score: number | null
      confidence_level: string
      provenance: Record<string, SceneProvenance>
    }
  >
}

export interface ModelRegistryEntry {
  id: number
  model_name: string
  version: string
  module: string
  model_type: string
  source: string
  input_requirements: Record<string, unknown>
  output_type: string
  status: string
  metrics: Record<string, unknown>
  limitations: string
}
