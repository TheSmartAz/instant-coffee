import * as React from 'react'
import { api } from '@/api/client'
import type { SessionTokenSummary } from '@/types'

export interface UseSessionCostReturn {
  data: SessionTokenSummary | undefined
  isLoading: boolean
  error: string | null
}

/**
 * Hook to fetch token usage and cost for a specific session.
 */
export function useSessionCost(sessionId: string | undefined): UseSessionCostReturn {
  const [data, setData] = React.useState<SessionTokenSummary | undefined>(undefined)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let active = true
    if (!sessionId) {
      setData(undefined)
      setError(null)
      return
    }

    const load = async () => {
      setIsLoading(true)
      try {
        const result = await api.sessions.getCost(sessionId)
        if (!active) return

        setData({
          total: {
            input_tokens: result.input_tokens,
            output_tokens: result.output_tokens,
            total_tokens: result.total_tokens,
            cost_usd: result.cost_usd,
          },
          by_agent: result.by_agent,
        })
        setError(null)
      } catch (err) {
        if (!active) return
        const message = err instanceof Error ? err.message : 'Failed to fetch session cost'
        setError(message)
      } finally {
        if (active) setIsLoading(false)
      }
    }

    load()

    // Poll every 5 seconds for live updates
    const interval = setInterval(() => {
      load()
    }, 5000)

    return () => {
      active = false
      clearInterval(interval)
    }
  }, [sessionId])

  return { data, isLoading, error }
}

export interface AllSessionsCostItem {
  session_id: string
  title: string
  updated_at: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cost_usd: number
}

export interface AllSessionsCostResponse {
  sessions: AllSessionsCostItem[]
}

export interface UseAllSessionsCostReturn {
  data: AllSessionsCostResponse | null
  isLoading: boolean
  error: string | null
}

/**
 * Hook to fetch token usage and cost across all sessions.
 */
export function useAllSessionsCost(limit: number = 50): UseAllSessionsCostReturn {
  const [data, setData] = React.useState<AllSessionsCostResponse | null>(null)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let active = true

    const load = async () => {
      setIsLoading(true)
      try {
        const result = await api.sessions.getAllCost(limit)
        if (!active) return
        setData(result)
        setError(null)
      } catch (err) {
        if (!active) return
        const message = err instanceof Error ? err.message : 'Failed to fetch all sessions cost'
        setError(message)
      } finally {
        if (active) setIsLoading(false)
      }
    }

    load()

    // Poll every 30 seconds
    const interval = setInterval(() => {
      load()
    }, 30000)

    return () => {
      active = false
      clearInterval(interval)
    }
  }, [limit])

  return { data, isLoading, error }
}
