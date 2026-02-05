import * as React from 'react'
import { api } from '@/api/client'
import type { ProductDoc, ProductDocStatus } from '@/types'

type ApiProductDoc = {
  id?: string
  session_id?: string
  content?: string
  structured?: unknown
  version?: number
  status?: string
  created_at?: string
  updated_at?: string
}

const toDate = (value?: string) => (value ? new Date(value) : new Date())

const normalizeProductDoc = (data: unknown): ProductDoc | null => {
  if (!data || typeof data !== 'object') return null
  const doc = data as ApiProductDoc

  if (!doc.id) return null

  return {
    id: doc.id,
    sessionId: doc.session_id ?? '',
    content: doc.content ?? '',
    structured: (doc.structured as ProductDoc['structured']) ?? {
      projectName: '',
      description: '',
      targetAudience: '',
      goals: [],
      features: [],
      designDirection: {
        style: '',
        colorPreference: '',
        tone: '',
        referenceSites: [],
      },
      pages: [],
      constraints: [],
    },
    version: doc.version ?? 1,
    status: (doc.status ?? 'draft') as ProductDocStatus,
    createdAt: toDate(doc.created_at),
    updatedAt: toDate(doc.updated_at),
  }
}

export interface UseProductDocOptions {
  enabled?: boolean
  onProductDocGenerated?: (docId: string) => void
  onProductDocUpdated?: (docId: string) => void
  onProductDocConfirmed?: (docId: string) => void
  onProductDocOutdated?: (docId: string) => void
}

export interface UseProductDocReturn {
  productDoc: ProductDoc | null
  isLoading: boolean
  error: string | null
  refresh: () => Promise<void>
}

export function useProductDoc(
  sessionId?: string,
  options?: UseProductDocOptions
): UseProductDocReturn {
  const { enabled = true, onProductDocGenerated, onProductDocUpdated, onProductDocConfirmed, onProductDocOutdated } = options ?? {}

  const [productDoc, setProductDoc] = React.useState<ProductDoc | null>(null)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const refresh = React.useCallback(async () => {
    if (!sessionId || !enabled) return
    setIsLoading(true)
    setError(null)
    try {
      const response = await api.productDocs.get(sessionId)
      const normalized = normalizeProductDoc(response)
      setProductDoc(normalized)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load product doc'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [sessionId, enabled])

  React.useEffect(() => {
    let active = true
    if (!sessionId || !enabled) return

    const load = async () => {
      setIsLoading(true)
      try {
        const response = await api.productDocs.get(sessionId)
        if (!active) return
        const normalized = normalizeProductDoc(response)
        setProductDoc(normalized)
      } catch (err) {
        if (!active) return
        const message = err instanceof Error ? err.message : 'Failed to load product doc'
        setError(message)
      } finally {
        if (active) setIsLoading(false)
      }
    }

    load()

    return () => {
      active = false
    }
  }, [sessionId, enabled])

  // Handle SSE events for real-time updates
  // This expects the parent to pass in events from the chat stream
  React.useEffect(() => {
    if (!enabled) return

    const handleEvent = (event: Event) => {
      const customEvent = event as CustomEvent
      const payload = customEvent.detail
      if (!payload || typeof payload !== 'object') return

      switch (payload.type) {
        case 'product_doc_generated':
          onProductDocGenerated?.(payload.doc_id ?? '')
          refresh()
          break
        case 'product_doc_updated':
          onProductDocUpdated?.(payload.doc_id ?? '')
          refresh()
          break
        case 'product_doc_confirmed':
          onProductDocConfirmed?.(payload.doc_id ?? '')
          refresh()
          break
        case 'product_doc_outdated':
          onProductDocOutdated?.(payload.doc_id ?? '')
          refresh()
          break
      }
    }

    // Listen for custom events dispatched by the chat component
    window.addEventListener('product-doc-event', handleEvent)

    return () => {
      window.removeEventListener('product-doc-event', handleEvent)
    }
  }, [enabled, onProductDocGenerated, onProductDocUpdated, onProductDocConfirmed, onProductDocOutdated, refresh])

  return {
    productDoc,
    isLoading,
    error,
    refresh,
  }
}
