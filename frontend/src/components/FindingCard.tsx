import { useState } from 'react'
import type { SafetyFinding, SeverityLevel } from '../api/types'

const SEVERITY_CONFIG: Record<SeverityLevel, {
  label: string
  dot: string
  strip: string
  text: string
  border: string
}> = {
  critical: { label: 'Critical', dot: 'bg-rose-400',    strip: 'bg-rose-50',    text: 'text-rose-700',    border: 'border-rose-200' },
  high:     { label: 'High',     dot: 'bg-amber-400',   strip: 'bg-amber-50',   text: 'text-amber-700',   border: 'border-amber-200' },
  moderate: { label: 'Moderate', dot: 'bg-yellow-400',  strip: 'bg-yellow-50',  text: 'text-yellow-700',  border: 'border-yellow-200' },
  low:      { label: 'Low',      dot: 'bg-emerald-400', strip: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
}

const FINDING_TYPE_LABELS: Record<string, string> = {
  drug_interaction:    'Drug Interaction',
  contraindication:    'Contraindication',
  adverse_effect:      'Adverse Effect',
  warning:             'Warning',
  general_information: 'Information',
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 80 ? 'bg-emerald-400' : pct >= 60 ? 'bg-yellow-400' : 'bg-rose-400'
  const label = pct >= 80 ? 'High' : pct >= 60 ? 'Moderate' : 'Low'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1 rounded-full bg-slate-100 overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-slate-400 flex-shrink-0 tabular-nums">{label} confidence · {pct}%</span>
    </div>
  )
}

interface Props {
  finding: SafetyFinding
}

export default function FindingCard({ finding }: Props) {
  const [open, setOpen] = useState(false)
  const cfg = SEVERITY_CONFIG[finding.severity] ?? SEVERITY_CONFIG.low
  const typeLabel = FINDING_TYPE_LABELS[finding.finding_type] ?? finding.finding_type

  return (
    <div
      className={`rounded-xl border ${cfg.border} bg-white shadow-sm cursor-pointer transition-shadow hover:shadow-md`}
      onClick={() => setOpen(o => !o)}
    >
      {/* Header strip */}
      <div className={`${cfg.strip} ${cfg.text} px-3.5 py-2 flex items-center justify-between rounded-t-xl`}>
        <div className="flex items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full flex-shrink-0 ${cfg.dot}`} />
          <span className="text-xs font-semibold">{cfg.label}</span>
          <span className="text-xs opacity-50">·</span>
          <span className="text-xs opacity-70">{typeLabel}</span>
        </div>
        <span className="text-xs opacity-50">{open ? '▲' : '▼'}</span>
      </div>

      {/* Body — always visible */}
      <div className="px-3.5 pt-3 pb-3 space-y-2.5">
        {/* Title */}
        <p className="text-sm font-semibold text-slate-800 leading-snug">{finding.title}</p>

        {/* Medication tags — clean, no emoji */}
        <div className="flex flex-wrap gap-1">
          {finding.medications_involved.map(m => (
            <span
              key={m}
              className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600"
            >
              {m}
            </span>
          ))}
        </div>

        {/* Expanded content */}
        {open && (
          <div className="space-y-2.5 pt-1 border-t border-slate-100">
            {/* Description */}
            <p className="text-sm text-slate-600 leading-relaxed">{finding.description}</p>

            {/* Confidence */}
            <ConfidenceBar value={finding.confidence} />

            {/* Professional review note */}
            {finding.requires_professional_review && (
              <p className="text-xs text-slate-400 italic">
                Consult a healthcare professional before making any medication changes.
              </p>
            )}

            {/* Evidence */}
            {finding.evidence.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                  Evidence sources
                </p>
                {finding.evidence.slice(0, 3).map((ev, i) => (
                  <div key={i} className="rounded-lg bg-slate-50 px-3 py-2 space-y-0.5">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-slate-600">{ev.source}</span>
                      <span className="text-xs text-slate-400">{Math.round(ev.support_score * 100)}% relevance</span>
                    </div>
                    {ev.excerpt && (
                      <p className="text-xs text-slate-500 leading-relaxed line-clamp-2">{ev.excerpt}</p>
                    )}
                    {ev.url && (
                      <a
                        href={ev.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={e => e.stopPropagation()}
                        className="text-xs text-blue-500 hover:underline"
                      >
                        View source →
                      </a>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
