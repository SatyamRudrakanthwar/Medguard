import type { ReviewRequest, ReviewResponse } from './types'

const BASE = '/api/v1'

function getApiKey(): string {
  try { return localStorage.getItem('medguard_api_key') ?? '' } catch { return '' }
}

function getProvider(): string {
  try { return localStorage.getItem('medguard_provider') ?? '' } catch { return '' }
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const apiKey = getApiKey()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }
  if (apiKey) headers['X-API-Key'] = apiKey
  const provider = getProvider()
  if (provider) headers['X-Provider'] = provider

  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  createReview(data: ReviewRequest): Promise<ReviewResponse> {
    return request('/review', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  getReview(reviewId: string): Promise<ReviewResponse> {
    return request(`/review/${reviewId}`)
  },

  listReviews(): Promise<ReviewResponse[]> {
    return request('/review')
  },

  streamUrl(reviewId: string): string {
    return `${BASE}/review/${reviewId}/stream`
  },
}
