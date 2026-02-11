import type { z } from 'zod'

export const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export type RequestError = Error & {
  status?: number
  data?: unknown
  errorType?: 'network' | 'timeout' | 'server' | 'client' | 'unknown'
}

export function classifyError(error: unknown): RequestError {
  if (error instanceof Error && 'status' in error) {
    const reqErr = error as RequestError
    const status = reqErr.status ?? 0
    if (status >= 500) reqErr.errorType = 'server'
    else if (status === 429) reqErr.errorType = 'server'
    else if (status >= 400) reqErr.errorType = 'client'
    else reqErr.errorType = 'unknown'
    return reqErr
  }
  if (error instanceof TypeError && /fetch|network/i.test(error.message)) {
    const reqErr = error as RequestError
    reqErr.errorType = 'network'
    return reqErr
  }
  if (error instanceof DOMException && error.name === 'AbortError') {
    const reqErr = error as RequestError
    reqErr.errorType = 'timeout'
    return reqErr
  }
  const reqErr = (error instanceof Error ? error : new Error(String(error))) as RequestError
  reqErr.errorType = 'unknown'
  return reqErr
}

export function userFriendlyMessage(error: RequestError): string {
  switch (error.errorType) {
    case 'network':
      return 'Network error — check your connection and try again.'
    case 'timeout':
      return 'Request timed out — the server may be busy, try again.'
    case 'server':
      return error.status === 429
        ? 'Rate limited — please wait a moment and try again.'
        : 'Server error — please try again later.'
    case 'client':
      return error.message || 'Invalid request.'
    default:
      return error.message || 'Something went wrong.'
  }
}

export const buildUrl = (path: string) =>
  path.startsWith('http') ? path : `${API_BASE}${path}`

export const buildQuery = (
  params: Record<string, string | number | boolean | undefined>
) => {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined) return
    search.set(key, String(value))
  })
  const query = search.toString()
  return query ? `?${query}` : ''
}

const parseBody = async (response: Response) => {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

const RETRYABLE_STATUSES = new Set([429, 500, 502, 503, 504])
const MAX_RETRIES = 2
const BASE_DELAY_MS = 1000
const MAX_RETRY_DELAY_MS = 60_000

function parseRetryAfter(response: Response): number | null {
  const header = response.headers.get('Retry-After')
  if (!header) return null
  const seconds = Number(header)
  if (!Number.isNaN(seconds) && seconds > 0) {
    return Math.min(seconds * 1000, MAX_RETRY_DELAY_MS)
  }
  const dateMs = Date.parse(header)
  if (!Number.isNaN(dateMs)) {
    const delay = dateMs - Date.now()
    if (delay > 0) return Math.min(delay, MAX_RETRY_DELAY_MS)
  }
  return null
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let lastError: RequestError | null = null
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const response = await fetch(buildUrl(path), {
        ...options,
        headers,
      })

      const data = await parseBody(response)

      if (!response.ok) {
        const error: RequestError = new Error(
          (data && (data.message || data.detail)) || response.statusText
        )
        error.status = response.status
        error.data = data
        if (RETRYABLE_STATUSES.has(response.status) && attempt < MAX_RETRIES) {
          lastError = classifyError(error)
          const retryAfter = response.status === 429 ? parseRetryAfter(response) : null
          const delay = retryAfter ?? Math.min(
            BASE_DELAY_MS * Math.pow(2, attempt) * (0.5 + Math.random() * 0.5),
            MAX_RETRY_DELAY_MS,
          )
          await new Promise((resolve) => setTimeout(resolve, delay))
          continue
        }
        throw classifyError(error)
      }

      return data as T
    } catch (error) {
      const classified = classifyError(error)
      if (classified.errorType === 'network' && attempt < MAX_RETRIES) {
        lastError = classified
        const delay = BASE_DELAY_MS * Math.pow(2, attempt) * (0.5 + Math.random() * 0.5)
        await new Promise((resolve) => setTimeout(resolve, delay))
        continue
      }
      throw classified
    }
  }
  throw lastError ?? new Error('Request failed after retries')
}

export async function validatedRequest<T>(
  schema: z.ZodType<T>,
  path: string,
  options?: RequestInit
): Promise<T> {
  const raw = await request<unknown>(path, options)
  const result = schema.safeParse(raw)
  if (result.success) return result.data
  console.warn(`[API] Response validation warning for ${path}:`, result.error.issues)
  return raw as T
}
