import type { MapLayer } from '../../lib/types'

interface LayerPanelProps {
  layers: MapLayer[]
  visibleKeys: Record<string, boolean>
  onToggle: (key: string) => void
  rasterOpacity: number
  onOpacity: (v: number) => void
}

export default function LayerPanel({ layers, visibleKeys, onToggle, rasterOpacity, onOpacity }: LayerPanelProps) {
  if (layers.length === 0) return null
  const visibleCount = layers.filter((l) => visibleKeys[l.key]).length
  return (
    <div className="absolute top-3 left-3 z-20 w-64 bg-surface-container-lowest/95 backdrop-blur-sm border border-outline-variant rounded-lg shadow-sm p-2.5">
      <div className="flex items-center justify-between pb-1.5 border-b border-outline-variant mb-1.5">
        <span className="text-telemetry font-mono text-on-surface font-semibold flex items-center gap-1">
          <span className="material-symbols-outlined text-sm text-primary" aria-hidden>layers</span>
          Cartographic Layers
        </span>
        <span className="text-label-coord font-mono text-outline">{visibleCount} visible</span>
      </div>
      <div className="space-y-1 max-h-64 overflow-y-auto">
        {layers.map((layer) => (
          <label
            key={layer.key}
            className="flex items-center justify-between p-1 rounded hover:bg-surface-container cursor-pointer transition-colors"
          >
            <span className="flex items-center gap-2 min-w-0">
              <input
                type="checkbox"
                checked={!!visibleKeys[layer.key]}
                onChange={() => onToggle(layer.key)}
                className="rounded text-primary focus:ring-0 border-outline-variant w-3.5 h-3.5"
              />
              <span className="text-xs text-on-surface truncate">{layer.title}</span>
            </span>
            {layer.kind === 'raster' ? (
              <span className="w-5 h-2 rounded-sm bg-gradient-to-r from-amber-500 via-lime-500 to-emerald-600 shrink-0" aria-hidden />
            ) : (
              <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: layer.style?.color ?? '#0369a1' }} aria-hidden />
            )}
          </label>
        ))}
      </div>
      <div className="mt-1.5 pt-1.5 border-t border-outline-variant flex items-center gap-2">
        <span className="text-label-coord font-mono text-outline whitespace-nowrap">Raster opacity</span>
        <input
          type="range"
          min={0}
          max={100}
          value={Math.round(rasterOpacity * 100)}
          onChange={(e) => onOpacity(Number(e.target.value) / 100)}
          className="w-full h-1 bg-outline-variant rounded appearance-none accent-primary cursor-pointer"
          aria-label="Raster layer opacity"
        />
        <span className="text-label-coord font-mono text-on-surface w-8 text-right">{Math.round(rasterOpacity * 100)}%</span>
      </div>
    </div>
  )
}
