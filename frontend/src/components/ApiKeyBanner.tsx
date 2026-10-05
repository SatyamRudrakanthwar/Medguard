import { Link } from 'react-router-dom'

export default function ApiKeyBanner() {
  const hasKey = Boolean(localStorage.getItem('medguard_api_key'))
  if (hasKey) return null

  return (
    <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 flex items-center justify-between gap-4">
      <div className="flex items-center gap-2 text-sm text-amber-800">
        <span>⚠️</span>
        <span>
          No Anthropic API key set — reviews will run with stub agents (demo mode).
        </span>
      </div>
      <Link
        to="/settings"
        className="flex-shrink-0 text-xs font-medium text-amber-800 underline hover:no-underline"
      >
        Add key →
      </Link>
    </div>
  )
}
