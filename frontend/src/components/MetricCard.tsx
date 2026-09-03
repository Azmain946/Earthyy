interface MetricCardProps {
  label: string
  value: string
  sub?: string
  tone?: 'default' | 'error' | 'secondary' | 'tertiary'
}

const TONES: Record<string, string> = {
  default: 'text-on-surface',
  error: 'text-error',
  secondary: 'text-secondary',
  tertiary: 'text-tertiary-container',
}

export default function MetricCard({ label, value, sub, tone = 'default' }: MetricCardProps) {
  return (
    <div className="p-2 bg-surface-container-low border border-outline-variant rounded-lg flex flex-col">
      <span className="text-label-coord font-mono text-outline uppercase">{label}</span>
      <span className={`text-base font-bold font-mono mt-0.5 ${TONES[tone]}`}>{value}</span>
      {sub && <span className="text-[10px] text-on-surface-variant mt-0.5">{sub}</span>}
    </div>
  )
}
