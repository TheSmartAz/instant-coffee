import * as React from 'react'
import { api } from '@/api/client'
import type { ProjectSnapshot } from '@/types'

export interface UseSnapshotsOptions {
  enabled?: boolean
  includeReleased?: boolean
}

export interface UseSnapshotsReturn {
  snapshots: ProjectSnapshot[]
  isLoading: boolean
  error: string | null
  refresh: () => Promise<void>
}

export function useSnapshots(
  sessionId?: string,
  options?: UseSnapshotsOptions
): UseSnapshotsReturn {
  const { enabled = true, includeReleased = false } = options ?? {}

  const [snapshots, setSnapshots] = React.useState<ProjectSnapshot[]>([])
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const refresh = React.useCallback(async () => {
    if (!sessionId || !enabled) return
    setIsLoading(true)
    setError(null)
    try {
      const response = await api.snapshots.getSnapshots(sessionId, {
        includeReleased,
      })
      const sorted = [...(response.snapshots ?? [])].sort(
        (a, b) => b.snapshot_number - a.snapshot_number
      )
      setSnapshots(sorted)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load snapshots'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [sessionId, enabled, includeReleased])

  React.useEffect(() => {
    let active = true
    if (!sessionId || !enabled) return

    const load = async () => {
      setIsLoading(true)
      try {
        const response = await api.snapshots.getSnapshots(sessionId, {
          includeReleased,
        })
        if (!active) return
        const sorted = [...(response.snapshots ?? [])].sort(
          (a, b) => b.snapshot_number - a.snapshot_number
        )
        setSnapshots(sorted)
      } catch (err) {
        if (!active) return
        const message =
          err instanceof Error ? err.message : 'Failed to load snapshots'
        setError(message)
      } finally {
        if (active) setIsLoading(false)
      }
    }

    load()

    return () => {
      active = false
    }
  }, [sessionId, enabled, includeReleased])

  return {
    snapshots,
    isLoading,
    error,
    refresh,
  }
}
