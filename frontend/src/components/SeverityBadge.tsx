import type { SeverityLevel } from '../api/types'

const CONFIG: Record<SeverityLevel, { label: string; classes: string; dot: string }> = {
  critical: { label: 'Critical', classes: 'bg-rose-50 text-rose-700 border-rose-200',     dot: 'bg-rose-400' },
  high:     { label: 'High',     classes: 'bg-amber-50 text-amber-700 border-amber-200',   dot: 'bg-amber-400' },
  moderate: { label: 'Moderate', classes: 'bg-yellow-50 text-yellow-700 border-yellow-200', dot: 'bg-yellow-400' },
  low:      { label: 'Low',      classes: 'bg-emerald-50 text-emerald-700 border-emerald-200', dot: 'bg-emerald-400' },
}

interface Props {
  severity: SeverityLevel
  size?: 'sm' | 'md'
}

export default function SeverityBadge({ severity, size = 'md' }: Props) {
  const { label, classes, dot } = CONFIG[severity] ?? CONFIG.low
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-medium ${classes} ${
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-0.5 text-sm'
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full flex-shrink-0 ${dot}`} />
      {label}
    </span>
  )
}
