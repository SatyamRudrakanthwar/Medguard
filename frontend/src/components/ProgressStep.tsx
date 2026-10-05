import { useState } from 'react'
import type { StreamEvent } from '../api/types'

interface Props {
  events: StreamEvent[]
  isRunning: boolean
}

const STEP_ICONS: Record<string, string> = {
  validate_input:        '🔍',
  normalize_medications: '💊',
  analyze_case:          '🧠',
  create_plan:           '📋',
  execute_research:      '🔬',
  aggregate_evidence:    '📊',
  validate_evidence:     '✅',
  research_again:        '🔄',
  analyze_risk:          '⚠️',
  generate_report:       '📄',
  blocked_end:           '🚫',
}

export default function ProgressStep({ events, isRunning }: Props) {
  const stepEvents = events.filter(e => e.event === 'step_completed')
  const [expanded, setExpanded] = useState(false)

  // While running always show all steps; when done show summary + toggle
  if (isRunning) {
    return (
      <div className="space-y-1">
        {stepEvents.map((event, i) => (
          <div key={i} className="flex items-center gap-2.5 rounded-lg px-3 py-2 bg-white border border-slate-100 text-sm">
            <span className="text-base leading-none">{STEP_ICONS[event.step ?? ''] ?? '▸'}</span>
            <span className="text-slate-700">{event.message}</span>
            <span className="ml-auto text-xs text-slate-400">
              {event.data?.retry_count ? `retry ${event.data.retry_count}` : ''}
            </span>
            <span className="text-green-500 text-xs">✓</span>
          </div>
        ))}
        <div className="flex items-center gap-2.5 rounded-lg px-3 py-2 bg-blue-50 border border-blue-100 text-sm">
          <span className="h-3 w-3 rounded-full bg-blue-500 animate-pulse" />
          <span className="text-blue-700">Processing…</span>
        </div>
      </div>
    )
  }

  // Done — collapsed summary with optional expand
  return (
    <div>
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center justify-between rounded-lg px-3 py-2 bg-slate-50 border border-slate-200 text-sm hover:bg-slate-100 transition-colors"
      >
        <div className="flex items-center gap-2 text-slate-600">
          <span className="text-green-500">✓</span>
          <span>{stepEvents.length} steps completed</span>
        </div>
        <span className="text-xs text-slate-400">{expanded ? '▲ hide' : '▼ show'}</span>
      </button>

      {expanded && (
        <div className="mt-1 space-y-1">
          {stepEvents.map((event, i) => (
            <div key={i} className="flex items-center gap-2.5 rounded-lg px-3 py-2 bg-white border border-slate-100 text-sm">
              <span className="text-base leading-none">{STEP_ICONS[event.step ?? ''] ?? '▸'}</span>
              <span className="text-slate-600">{event.message}</span>
              <span className="ml-auto text-xs text-slate-400">
                {event.data?.retry_count ? `retry ${event.data.retry_count}` : ''}
              </span>
              <span className="text-green-500 text-xs">✓</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
