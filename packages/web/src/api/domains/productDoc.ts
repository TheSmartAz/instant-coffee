import type {
  ProductDocHistory,
  ProductDocHistoryListResponse,
  ProductDocHistoryPinResponse,
  ProductDocHistoryResponse,
  ProductDocResponse,
} from '@/types'
import type { RequestError } from '@/api/client-core'
import { buildQuery, request } from '@/api/client-core'

export const createProductDocsApi = () => ({
  get: (sessionId: string) =>
    request<ProductDocResponse>(`/api/sessions/${sessionId}/product-doc`).catch(
      (error: RequestError) => {
        if (error.status === 404) return null
        throw error
      }
    ),
})

export const createProductDocHistoryApi = () => ({
  getProductDocHistory: (
    sessionId: string,
    options?: { includeReleased?: boolean }
  ) =>
    request<ProductDocHistoryListResponse>(
      `/api/sessions/${sessionId}/product-doc/history${buildQuery({
        include_released: options?.includeReleased,
      })}`
    ),
  getProductDocHistoryVersion: (sessionId: string, historyId: number) =>
    request<ProductDocHistoryResponse>(
      `/api/sessions/${sessionId}/product-doc/history/${historyId}`
    ),
  pinProductDocHistory: (sessionId: string, historyId: number) =>
    request<ProductDocHistoryPinResponse | ProductDocHistory>(
      `/api/sessions/${sessionId}/product-doc/history/${historyId}/pin`,
      { method: 'POST' }
    ),
  unpinProductDocHistory: (sessionId: string, historyId: number) =>
    request<ProductDocHistoryPinResponse | ProductDocHistory>(
      `/api/sessions/${sessionId}/product-doc/history/${historyId}/unpin`,
      { method: 'POST' }
    ),
})
