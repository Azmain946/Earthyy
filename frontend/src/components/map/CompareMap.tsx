import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import type { Map as MLMap, LngLatBoundsLike } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { fileUrl } from '../../lib/api'
import { BASEMAPS } from './MapView'
import type { MapLayer } from '../../lib/types'

interface CompareMapProps {
  beforeLayer: MapLayer
  afterLayer: MapLayer
  beforeLabel: string
  afterLabel: string
  bounds: [number, number, number, number]
}

function makeMap(container: HTMLDivElement, layer: MapLayer, bounds: [number, number, number, number]) {
  const bm = BASEMAPS.satellite
  const [w, s, e, n] = layer.bounds!
  const map = new maplibregl.Map({
    container,
    style: {
      version: 8,
      sources: {
        basemap: { type: 'raster', tiles: bm.tiles, tileSize: 256, attribution: bm.attribution },
        overlay: {
          type: 'image',
          url: fileUrl(layer.path!),
          coordinates: [
            [w, n],
            [e, n],
            [e, s],
            [w, s],
          ],
        },
      },
      layers: [
        { id: 'basemap', type: 'raster', source: 'basemap' },
        { id: 'overlay', type: 'raster', source: 'overlay', paint: { 'raster-opacity': 1 } },
      ],
    },
    bounds: bounds as LngLatBoundsLike,
    fitBoundsOptions: { padding: 30 },
    attributionControl: false,
  })
  return map
}

/** Before/after split comparison with a draggable divider and synced maps. */
export default function CompareMap({ beforeLayer, afterLayer, beforeLabel, afterLabel, bounds }: CompareMapProps) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const beforeRef = useRef<HTMLDivElement>(null)
  const afterRef = useRef<HTMLDivElement>(null)
  const [split, setSplit] = useState(50)
  const dragging = useRef(false)

  useEffect(() => {
    if (!beforeRef.current || !afterRef.current) return
    const before = makeMap(beforeRef.current, beforeLayer, bounds)
    const after = makeMap(afterRef.current, afterLayer, bounds)

    let syncing = false
    const sync = (src: MLMap, dst: MLMap) => () => {
      if (syncing) return
      syncing = true
      dst.jumpTo({ center: src.getCenter(), zoom: src.getZoom(), bearing: src.getBearing(), pitch: src.getPitch() })
      syncing = false
    }
    before.on('move', sync(before, after))
    after.on('move', sync(after, before))

    return () => {
      before.remove()
      after.remove()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [beforeLayer.path, afterLayer.path])

  useEffect(() => {
    const onMove = (clientX: number) => {
      if (!dragging.current || !wrapRef.current) return
      const rect = wrapRef.current.getBoundingClientRect()
      const pct = Math.max(5, Math.min(95, ((clientX - rect.left) / rect.width) * 100))
      setSplit(pct)
    }
    const mm = (e: MouseEvent) => onMove(e.clientX)
    const tm = (e: TouchEvent) => e.touches[0] && onMove(e.touches[0].clientX)
    const up = () => (dragging.current = false)
    window.addEventListener('mousemove', mm)
    window.addEventListener('touchmove', tm)
    window.addEventListener('mouseup', up)
    window.addEventListener('touchend', up)
    return () => {
      window.removeEventListener('mousemove', mm)
      window.removeEventListener('touchmove', tm)
      window.removeEventListener('mouseup', up)
      window.removeEventListener('touchend', up)
    }
  }, [])

  return (
    <div ref={wrapRef} className="relative w-full h-full overflow-hidden select-none bg-inverse-surface">
      {/* After (base, full) */}
      <div ref={afterRef} className="absolute inset-0" />
      {/* Before (clipped) */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none" style={{ width: `${split}%` }}>
        <div ref={beforeRef} className="absolute top-0 left-0 h-full" style={{ width: wrapRef.current?.clientWidth ?? '100vw' }} />
      </div>
      {/* Labels */}
      <div className="absolute top-3 left-3 z-20 bg-inverse-surface/90 text-inverse-on-surface px-2.5 py-1 rounded-lg border border-outline/50 shadow-md pointer-events-none">
        <span className="text-label-badge font-semibold text-secondary-fixed tracking-wider">HISTORICAL BASELINE</span>
        <div className="text-label-coord font-mono">{beforeLabel}</div>
      </div>
      <div className="absolute top-3 right-3 z-20 bg-inverse-surface/90 text-inverse-on-surface px-2.5 py-1 rounded-lg border border-outline/50 shadow-md pointer-events-none">
        <span className="text-label-badge font-semibold text-tertiary-fixed tracking-wider">CURRENT OBSERVATION</span>
        <div className="text-label-coord font-mono text-right">{afterLabel}</div>
      </div>
      {/* Divider */}
      <div
        className="absolute top-0 bottom-0 z-30 w-[2px] bg-white cursor-ew-resize shadow-[0_0_10px_rgba(0,0,0,0.6)]"
        style={{ left: `${split}%` }}
        onMouseDown={(e) => {
          dragging.current = true
          e.preventDefault()
        }}
        onTouchStart={() => (dragging.current = true)}
      >
        <div className="absolute top-1/2 -translate-y-1/2 -left-4 w-8 h-8 rounded-full bg-surface-container-lowest border-2 border-primary shadow-xl flex items-center justify-center cursor-ew-resize hover:scale-105 transition-transform">
          <span className="material-symbols-outlined text-lg text-primary">drag_indicator</span>
        </div>
      </div>
    </div>
  )
}
