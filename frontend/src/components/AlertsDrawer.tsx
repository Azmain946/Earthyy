import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { alertService } from '../services'
import { fmtAgo } from '../lib/format'
import type { Alert } from '../lib/types'

const SEVERITY_STYLES: Record<string, string> = {
  critical: 'bg-error text-white',
  warning: 'bg-tertiary-fixed text-tertiary',
  info: 'bg-primary-fixed text-primary',
}

export default function AlertsDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const { data: alerts, isLoading } = useQuery({
    queryKey: ['alerts', 'all'],
    queryFn: () => alertService.list(),
    enabled: open,
  })

  const ack = useMutation({
    mutationFn: (id: number) => alertService.acknowledge(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  })
  const resolve = useMutation({
    mutationFn: (id: number) => alertService.resolve(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  })

  if (!open) return null

  return (
    <div className="fixed top-12 right-0 bottom-0 z-40 w-96 bg-surface-container-lowest border-l border-outline-variant shadow-2xl flex flex-col" role="complementary" aria-label="Alerts">
      <div className="flex items-center justify-between px-4 py-3 border-b border-outline-variant bg-surface-container-low">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary text-lg" aria-hidden>notifications_active</span>
          <h3 className="font-semibold text-on-surface text-sm">Alert Feed</h3>
        </div>
        <button onClick={onClose} className="text-outline hover:text-on-surface" aria-label="Close alerts">
          <span className="material-symbols-outlined" aria-hidden>close</span>
        </button>
      </div>
      <div className="flex-1 overflow-y-auto divide-y divide-outline-variant/60">
        {isLoading && <div className="p-4 text-xs text-outline">Loading alerts…</div>}
        {alerts?.length === 0 && (
          <div className="p-6 text-center text-xs text-on-surface-variant">
            No alerts. Alerts are generated only when real analysis measurements cross zone thresholds.
          </div>
        )}
        {alerts?.map((a: Alert) => (
          <div key={a.id} className={`p-3 ${a.status === 'unread' ? 'bg-surface-container-low/60' : ''}`}>
            <div className="flex items-center gap-2">
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${SEVERITY_STYLES[a.severity]}`}>
                {a.severity}
              </span>
              <span className="text-xs font-semibold text-on-surface flex-1">{a.title}</span>
              <span className="text-label-coord font-mono text-outline">{fmtAgo(a.created_at)}</span>
            </div>
            <p className="mt-1 text-xs text-on-surface-variant leading-relaxed">{a.message}</p>
            <div className="mt-1.5 flex items-center justify-between">
              <span className="text-label-coord font-mono text-outline uppercase">{a.status}</span>
              <div className="flex gap-1.5">
                {a.status === 'unread' && (
                  <button
                    onClick={() => ack.mutate(a.id)}
                    className="px-2 py-0.5 text-label-coord font-mono border border-outline-variant rounded hover:bg-surface-container"
                  >
                    Acknowledge
                  </button>
                )}
                {a.status !== 'resolved' && (
                  <button
                    onClick={() => resolve.mutate(a.id)}
                    className="px-2 py-0.5 text-label-coord font-mono border border-outline-variant rounded hover:bg-surface-container"
                  >
                    Resolve
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
