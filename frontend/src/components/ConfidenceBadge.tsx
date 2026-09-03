export default function ConfidenceBadge({ score, level }: { score: number | null; level: string }) {
  const styles: Record<string, string> = {
    high: 'bg-secondary-fixed/40 text-secondary',
    medium: 'bg-primary-fixed text-primary',
    low: 'bg-tertiary-fixed/60 text-tertiary',
    unavailable: 'bg-surface-container-highest text-outline',
  }
  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-label-coord font-mono ${styles[level] ?? styles.unavailable}`}
      title="Data-quality-derived confidence (valid pixel fraction, cloud cover) — not a validated model accuracy"
    >
      {score !== null ? `${Math.round(score * 100)}% CONFIDENCE` : 'CONFIDENCE UNAVAILABLE'}
      <span className="uppercase">· {level}</span>
    </span>
  )
}
