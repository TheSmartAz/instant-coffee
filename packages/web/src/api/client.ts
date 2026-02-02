const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export type RequestError = Error & {
  status?: number
  data?: unknown
}

const buildUrl = (path: string) =>
  path.startsWith('http') ? path : `${API_BASE}${path}`

const buildQuery = (
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
    remove: (id: string) =>
      request<{ deleted: boolean }>(`/api/sessions/${id}`, { method: 'DELETE' }),
    messages: (id: string) =>
      request<{ messages: unknown[] }>(`/api/sessions/${id}/messages`),
    versions: (id: string) =>
      request<{ versions: unknown[]; current_version?: number }>(
        `/api/sessions/${id}/versions`
      ),
    clearMessages: (id: string) =>
      request<{ deleted: number }>(`/api/sessions/${id}/messages`, {
        method: 'DELETE',
      }),
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
    send: (
      sessionId: string,
      message: string,
      options?: { interview?: boolean; generateNow?: boolean }
    ) =>
      request<unknown>('/api/chat', {
        method: 'POST',
        body: JSON.stringify({
          session_id: sessionId,
          message,
          interview: options?.interview,
          generate_now: options?.generateNow,
        }),
      }),
    streamUrl: (
      sessionId: string,
      message?: string,
      options?: { interview?: boolean; generateNow?: boolean }
    ) => {
      const params = new URLSearchParams({ session_id: sessionId })
      if (message) params.set('message', message)
      if (options?.interview !== undefined) {
        params.set('interview', options.interview ? 'true' : 'false')
      }
      if (options?.generateNow !== undefined) {
        params.set('generate_now', options.generateNow ? 'true' : 'false')
      }
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
  productDocs: {
    get: (sessionId: string) =>
      request<unknown>(`/api/sessions/${sessionId}/product-doc`).catch(
        (error: RequestError) => {
          if (error.status === 404) return null
          throw error
        }
      ),
  },
  productDocHistory: {
    getProductDocHistory: (
      sessionId: string,
      options?: { includeReleased?: boolean }
    ) =>
      request<import('../types').ProductDocHistoryListResponse>(
        `/api/sessions/${sessionId}/product-doc/history${buildQuery({
          include_released: options?.includeReleased,
        })}`
      ),
    getProductDocHistoryVersion: (sessionId: string, historyId: number) =>
      request<import('../types').ProductDocHistoryResponse>(
        `/api/sessions/${sessionId}/product-doc/history/${historyId}`
      ),
    pinProductDocHistory: (sessionId: string, historyId: number) =>
      request<import('../types').ProductDocHistoryPinResponse | import('../types').ProductDocHistory>(
        `/api/sessions/${sessionId}/product-doc/history/${historyId}/pin`,
        { method: 'POST' }
      ),
    unpinProductDocHistory: (sessionId: string, historyId: number) =>
      request<import('../types').ProductDocHistoryPinResponse | import('../types').ProductDocHistory>(
        `/api/sessions/${sessionId}/product-doc/history/${historyId}/unpin`,
        { method: 'POST' }
      ),
  },
  pages: {
    list: (sessionId: string) =>
      request<{ pages: unknown[]; total: number }>(
        `/api/sessions/${sessionId}/pages`
      ),
    get: (pageId: string) => request<unknown>(`/api/pages/${pageId}`),
    previewUrl: (pageId: string) => buildUrl(`/api/pages/${pageId}/preview`),
    getPreview: (pageId: string) =>
      request<{ page_id: string; slug: string; html: string; version: number }>(
        `/api/pages/${pageId}/preview`,
        { headers: { Accept: 'application/json' } }
      ),
    getVersions: (pageId: string, includeReleased?: boolean) =>
      request<import('../types').PageVersionListResponse>(
        `/api/pages/${pageId}/versions${buildQuery({
          include_released: includeReleased,
        })}`
      ),
    previewVersion: (pageId: string, versionId: number) =>
      request<import('../types').PageVersionPreview>(
        `/api/pages/${pageId}/versions/${versionId}/preview`
      ),
    pinVersion: (pageId: string, versionId: number) =>
      request<import('../types').PageVersionPinResponse>(
        `/api/pages/${pageId}/versions/${versionId}/pin`,
        { method: 'POST' }
      ),
    unpinVersion: (pageId: string, versionId: number) =>
      request<import('../types').PageVersionPinResponse>(
        `/api/pages/${pageId}/versions/${versionId}/unpin`,
        { method: 'POST' }
      ),
    /** @deprecated PageVersion rollback is deprecated; use ProjectSnapshot rollback instead. */
    rollback: (pageId: string, versionId: number) =>
      request<{
        page_id: string
        rolled_back_to_version: number
        new_current_version_id: number
      }>(`/api/pages/${pageId}/rollback`, {
        method: 'POST',
        body: JSON.stringify({ version_id: versionId }),
      }),
  },
  snapshots: {
    getSnapshots: (
      sessionId: string,
      options?: { includeReleased?: boolean }
    ) =>
      request<import('../types').ProjectSnapshotListResponse>(
        `/api/sessions/${sessionId}/snapshots${buildQuery({
          include_released: options?.includeReleased,
        })}`
      ),
    getSnapshot: (sessionId: string, snapshotId: string) =>
      request<import('../types').ProjectSnapshot>(
        `/api/sessions/${sessionId}/snapshots/${snapshotId}`
      ),
    createSnapshot: (sessionId: string, label?: string) =>
      request<import('../types').ProjectSnapshot>(
        `/api/sessions/${sessionId}/snapshots`,
        {
          method: 'POST',
          body: JSON.stringify({ label }),
        }
      ),
    rollbackToSnapshot: (sessionId: string, snapshotId: string) =>
      request<import('../types').SnapshotRollbackResponse>(
        `/api/sessions/${sessionId}/snapshots/${snapshotId}/rollback`,
        { method: 'POST' }
      ),
    pinSnapshot: (sessionId: string, snapshotId: string) =>
      request<import('../types').SnapshotPinResponse>(
        `/api/sessions/${sessionId}/snapshots/${snapshotId}/pin`,
        { method: 'POST' }
      ),
    unpinSnapshot: (sessionId: string, snapshotId: string) =>
      request<import('../types').SnapshotPinResponse>(
        `/api/sessions/${sessionId}/snapshots/${snapshotId}/unpin`,
        { method: 'POST' }
      ),
  },
  files: {
    getTree: (sessionId: string) =>
      request<{ tree: import('../types').FileTreeNode[] }>(
        `/api/sessions/${sessionId}/files`
      ),
    getContent: (sessionId: string, path: string) =>
      request<import('../types').FileContent>(
        `/api/sessions/${sessionId}/files/${encodeURIComponent(path)}`
      ),
  },
  export: {
    session: (sessionId: string) =>
      request<{
        export_dir: string
        manifest: import('../types').ExportManifest
        success: boolean
      }>(`/api/sessions/${sessionId}/export`, { method: 'POST' }),
  },
  events: {
    getSessionEvents: (sessionId: string, sinceSeq?: number, limit?: number) =>
      request<import('../types/events').SessionEventsResponse>(
        `/api/sessions/${sessionId}/events${buildQuery({
          since_seq: sinceSeq,
          limit,
        })}`
      ),
  },
}

export { API_BASE }
