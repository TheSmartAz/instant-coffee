import * as React from 'react'
import { api, type RequestError } from '@/api/client'

export type VersionPinType = 'page' | 'snapshot' | 'product-doc'

export interface PinRequest {
  type: VersionPinType
  sessionId?: string
  pageId?: string
  id: string | number
}

export interface PinConflict {
  message?: string
  currentPinned?: Array<string | number>
}

export type PinResult =
  | { ok: true }
  | { ok: false; conflict: PinConflict }

const extractPinnedConflict = (error: RequestError): PinConflict => {
  const data = error.data as
    | { current_pinned?: Array<string | number>; message?: string }
    | { detail?: { current_pinned?: Array<string | number>; message?: string } }
    | null

  if (!data) return { message: error.message }
  if ('current_pinned' in data || 'message' in data) {
    return {
      message: data.message ?? error.message,
      currentPinned: data.current_pinned,
    }
  }
  if ('detail' in data && data.detail) {
    return {
      message: data.detail.message ?? error.message,
      currentPinned: data.detail.current_pinned,
    }
  }
  return { message: error.message }
}

export function useVersionPin() {
  const [isLoading, setIsLoading] = React.useState(false)

  const pin = React.useCallback(async (request: PinRequest): Promise<PinResult> => {
    setIsLoading(true)
    try {
      switch (request.type) {
        case 'page':
          if (!request.pageId) {
            throw new Error('Missing pageId for page version pin')
          }
          await api.pages.pinVersion(request.pageId, Number(request.id))
          break
        case 'snapshot':
          if (!request.sessionId) {
            throw new Error('Missing sessionId for snapshot pin')
          }
          await api.snapshots.pinSnapshot(request.sessionId, String(request.id))
          break
        case 'product-doc':
          if (!request.sessionId) {
            throw new Error('Missing sessionId for product doc pin')
          }
          await api.productDocHistory.pinProductDocHistory(
            request.sessionId,
            Number(request.id)
          )
          break
      }
      return { ok: true }
    } catch (err) {
      const error = err as RequestError
      if (error.status === 409) {
        const data = error.data as
          | { error?: string; current_pinned?: Array<string | number> }
          | { detail?: { error?: string; current_pinned?: Array<string | number> } }
          | { detail?: string }
          | null
        const detail =
          data && typeof data === 'object' && 'detail' in data && typeof data.detail === 'object'
            ? data.detail
            : null
        const errorCode = data && 'error' in data ? data.error : detail?.error
        const hasPinnedList =
          Boolean(data && 'current_pinned' in data && data.current_pinned) ||
          Boolean(detail && detail.current_pinned)
        if (errorCode === 'pinned_limit_exceeded' || hasPinnedList) {
          return { ok: false, conflict: extractPinnedConflict(error) }
        }
      }
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  const unpin = React.useCallback(async (request: PinRequest): Promise<void> => {
    setIsLoading(true)
    try {
      switch (request.type) {
        case 'page':
          if (!request.pageId) {
            throw new Error('Missing pageId for page version unpin')
          }
          await api.pages.unpinVersion(request.pageId, Number(request.id))
          break
        case 'snapshot':
          if (!request.sessionId) {
            throw new Error('Missing sessionId for snapshot unpin')
          }
          await api.snapshots.unpinSnapshot(request.sessionId, String(request.id))
          break
        case 'product-doc':
          if (!request.sessionId) {
            throw new Error('Missing sessionId for product doc unpin')
          }
          await api.productDocHistory.unpinProductDocHistory(
            request.sessionId,
            Number(request.id)
          )
          break
      }
    } finally {
      setIsLoading(false)
    }
  }, [])

  return {
    pin,
    unpin,
    isLoading,
  }
}
