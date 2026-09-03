import { NavLink, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { overviewService, zoneService } from '../../services'
import { useAuth } from '../../hooks/useAuth'
import { MODULE_META } from '../../lib/format'

const NAV_ITEMS = [
  { to: '/', key: 'overview' },
  { to: '/river', key: 'river' },
  { to: '/agriculture', key: 'agriculture' },
  { to: '/forest', key: 'forest' },
  { to: '/brick-kilns', key: 'brick_kiln' },
]

export default function SideNav({ onCreateZone }: { onCreateZone: () => void }) {
  const location = useLocation()
  const { user, logout } = useAuth()
  const { data: zones } = useQuery({ queryKey: ['zones'], queryFn: () => zoneService.list({ status: 'active' }) })
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: overviewService.health,
    refetchInterval: 60000,
  })

  const kilnCount = zones?.filter((z) => z.zone_type === 'brick_kiln').length ?? 0

  return (
    <aside className="fixed left-0 top-0 bottom-0 z-30 flex flex-col w-sidebar-width bg-surface-container-low border-r border-outline-variant justify-between">
      <div>
        {/* Brand */}
        <div className="h-12 flex items-center gap-2.5 px-3 border-b border-outline-variant bg-surface-container-lowest">
          <img src="/earthyy.svg" alt="Earthyy logo" className="w-7 h-7 rounded" />
          <div className="flex flex-col leading-tight">
            <span className="font-semibold tracking-tight text-on-surface">Earthyy</span>
            <span className="text-label-badge text-outline tracking-wider uppercase">Observation Intelligence</span>
          </div>
        </div>

        {/* Monitoring zones CTA */}
        <div className="p-2 border-b border-outline-variant bg-surface-container-lowest/50">
          <button
            onClick={onCreateZone}
            className="w-full flex items-center justify-between px-3 py-1.5 bg-primary text-white rounded-lg text-telemetry font-mono hover:bg-primary-container transition-colors shadow-sm"
          >
            <span className="flex items-center gap-1.5">
              <span className="material-symbols-outlined text-base" aria-hidden>add_circle</span>
              <span>Monitoring Zones</span>
            </span>
            <span className="bg-white/20 px-1.5 py-0.5 rounded text-[10px] font-semibold">
              {zones?.length ?? 0} ACTIVE
            </span>
          </button>
        </div>

        {/* Modules */}
        <nav className="py-1 flex flex-col" aria-label="Observation modules">
          <div className="px-3 py-1.5 text-label-coord font-mono text-outline uppercase tracking-wider">
            Primary Observables
          </div>
          {NAV_ITEMS.map(({ to, key }) => {
            const meta = MODULE_META[key]
            const active = location.pathname === to
            return (
              <NavLink
                key={key}
                to={to}
                className={
                  active
                    ? 'flex items-center gap-2 px-3 py-2 bg-surface-container-highest text-primary font-semibold border-l-2 border-primary'
                    : 'flex items-center gap-2 px-3 py-2 text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors border-l-2 border-transparent'
                }
              >
                <span className={`material-symbols-outlined text-lg ${active ? 'msym-fill' : 'text-outline'}`} aria-hidden>
                  {meta.icon}
                </span>
                <span className="text-sm flex-1">{meta.label}</span>
                {key === 'brick_kiln' && kilnCount > 0 ? (
                  <span className="text-label-coord font-mono text-tertiary bg-tertiary-fixed/60 px-1 rounded">
                    {kilnCount} zone{kilnCount > 1 ? 's' : ''}
                  </span>
                ) : meta.navBadge ? (
                  <span className="text-label-coord font-mono text-outline bg-surface-container-highest px-1 rounded">
                    {meta.navBadge}
                  </span>
                ) : active ? (
                  <span className="flex h-2 w-2 relative" aria-hidden>
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                  </span>
                ) : null}
              </NavLink>
            )
          })}
        </nav>

        {/* Sensor status */}
        <div className="mt-2 px-3 py-1 border-t border-outline-variant">
          <div className="text-label-coord font-mono text-outline uppercase tracking-wider mb-1.5">
            Multi-Sensor Status
          </div>
          <div className="space-y-1.5">
            {[
              { name: 'Earth Search STAC', detail: 'Sentinel-2 L2A • 10m' },
              { name: 'Planetary Computer', detail: 'Sentinel-2 / Landsat' },
              { name: 'Copernicus Data Space', detail: 'catalogue' },
            ].map((s) => (
              <div key={s.name} className="flex items-center justify-between p-1.5 rounded bg-surface-container-lowest border border-outline-variant">
                <div className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-secondary" aria-hidden></span>
                  <span className="text-telemetry font-mono text-on-surface">{s.name}</span>
                </div>
                <span className="text-label-coord font-mono text-outline">{s.detail}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-outline-variant bg-surface-container-lowest">
        <div className="flex items-center justify-between px-3 py-1.5 text-xs text-on-surface-variant">
          <span className="flex items-center gap-1.5">
            <span className="material-symbols-outlined text-base text-outline" aria-hidden>satellite_alt</span>
            Data Sources
          </span>
          <span
            className={`font-mono text-label-coord font-semibold ${health?.status === 'ok' ? 'text-secondary' : 'text-error'}`}
          >
            {health?.status === 'ok' ? 'ONLINE' : health ? 'DEGRADED' : '…'}
          </span>
        </div>
        <div className="flex items-center gap-2 px-3 py-2 border-t border-outline-variant">
          <div className="w-7 h-7 rounded bg-primary-container text-white flex items-center justify-center font-mono text-xs font-semibold">
            {user?.full_name?.split(' ').map((p) => p[0]).slice(0, 2).join('') ?? '—'}
          </div>
          <div className="flex flex-col min-w-0 flex-1 leading-tight">
            <span className="text-xs font-medium text-on-surface truncate">{user?.full_name ?? 'Analyst'}</span>
            <span className="text-label-coord font-mono text-outline truncate">{user?.role ?? ''} · Geo-Engine Operator</span>
          </div>
          <button onClick={logout} className="text-outline hover:text-error transition-colors p-1" title="Sign out" aria-label="Sign out">
            <span className="material-symbols-outlined text-base" aria-hidden>logout</span>
          </button>
        </div>
      </div>
    </aside>
  )
}
