import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import type { Map as MLMap, LngLatBoundsLike, MapMouseEvent } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import MapboxDraw from '@mapbox/mapbox-gl-draw'
import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css'
import bbox from '@turf/bbox'
import { fileUrl } from '../../lib/api'
import type { MapLayer, GeoJSONGeometry } from '../../lib/types'

// mapbox-gl-draw expects the mapbox-gl global class names; maplibre is compatible.
;(MapboxDraw.constants as { classes: Record<string, string> }).classes.CANVAS = 'maplibregl-canvas'
;(MapboxDraw.constants as { classes: Record<string, string> }).classes.CONTROL_BASE = 'maplibregl-ctrl'
;(MapboxDraw.constants as { classes: Record<string, string> }).classes.CONTROL_PREFIX = 'maplibregl-ctrl-'
;(MapboxDraw.constants as { classes: Record<string, string> }).classes.CONTROL_GROUP = 'maplibregl-ctrl-group'
;(MapboxDraw.constants as { classes: Record<string, string> }).classes.ATTRIBUTION = 'maplibregl-ctrl-attrib'

export const BASEMAPS = {
  satellite: {
    name: 'Satellite',
    tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
    attribution: 'Esri, Maxar, Earthstar Geographics',
  },
  streets: {
    name: 'Streets',
    tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
    attribution: '© OpenStreetMap contributors',
  },
}

function baseStyle(kind: keyof typeof BASEMAPS): maplibregl.StyleSpecification {
  const bm = BASEMAPS[kind]
  return {
    version: 8,
    sources: {
      basemap: { type: 'raster', tiles: bm.tiles, tileSize: 256, attribution: bm.attribution },
    },
    layers: [{ id: 'basemap', type: 'raster', source: 'basemap' }],
  }
}

export interface MapViewProps {
  layers: MapLayer[]
  visibleKeys: Record<string, boolean>
  rasterOpacity: number
  zoneGeometry?: GeoJSONGeometry | null
  focusBounds?: [number, number, number, number] | null
  basemap: keyof typeof BASEMAPS
  drawEnabled?: boolean
  onDrawn?: (geometry: GeoJSONGeometry | null) => void
  onMapReady?: (map: MLMap) => void
  initialCenter?: [number, number]
  initialZoom?: number
}

const LAYER_PREFIX = 'earthyy-'

