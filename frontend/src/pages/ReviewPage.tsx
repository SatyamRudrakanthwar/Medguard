import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../api/client'
import type { ReviewResponse } from '../api/types'
import { useReviewStream } from '../hooks/useReviewStream'
import ProgressStep from '../components/ProgressStep'
import FindingCard from '../components/FindingCard'
import SeverityBadge from '../components/SeverityBadge'

export default function ReviewPage() {
  const { reviewId } = useParams<{ reviewId: string }>()
  const { events, status: streamStatus } = useReviewStream(reviewId)
  const [review, setReview] = useState<ReviewResponse | null>(null)
  const [polling, setPolling] = useState(true)

  // Poll for the final report once the stream signals done
  useEffect(() => {
    if (!reviewId || !polling) return
    if (streamStatus !== 'done' && streamStatus !== 'error') return

    let cancelled = false
    const attempt = async () => {
      try {
        const r = await api.getReview(reviewId)
        if (!cancelled) {
          setReview(r)
          if (r.status === 'completed' || r.status === 'failed' || r.status === 'blocked') {
            setPolling(false)
          }
        }
      } catch { /* ignore */ }
    }
    attempt()
    return () => { cancelled = true }
  }, [reviewId, streamStatus, polling])

  // Also poll every 3s while processing (handles page reload)
  useEffect(() => {
    if (!reviewId || !polling) return
    const id = setInterval(async () => {
      try {
        const r = await api.getReview(reviewId)
        setReview(r)
        if (r.status === 'completed' || r.status === 'failed' || r.status === 'blocked') {
          setPolling(false)
        }
      } catch { /* ignore */ }
    }, 3000)
    return () => clearInterval(id)
  }, [reviewId, polling])

  const isRunning = !review || review.status === 'processing'
  const isCompleted = review?.status === 'completed'

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Safety Review</h1>
          <p className="text-xs text-slate-400 font-mono mt-0.5">{reviewId}</p>
        </div>
        <Link to="/" className="btn-secondary text-sm">
          ← New Review
        </Link>
      </div>

      {/* Medications */}
      {review?.medications_reviewed && review.medications_reviewed.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {review.medications_reviewed.map(m => (
            <span key={m} className="rounded-full bg-blue-50 border border-blue-200 px-2.5 py-0.5 text-sm text-blue-800">
              {m}
            </span>
          ))}
        </div>
      )}

      {/* Progress stream */}
      {(isRunning || events.length > 0) && (
        <div className="card">
          <h2 className="text-sm font-semibold text-slate-700 mb-3">
            {isRunning ? 'Analysis in Progress' : 'Completed Steps'}
          </h2>
          <ProgressStep events={events} isRunning={isRunning} />
        </div>
      )}

      {/* Blocked */}
      {review?.status === 'blocked' && (
        <div className="card border-amber-200 bg-amber-50">
          <h2 className="font-semibold text-amber-800 mb-1">Request Blocked</h2>
          <p className="text-sm text-amber-700">{review.message}</p>
        </div>
      )}

      {/* Failed */}
      {review?.status === 'failed' && (
        <div className="card border-red-200 bg-red-50">
          <h2 className="font-semibold text-red-800 mb-1">Review Failed</h2>
          <p className="text-sm text-red-700">{review.message}</p>
        </div>
      )}

      {/* Results */}
      {isCompleted && review && (
        <>
          {/* Summary bar */}
          <div className="card flex flex-wrap items-center gap-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-slate-900">{review.findings.length}</p>
              <p className="text-xs text-slate-500">Total Findings</p>
            </div>
            {review.high_severity_count > 0 && (
              <div className="text-center">
                <p className="text-2xl font-bold text-orange-600">{review.high_severity_count}</p>
                <p className="text-xs text-slate-500">High/Critical</p>
              </div>
            )}
            <div className="ml-auto flex flex-wrap gap-1">
              {Array.from(new Set(review.findings.map(f => f.severity))).map(s => (
                <SeverityBadge key={s} severity={s} size="sm" />
              ))}
            </div>
          </div>

          {/* Findings */}
          {review.findings.length > 0 ? (
            <div>
              <h2 className="font-semibold text-slate-900 mb-3">Safety Findings</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-start">
                {review.findings.map((f) => (
                  <FindingCard key={f.finding_id} finding={f} />
                ))}
              </div>
            </div>
          ) : (
            <div className="card text-center py-8 text-slate-500">
              <p className="text-3xl mb-2">✓</p>
              <p className="font-medium">No significant safety findings identified.</p>
            </div>
          )}

          {/* Additional info */}
          {review.additional_information.length > 0 && (
            <div className="card space-y-2">
              <h2 className="text-sm font-semibold text-slate-700">Additional Notes</h2>
              <ul className="space-y-1">
                {review.additional_information.map((info, i) => (
                  <li key={i} className="text-sm text-slate-600 flex gap-2">
                    <span className="text-blue-400 flex-shrink-0">•</span>
                    {info}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Disclaimer */}
          <div className="rounded-lg bg-slate-100 px-4 py-3 text-xs text-slate-500 leading-relaxed">
            {review.disclaimer}
          </div>
        </>
      )}
    </div>
  )
}
