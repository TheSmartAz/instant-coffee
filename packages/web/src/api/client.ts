import type {
  ChatRequestPayload,
  ChatResponse,
  SettingsResponse,
} from '@/types'
import { HealthSchema } from '@/api/schemas'
import {
  buildQuery,
  buildUrl,
  request,
  validatedRequest,
  API_BASE,
  classifyError,
  userFriendlyMessage,
} from '@/api/client-core'
import { createSessionsApi } from '@/api/domains/sessions'
import { createPagesApi } from '@/api/domains/pages'
import {
  createProductDocsApi,
  createProductDocHistoryApi,
} from '@/api/domains/productDoc'

export type { RequestError } from '@/api/client-core'
export { API_BASE, buildUrl, classifyError, userFriendlyMessage }

const sessionsApi = createSessionsApi()
const pagesApi = createPagesApi()
const productDocsApi = createProductDocsApi()
const productDocHistoryApi = createProductDocHistoryApi()

export const api = {
  health: () => validatedRequest(HealthSchema, '/health'),
  sessions: sessionsApi,
  data: {
    listTables: (sessionId: string) =>
      request<{
        schema?: string
        tables?: Array<{
          name: string
          columns: Array<{
            name: string
            data_type?: string
            udt_name?: string
            nullable?: boolean
            default?: unknown
          }>
        }>
      }>(`/api/sessions/${sessionId}/data/tables`),
    queryTable: (
      sessionId: string,
      table: string,
      options?: {
        limit?: number
        offset?: number
        orderBy?: string
      }
    ) =>
      request<{
        records?: Array<Record<string, unknown>>
        total?: number
        limit?: number
        offset?: number
        order_by?: { column?: string; direction?: string } | null
      }>(
        `/api/sessions/${sessionId}/data/${encodeURIComponent(table)}${buildQuery({
          limit: options?.limit,
          offset: options?.offset,
          order_by: options?.orderBy,
        })}`
      ),
    getTableStats: (sessionId: string, table: string) =>
      request<{
        table?: string
        count?: number
        numeric?: Record<
          string,
          {
            sum?: number | string | null
            avg?: number | string | null
            min?: number | string | null
            max?: number | string | null
          }
        >
        boolean?: Record<string, Record<string, number>>
      }>(`/api/sessions/${sessionId}/data/${encodeURIComponent(table)}/stats`),
  },
  chat: {
    send: (payload: ChatRequestPayload) =>
      request<ChatResponse>('/api/chat', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    streamUrl: (
      sessionId: string | undefined,
      message?: string,
      options?: { interview?: boolean; generateNow?: boolean }
    ) => {
      const params = new URLSearchParams()
      if (sessionId) {
        params.set('session_id', sessionId)
      }
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
    get: () => request<SettingsResponse>('/api/settings'),
    update: (data: Record<string, unknown>) =>
      request<SettingsResponse>('/api/settings', {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
  },
  tasks: {
    retry: (id: string) =>
      request<{ success: boolean }>(`/api/task/${id}/retry`, { method: 'POST' }),
    skip: (id: string) =>
      request<{ success: boolean }>(`/api/task/${id}/skip`, { method: 'POST' }),
  },
  productDocs: productDocsApi,
  productDocHistory: productDocHistoryApi,
  pages: pagesApi,
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
  build: {
    status: (sessionId: string) =>
      request<{
        status: string
        pages?: string[]
        dist_path?: string | null
        error?: string | null
        started_at?: string | null
        completed_at?: string | null
      }>(`/api/sessions/${sessionId}/build/status`),
    start: (sessionId: string) =>
      request<{
        status: string
        pages?: string[]
        dist_path?: string | null
        error?: string | null
        started_at?: string | null
        completed_at?: string | null
      }>(`/api/sessions/${sessionId}/build`, { method: 'POST' }),
    cancel: (sessionId: string) =>
      request<{
        status: string
        pages?: string[]
        dist_path?: string | null
        error?: string | null
        started_at?: string | null
        completed_at?: string | null
      }>(`/api/sessions/${sessionId}/build`, { method: 'DELETE' }),
    streamUrl: (sessionId: string, options?: { sinceSeq?: number }) =>
      buildUrl(
        `/api/sessions/${sessionId}/build/stream${buildQuery({
          since_seq: options?.sinceSeq,
        })}`
      ),
    previewUrl: (sessionId: string, path?: string) => {
      const cleaned = path ? path.replace(/^\/+/, '') : ''
      const suffix = cleaned ? `/${encodeURI(cleaned)}` : ''
      return buildUrl(`/preview/${sessionId}${suffix}`)
    },
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
