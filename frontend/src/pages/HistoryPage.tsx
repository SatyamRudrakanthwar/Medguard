import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { ReviewResponse } from '../api/types'
import SeverityBadge from '../components/SeverityBadge'

const STATUS_COLORS: Record<string, string> = {
  completed: 'text-green-700 bg-green-50 border-green-200',
  processing: 'text-blue-700 bg-blue-50 border-blue-200',
  failed:    'text-red-700 bg-red-50 border-red-200',
  blocked:   'text-amber-700 bg-amber-50 border-amber-200',
  pending:   'text-slate-700 bg-slate-50 border-slate-200',
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function HistoryPage() {
  const [reviews, setReviews] = useState<ReviewResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.listReviews()
      .then(setReviews)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <span className="h-6 w-6 rounded-full border-2 border-blue-500/30 border-t-blue-500 animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="card bg-red-50 border-red-200 text-red-700 text-sm">
        {error}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-900">Review History</h1>
        <Link to="/" className="btn-primary text-sm">New Review</Link>
      </div>

      {reviews.length === 0 ? (
        <div className="card text-center py-12 text-slate-500">
          <p className="text-3xl mb-3">📋</p>
          <p className="font-medium">No reviews yet.</p>
          <Link to="/" className="mt-3 inline-block text-sm text-blue-600 hover:underline">
            Run your first review →
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {reviews.map(review => (
            <Link
              key={review.review_id}
              to={`/review/${review.review_id}`}
              className="card block hover:border-blue-200 hover:shadow-md transition-all"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {review.medications_reviewed.slice(0, 5).map(m => (
                      <span key={m} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700">
                        {m}
                      </span>
                    ))}
                    {review.medications_reviewed.length > 5 && (
                      <span className="text-xs text-slate-400">
                        +{review.medications_reviewed.length - 5} more
                      </span>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                    <span>{formatDate(review.created_at)}</span>
                    {review.status === 'completed' && (
                      <>
                        <span>{review.findings.length} finding{review.findings.length !== 1 ? 's' : ''}</span>
                        {review.high_severity_count > 0 && (
                          <SeverityBadge severity="high" size="sm" />
                        )}
                      </>
                    )}
                  </div>
                </div>

                <span
                  className={`flex-shrink-0 rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize ${
                    STATUS_COLORS[review.status] ?? STATUS_COLORS.pending
                  }`}
                >
                  {review.status}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
