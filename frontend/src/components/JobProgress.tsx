import type { Job } from '../lib/types'

const STAGES: Array<{ key: string; label: string }> = [
  { key: 'preparing_area', label: 'Preparing area' },
  { key: 'searching_imagery', label: 'Finding satellite observations' },
  { key: 'retrieving_imagery', label: 'Preparing imagery' },
  { key: 'analyzing', label: 'Running analysis' },
  { key: 'calculating_changes', label: 'Calculating changes' },
  { key: 'generating_layers', label: 'Generating map layers' },
]

const ORDER = ['queued', 'preparing_area', 'searching_imagery', 'retrieving_imagery', 'processing', 'analyzing', 'calculating_changes', 'generating_layers', 'completed']

export default function JobProgress({ job }: { job: Job }) {
  if (job.status === 'failed') {
    return (
      <div className="p-3 bg-error-container/40 border border-error/40 rounded-lg" role="alert">
        <div className="flex items-center gap-1.5 text-error text-xs font-semibold">
          <span className="material-symbols-outlined text-base" aria-hidden>error</span>
          Analysis failed
        </div>
        <p className="mt-1 text-xs text-on-error-container leading-relaxed">{job.error}</p>
      </div>
    )
  }

  const currentIdx = ORDER.indexOf(job.stage === 'processing' ? 'analyzing' : job.stage)

  return (
    <div className="p-3 bg-surface-container-lowest border border-outline-variant rounded-lg space-y-1.5" aria-live="polite">
      <div className="flex items-center justify-between text-label-coord font-mono text-outline">
        <span className="uppercase tracking-wider">Processing Job</span>
        <span>{Math.round(job.progress * 100)}%</span>
      </div>
      <div className="w-full h-1 bg-surface-container-high rounded overflow-hidden" aria-hidden>
        <div className="h-full bg-primary transition-all duration-500" style={{ width: `${job.progress * 100}%` }} />
      </div>
      <ul className="pt-1 space-y-1">
        {STAGES.map((s) => {
          const idx = ORDER.indexOf(s.key)
          const done = job.status === 'completed' || idx < currentIdx
          const active = !done && idx === currentIdx
          return (
            <li key={s.key} className="flex items-center gap-2 text-xs">
              {done ? (
                <span className="material-symbols-outlined text-base text-secondary" aria-hidden>check_circle</span>
              ) : active ? (
                <span className="w-4 h-4 flex items-center justify-center" aria-hidden>
                  <span className="w-2.5 h-2.5 rounded-full border-2 border-primary border-t-transparent animate-spin" />
                </span>
              ) : (
                <span className="material-symbols-outlined text-base text-outline-variant" aria-hidden>radio_button_unchecked</span>
              )}
              <span className={done ? 'text-on-surface-variant' : active ? 'text-on-surface font-medium' : 'text-outline'}>
                {s.label}
              </span>
            </li>
          )
        })}
      </ul>
      {job.status === 'completed' && (
        <div className="flex items-center gap-1.5 text-secondary text-xs font-semibold pt-1">
          <span className="material-symbols-outlined text-base" aria-hidden>task_alt</span>
          Analysis complete
        </div>
      )}
    </div>
  )
}
