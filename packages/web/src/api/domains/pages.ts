import type { PageResponse, PageVersionListResponse, PageVersionPinResponse, PageVersionPreview } from '@/types'
import { buildQuery, buildUrl, request } from '@/api/client-core'

export const createPagesApi = () => ({
  list: (sessionId: string) =>
    request<{ pages: unknown[]; total: number }>(
      `/api/sessions/${sessionId}/pages`
    ),
  get: (pageId: string) => request<PageResponse>(`/api/pages/${pageId}`),
  previewUrl: (pageId: string) => buildUrl(`/api/pages/${pageId}/preview`),
  getPreview: (pageId: string) =>
    request<{ page_id: string; slug: string; html: string; version: number }>(
      `/api/pages/${pageId}/preview`,
      { headers: { Accept: 'application/json' } }
    ),
  getVersions: (pageId: string, includeReleased?: boolean) =>
    request<PageVersionListResponse>(
      `/api/pages/${pageId}/versions${buildQuery({
        include_released: includeReleased,
      })}`
    ),
  previewVersion: (pageId: string, versionId: number) =>
    request<PageVersionPreview>(
      `/api/pages/${pageId}/versions/${versionId}/preview`
    ),
  pinVersion: (pageId: string, versionId: number) =>
    request<PageVersionPinResponse>(
      `/api/pages/${pageId}/versions/${versionId}/pin`,
      { method: 'POST' }
    ),
  unpinVersion: (pageId: string, versionId: number) =>
    request<PageVersionPinResponse>(
      `/api/pages/${pageId}/versions/${versionId}/unpin`,
      { method: 'POST' }
    ),
  rollback: (pageId: string, versionId: number) =>
    request<{
      page_id: string
      rolled_back_to_version: number
      new_current_version_id: number
    }>(`/api/pages/${pageId}/rollback`, {
      method: 'POST',
      body: JSON.stringify({ version_id: versionId }),
    }),
})
