import * as React from 'react'
import { api } from '@/api/client'

export type DiffSelectionValue = 'current' | number | string | null | undefined

export interface UseProductDocDiffOptions {
  enabled?: boolean
  currentContent?: string
}

export interface UseProductDocDiffReturn {
  leftContent: string
  rightContent: string
  isLoading: boolean
  error: string | null
  refresh: () => Promise<void>
}

type NormalizedSelection = 'current' | number | null

const normalizeSelection = (value: DiffSelectionValue): NormalizedSelection => {
  if (value === null || value === undefined || value === '') return null
  if (value === 'current') return 'current'
  const parsed = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

const resolveContent = async (
  sessionId: string,
  selection: NormalizedSelection,
  currentContent?: string
): Promise<string> => {
  if (selection === null) return ''
  if (selection === 'current') return currentContent ?? ''
  const response = await api.productDocHistory.getProductDocHistoryVersion(
    sessionId,
    selection
  )
  return response.content ?? ''
}

export function useProductDocDiff(
  sessionId: string,
  leftSelection: DiffSelectionValue,
  rightSelection: DiffSelectionValue,
  options?: UseProductDocDiffOptions
): UseProductDocDiffReturn {
  const { enabled = true, currentContent } = options ?? {}

  const [leftContent, setLeftContent] = React.useState('')
  const [rightContent, setRightContent] = React.useState('')
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const refresh = React.useCallback(async () => {
    if (!enabled || !sessionId) return

    const normalizedLeft = normalizeSelection(leftSelection)
    const normalizedRight = normalizeSelection(rightSelection)

    if (!normalizedLeft || !normalizedRight) {
      setLeftContent('')
      setRightContent('')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const [left, right] = await Promise.all([
        resolveContent(sessionId, normalizedLeft, currentContent),
        resolveContent(sessionId, normalizedRight, currentContent),
      ])

      setLeftContent(left)
      setRightContent(right)
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to load ProductDoc diff'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [enabled, sessionId, leftSelection, rightSelection, currentContent])

  React.useEffect(() => {
    refresh()
  }, [refresh])

  return {
    leftContent,
    rightContent,
    isLoading,
    error,
    refresh,
  }
}
