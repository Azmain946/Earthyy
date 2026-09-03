// Frontend data-access layer: typed service functions per API domain.
import { api } from '../lib/api'
import type {
  Alert,
  Analysis,
  Detection,
  Job,
  ModelRegistryEntry,
  ModuleKey,
  Observation,
  OverviewData,
  Scene,
  SearchResult,
  User,
  Zone,
  GeoJSONGeometry,
} from '../lib/types'

// ---- auth ----
export const authService = {
  login: (email: string, password: string) =>
    api.post<{ access_token: string }>('/auth/login', { email, password }),
  me: () => api.get<User>('/auth/me'),
}

// ---- overview ----
export const overviewService = {
  get: () => api.get<OverviewData>('/overview'),
  health: () => api.get<{ status: string; components: Record<string, string> }>('/health'),
}

// ---- monitoring zones ----
export const zoneService = {
  list: (params?: { zone_type?: string; status?: string }) => {
    const q = new URLSearchParams()
    if (params?.zone_type) q.set('zone_type', params.zone_type)
    if (params?.status) q.set('status', params.status)
    const qs = q.toString()
    return api.get<Zone[]>(`/monitoring-zones${qs ? `?${qs}` : ''}`)
  },
  get: (id: number) => api.get<Zone>(`/monitoring-zones/${id}`),
  create: (body: {
    name: string
    zone_type: string
    geometry: GeoJSONGeometry
    baseline_date?: string
    thresholds?: Record<string, number>
    description?: string
  }) => api.post<Zone>('/monitoring-zones', body),
  update: (id: number, body: Partial<Pick<Zone, 'name' | 'status' | 'thresholds' | 'description'>>) =>
    api.patch<Zone>(`/monitoring-zones/${id}`, body),
  archive: (id: number) => api.del<void>(`/monitoring-zones/${id}`),
  observations: (id: number, module?: string) =>
    api.get<Observation[]>(`/monitoring-zones/${id}/observations${module ? `?module=${module}` : ''}`),
}

// ---- analysis / jobs ----
export const analysisService = {
  request: (body: {
    module: ModuleKey
    zone_id?: number
    geometry?: GeoJSONGeometry
    baseline_date: string
    current_date: string
    provider?: string
    max_cloud_cover?: number
  }) => api.post<Job>('/analysis', body),
  get: (id: number) => api.get<Analysis>(`/analysis/${id}`),
  list: (params?: { zone_id?: number; module?: string; limit?: number }) => {
    const q = new URLSearchParams()
    if (params?.zone_id != null) q.set('zone_id', String(params.zone_id))
    if (params?.module) q.set('module', params.module)
    if (params?.limit) q.set('limit', String(params.limit))
    const qs = q.toString()
    return api.get<Analysis[]>(`/analysis${qs ? `?${qs}` : ''}`)
  },
  detections: (id: number) => api.get<Detection[]>(`/analysis/${id}/detections`),
}

export const jobService = {
  get: (id: string) => api.get<Job>(`/jobs/${id}`),
  list: (status?: string) => api.get<Job[]>(`/jobs${status ? `?status=${status}` : ''}`),
}

// ---- changes / alerts ----
export const changeService = {
  recent: (params?: { module?: string; limit?: number }) => {
    const q = new URLSearchParams()
    if (params?.module) q.set('module', params.module)
    if (params?.limit) q.set('limit', String(params.limit))
    const qs = q.toString()
    return api.get<Detection[]>(`/changes${qs ? `?${qs}` : ''}`)
  },
}

export const alertService = {
  list: (status?: string) => api.get<Alert[]>(`/alerts${status ? `?status=${status}` : ''}`),
  acknowledge: (id: number) => api.post<Alert>(`/alerts/${id}/acknowledge`),
  resolve: (id: number) => api.post<Alert>(`/alerts/${id}/resolve`),
}

// ---- satellite scenes ----
export const sceneService = {
  search: (params: {
    bbox: [number, number, number, number]
    start: string
    end: string
    provider?: string
    max_cloud_cover?: number
  }) => {
    const q = new URLSearchParams({
      bbox: params.bbox.join(','),
      start: params.start,
      end: params.end,
    })
    if (params.provider) q.set('provider', params.provider)
    if (params.max_cloud_cover != null) q.set('max_cloud_cover', String(params.max_cloud_cover))
    return api.get<Scene[]>(`/satellite/scenes?${q}`)
  },
}

// ---- search ----
export const searchService = {
  query: (q: string) => api.get<{ query: string; results: SearchResult[] }>(`/search?q=${encodeURIComponent(q)}`),
}

// ---- reports ----
export const reportService = {
  create: (analysisId: number, format: 'pdf' | 'csv' | 'geojson') =>
    api.post<{ id: number; format: string; download_url: string }>(
      `/reports?analysis_id=${analysisId}&format=${format}`,
    ),
  list: () => api.get<Array<{ id: number; title: string; format: string; download_url: string; created_at: string }>>('/reports'),
}

// ---- model registry ----
export const registryService = {
  list: () => api.get<ModelRegistryEntry[]>('/models'),
}
