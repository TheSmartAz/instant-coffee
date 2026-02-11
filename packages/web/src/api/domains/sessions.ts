import { SessionListSchema } from '@/api/schemas'
import type {
  SessionMetadataResponse,
  SessionResponse,
  SessionRevertResponse,
  Thread,
} from '@/types'
import type { RequestError } from '@/api/client-core'
import { buildQuery, request, validatedRequest } from '@/api/client-core'

export const createSessionsApi = () => ({
  list: (options?: { search?: string; sort?: string; order?: string }) =>
    validatedRequest(
      SessionListSchema,
      `/api/sessions${buildQuery({
        search: options?.search,
        sort: options?.sort,
        order: options?.order,
      })}`
    ),
  get: (id: string) => request<SessionResponse>(`/api/sessions/${id}`),
  getMetadata: (id: string) => request<SessionMetadataResponse>(`/api/sessions/${id}/metadata`),
  create: (data: { title?: string }) =>
    request<SessionResponse>('/api/sessions', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  remove: (id: string) =>
    request<{ deleted: boolean }>(`/api/sessions/${id}`, { method: 'DELETE' }),
  messages: (id: string, threadId?: string) =>
    request<{ messages: unknown[] }>(
      `/api/sessions/${id}/messages${buildQuery({ thread_id: threadId })}`
    ),
  versions: (id: string, options?: { includePreviewHtml?: boolean }) =>
    request<{ versions: unknown[]; current_version?: number }>(
      `/api/sessions/${id}/versions${buildQuery({
        include_preview_html: options?.includePreviewHtml,
      })}`
    ),
  clearMessages: (id: string, threadId?: string) =>
    request<{ deleted: number }>(
      `/api/sessions/${id}/messages${buildQuery({ thread_id: threadId })}`,
      { method: 'DELETE' }
    ),
  abort: (id: string) =>
    request<{ success: boolean; plan_ids: string[]; completed_tasks: string[]; aborted_tasks: string[] }>(
      `/api/session/${id}/abort`,
      { method: 'POST' }
    ),
  revert: async (id: string, versionId: string | number) => {
    try {
      return await request<SessionRevertResponse>(
        `/api/sessions/${id}/versions/${versionId}/revert`,
        {
          method: 'POST',
        }
      )
    } catch (error) {
      const status = (error as RequestError)?.status
      if (status !== 404 && status !== 405) throw error
      return request<SessionRevertResponse>(`/api/sessions/${id}/rollback`, {
        method: 'POST',
        body: JSON.stringify({ version: Number(versionId) }),
      })
    }
  },
  threads: (id: string) =>
    request<{ threads: unknown[] }>(`/api/sessions/${id}/threads`),
  createThread: (id: string, title?: string) =>
    request<Thread>(`/api/sessions/${id}/threads`, {
      method: 'POST',
      body: JSON.stringify({ title: title ?? null }),
    }),
  deleteThread: (sessionId: string, threadId: string) =>
    request<{ deleted: boolean }>(`/api/sessions/${sessionId}/threads/${threadId}`, {
      method: 'DELETE',
    }),
  updateThread: (sessionId: string, threadId: string, data: { title?: string }) =>
    request<Thread>(`/api/sessions/${sessionId}/threads/${threadId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  getCost: (id: string) =>
    request<{
      session_id: string
      input_tokens: number
      output_tokens: number
      total_tokens: number
      cost_usd: number
      by_agent: Record<string, {
        input_tokens: number
        output_tokens: number
        total_tokens: number
        cost_usd: number
      }>
    }>(`/api/sessions/${id}/cost`),
  getAllCost: (limit?: number) =>
    request<{
      sessions: Array<{
        session_id: string
        title: string
        updated_at: string
        input_tokens: number
        output_tokens: number
        total_tokens: number
        cost_usd: number
      }>
    }>(`/api/sessions/cost${buildQuery({ limit })}`),
})
