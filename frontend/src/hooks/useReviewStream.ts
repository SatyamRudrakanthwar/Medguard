import { useState, useEffect, useRef } from 'react'
import type { StreamEvent } from '../api/types'
import { api } from '../api/client'

export type StreamStatus = 'connecting' | 'streaming' | 'done' | 'error'

export interface UseReviewStreamResult {
  events: StreamEvent[]
  status: StreamStatus
  error?: string
}

export function useReviewStream(reviewId: string | undefined): UseReviewStreamResult {
  const [events, setEvents] = useState<StreamEvent[]>([])
  const [status, setStatus] = useState<StreamStatus>('connecting')
  const [error, setError] = useState<string | undefined>()
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!reviewId) return

    setEvents([])
    setStatus('connecting')
    setError(undefined)

    const es = new EventSource(api.streamUrl(reviewId))
    esRef.current = es

    es.onopen = () => {
      setStatus('streaming')
    }

    es.onmessage = (e: MessageEvent<string>) => {
      try {
        const event = JSON.parse(e.data) as StreamEvent
        setEvents(prev => [...prev, event])

        if (event.event === 'done') {
          setStatus('done')
          es.close()
        } else if (event.event === 'error') {
          setStatus('error')
          setError(event.message ?? 'Unknown error')
          es.close()
        }
      } catch {
        // ignore malformed event
      }
    }

    es.onerror = () => {
      // EventSource auto-reconnects — only treat as final error if already done
      if (status === 'done') return
      setStatus('error')
      setError('Connection lost')
      es.close()
    }

    return () => {
      es.close()
      esRef.current = null
    }
  }, [reviewId]) // eslint-disable-line react-hooks/exhaustive-deps

  return { events, status, error }
}