export default function MapView({
  layers,
  visibleKeys,
  rasterOpacity,
  zoneGeometry,
  focusBounds,
  basemap,
  drawEnabled,
  onDrawn,
  onMapReady,
  initialCenter = [89.75, 23.76],
  initialZoom = 11,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MLMap | null>(null)
  const drawRef = useRef<MapboxDraw | null>(null)
  const [ready, setReady] = useState(false)
  const [cursor, setCursor] = useState<{ lng: number; lat: number } | null>(null)
  const onDrawnRef = useRef(onDrawn)
  onDrawnRef.current = onDrawn

  // Init map once
  useEffect(() => {
    if (!containerRef.current) return
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: baseStyle(basemap),
      center: initialCenter,
      zoom: initialZoom,
      attributionControl: { compact: true },
    })
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), 'bottom-right')
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: 'metric' }), 'bottom-right')
    map.addControl(new maplibregl.FullscreenControl(), 'bottom-right')
    map.on('mousemove', (e: MapMouseEvent) => setCursor({ lng: e.lngLat.lng, lat: e.lngLat.lat }))
    map.on('load', () => {
      setReady(true)
      onMapReady?.(map)
    })
    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
      setReady(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Basemap switch
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    const src = map.getSource('basemap') as maplibregl.RasterTileSource | undefined
    if (src) {
      src.setTiles(BASEMAPS[basemap].tiles)
    }
  }, [basemap, ready])

  // Draw control
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    if (drawEnabled && !drawRef.current) {
      const draw = new MapboxDraw({
        displayControlsDefault: false,
        controls: { polygon: true, trash: true },
      })
      map.addControl(draw as unknown as maplibregl.IControl, 'top-right')
      drawRef.current = draw
      const emit = () => {
        const fc = draw.getAll()
        const feat = fc.features[fc.features.length - 1]
        onDrawnRef.current?.(feat ? (feat.geometry as GeoJSONGeometry) : null)
      }
      const mapAny = map as unknown as { on: (ev: string, fn: () => void) => void }
      mapAny.on('draw.create', emit)
      mapAny.on('draw.update', emit)
      mapAny.on('draw.delete', () => onDrawnRef.current?.(null))
    } else if (!drawEnabled && drawRef.current) {
      map.removeControl(drawRef.current as unknown as maplibregl.IControl)
      drawRef.current = null
    }
  }, [drawEnabled, ready])

  // Zone boundary layer
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    const id = `${LAYER_PREFIX}zone`
    if (map.getLayer(id)) map.removeLayer(id)
    if (map.getSource(id)) map.removeSource(id)
    if (zoneGeometry) {
      map.addSource(id, {
        type: 'geojson',
        data: { type: 'Feature', geometry: zoneGeometry as GeoJSON.Geometry, properties: {} },
      })
      map.addLayer({
        id,
        type: 'line',
        source: id,
        paint: { 'line-color': '#f6faff', 'line-width': 2, 'line-dasharray': [3, 2] },
      })
    }
  }, [zoneGeometry, ready])

  // Analysis layers sync
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return

    // Remove stale earthyy layers (except zone)
    const style = map.getStyle()
    for (const lyr of style.layers ?? []) {
      if (lyr.id.startsWith(LAYER_PREFIX) && lyr.id !== `${LAYER_PREFIX}zone`) {
        map.removeLayer(lyr.id)
      }
    }
    for (const srcId of Object.keys(style.sources ?? {})) {
      if (srcId.startsWith(LAYER_PREFIX) && srcId !== `${LAYER_PREFIX}zone`) {
        map.removeSource(srcId)
      }
    }

    // Raster layers first (under vectors)
    for (const layer of layers) {
      if (!visibleKeys[layer.key]) continue
      const id = `${LAYER_PREFIX}${layer.key}`
      if (layer.kind === 'raster' && layer.path && layer.bounds) {
        const [w, s, e, n] = layer.bounds
        map.addSource(id, {
          type: 'image',
          url: fileUrl(layer.path),
          coordinates: [
            [w, n],
            [e, n],
            [e, s],
            [w, s],
          ],
        })
        map.addLayer({
          id,
          type: 'raster',
          source: id,
          paint: { 'raster-opacity': rasterOpacity, 'raster-resampling': 'nearest' },
        })
      }
    }
    for (const layer of layers) {
      if (!visibleKeys[layer.key]) continue
      const id = `${LAYER_PREFIX}${layer.key}`
      if (layer.kind === 'geojson' && layer.data) {
        map.addSource(id, { type: 'geojson', data: layer.data })
        const color = layer.style?.color ?? '#0369a1'
        if (layer.style?.marker) {
          map.addLayer({
            id,
            type: 'circle',
            source: id,
            paint: {
              'circle-radius': 6,
              'circle-color': color,
              'circle-stroke-color': '#ffffff',
              'circle-stroke-width': 1.5,
              'circle-opacity': 0.9,
            },
          })
        } else {
          if (layer.style?.fill) {
            map.addLayer({
              id: `${id}-fill`,
              type: 'fill',
              source: id,
              paint: { 'fill-color': color, 'fill-opacity': 0.32 },
            })
          }
          map.addLayer({
            id,
            type: 'line',
            source: id,
            paint: {
              'line-color': color,
              'line-width': layer.style?.fill ? 1.5 : 2.2,
              ...(layer.style?.dash ? { 'line-dasharray': [4, 3] } : {}),
            },
          })
        }
      }
    }
  }, [layers, visibleKeys, rasterOpacity, ready])

  // Focus bounds
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    if (focusBounds) {
      map.fitBounds(focusBounds as LngLatBoundsLike, { padding: 60, duration: 800, maxZoom: 15 })
    } else if (zoneGeometry) {
      try {
        const b = bbox({ type: 'Feature', geometry: zoneGeometry as GeoJSON.Geometry, properties: {} })
        map.fitBounds(b as LngLatBoundsLike, { padding: 60, duration: 800, maxZoom: 14 })
      } catch {
        /* ignore */
      }
    }
  }, [focusBounds, zoneGeometry, ready])

  return (
    <div className="relative w-full h-full" data-purpose="map-viewport">
      <div ref={containerRef} className="absolute inset-0" />
      {/* Coordinate + CRS readout */}
      <div className="absolute bottom-2 left-2 z-10 flex items-center gap-2 bg-surface-container-lowest/95 backdrop-blur-sm border border-outline-variant rounded px-2.5 py-1 text-label-coord font-mono text-on-surface-variant shadow-sm pointer-events-none">
        <span className="font-bold text-on-surface">N</span>
        <span className="material-symbols-outlined text-sm text-primary">navigation</span>
        <span className="border-l border-outline-variant pl-2">
          {cursor ? `${cursor.lat.toFixed(4)}°N ${cursor.lng.toFixed(4)}°E` : '—'}
        </span>
        <span className="border-l border-outline-variant pl-2">EPSG:4326 → 3857</span>
      </div>
    </div>
  )
}
