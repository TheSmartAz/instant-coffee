const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export type RequestError = Error & {
  status?: number
  data?: unknown
}

const buildUrl = (path: string) =>
  path.startsWith('http') ? path : `${API_BASE}${path}`

const parseBody = async (response: Response) => {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

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
    throw error
  }

  return data as T
}

export const api = {
  sessions: {
    list: () => request<{ sessions: unknown[]; total?: number }>('/api/sessions'),
    get: (id: string) => request<unknown>(`/api/sessions/${id}`),
    create: (data: { title?: string }) =>
      request<unknown>('/api/sessions', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    messages: (id: string) =>
      request<{ messages: unknown[] }>(`/api/sessions/${id}/messages`),
    versions: (id: string) =>
      request<{ versions: unknown[]; current_version?: number }>(
        `/api/sessions/${id}/versions`
      ),
    revert: async (id: string, versionId: string | number) => {
      try {
        return await request<unknown>(
          `/api/sessions/${id}/versions/${versionId}/revert`,
          {
            method: 'POST',
          }
        )
      } catch (error) {
        const status = (error as RequestError)?.status
        if (status !== 404 && status !== 405) throw error
        return request<unknown>(`/api/sessions/${id}/rollback`, {
          method: 'POST',
          body: JSON.stringify({ version: Number(versionId) }),
        })
      }
    },
  },
  chat: {
    send: (sessionId: string, message: string) =>
      request<unknown>('/api/chat', {
        method: 'POST',
        body: JSON.stringify({ session_id: sessionId, message }),
      }),
    streamUrl: (sessionId: string, message?: string) => {
      const params = new URLSearchParams({ session_id: sessionId })
      if (message) params.set('message', message)
      return buildUrl(`/api/chat/stream?${params.toString()}`)
    },
  },
  settings: {
    get: () => request<unknown>('/api/settings'),
    update: (data: Record<string, unknown>) =>
      request<unknown>('/api/settings', {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
  },
  tasks: {
    retry: (id: string) =>
      request<unknown>(`/api/task/${id}/retry`, { method: 'POST' }),
    skip: (id: string) =>
      request<unknown>(`/api/task/${id}/skip`, { method: 'POST' }),
  },
}

export { API_BASE }
