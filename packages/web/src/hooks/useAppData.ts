import * as React from 'react'
import { api } from '@/api/client'

const DEFAULT_PAGE_SIZE = 25

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value && typeof value === 'object' && !Array.isArray(value))

const toNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return null
}

const normalizePostMessagePayload = (value: unknown): Record<string, unknown> | null => {
  if (isRecord(value)) return value
  if (typeof value !== 'string') return null
  try {
    const parsed = JSON.parse(value)
    return isRecord(parsed) ? parsed : null
  } catch {
    return null
  }
}

const shouldRefreshFromMessage = (payload: Record<string, unknown>) => {
  const type = typeof payload.type === 'string' ? payload.type.toLowerCase() : ''
  const event = typeof payload.event === 'string' ? payload.event.toLowerCase() : ''
  const action = typeof payload.action === 'string' ? payload.action.toLowerCase() : ''

  return (
    type === 'data_changed' ||
    event === 'data_changed' ||
    action === 'data_changed' ||
    type === 'instant-coffee:update'
  )
}

export interface AppDataColumnInfo {
  name: string
  data_type?: string
  udt_name?: string
  nullable?: boolean
  default?: unknown
}

export interface AppDataTableInfo {
  name: string
  columns: AppDataColumnInfo[]
}

export interface AppDataTableStats {
  table?: string
  count: number
  numeric: Record<
    string,
    {
      sum: number | null
      avg: number | null
      min: number | null
      max: number | null
    }
  >
  boolean: Record<string, Record<string, number>>
}

export interface AppDataPagination {
  page: number
  pageSize: number
  total: number
}

export interface UseAppDataReturn {
  tables: AppDataTableInfo[]
  activeTable: string | null
  records: Record<string, unknown>[]
  stats: AppDataTableStats | null
  isLoading: boolean
  error: string | null
  selectTable: (name: string) => void
  refreshTable: () => void
  setPage: (page: number) => void
  pagination: AppDataPagination
}

export function useAppData(
  sessionId?: string,
  options?: {
    pageSize?: number
  }
): UseAppDataReturn {
  const pageSize = Math.max(1, options?.pageSize ?? DEFAULT_PAGE_SIZE)
  const [tables, setTables] = React.useState<AppDataTableInfo[]>([])
  const [activeTable, setActiveTable] = React.useState<string | null>(null)
  const [records, setRecords] = React.useState<Record<string, unknown>[]>([])
  const [stats, setStats] = React.useState<AppDataTableStats | null>(null)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [pagination, setPagination] = React.useState<AppDataPagination>({
    page: 1,
    pageSize,
    total: 0,
  })
  const [refreshToken, setRefreshToken] = React.useState(0)

  React.useEffect(() => {
    setPagination((prev) => {
      if (prev.pageSize === pageSize) return prev
      return { ...prev, pageSize, page: 1 }
    })
  }, [pageSize])

  const refreshTable = React.useCallback(() => {
    setRefreshToken((value) => value + 1)
  }, [])

  const selectTable = React.useCallback((name: string) => {
    setActiveTable((prev) => (prev === name ? prev : name))
    setPagination((prev) => ({ ...prev, page: 1 }))
  }, [])

  const setPage = React.useCallback((page: number) => {
    const normalized = Math.max(1, Math.floor(page))
    setPagination((prev) => (prev.page === normalized ? prev : { ...prev, page: normalized }))
  }, [])

  React.useEffect(() => {
    let active = true

    if (!sessionId) {
      setTables([])
      setActiveTable(null)
      setRecords([])
      setStats(null)
      setError(null)
      setPagination((prev) => ({ ...prev, page: 1, total: 0 }))
      return
    }

    const loadTables = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const response = await api.data.listTables(sessionId)
        if (!active) return

        const normalizedTables: AppDataTableInfo[] = Array.isArray(response.tables)
          ? response.tables
              .filter((item): item is AppDataTableInfo => {
                if (!item || typeof item !== 'object') return false
                return typeof item.name === 'string' && Array.isArray(item.columns)
              })
              .map((item) => ({
                name: item.name,
                columns: item.columns
                  .filter(
                    (column): column is AppDataColumnInfo =>
                      Boolean(column && typeof column === 'object' && typeof column.name === 'string')
                  )
                  .map((column) => ({
                    name: column.name,
                    data_type: column.data_type,
                    udt_name: column.udt_name,
                    nullable: column.nullable,
                    default: column.default,
                  })),
              }))
          : []

        setTables(normalizedTables)
        setActiveTable((prev) => {
          const fallback = normalizedTables[0]?.name ?? null
          if (!prev) return fallback
          const exists = normalizedTables.some((table) => table.name === prev)
          return exists ? prev : fallback
        })
      } catch (err) {
        if (!active) return
        const message = err instanceof Error ? err.message : 'Failed to load data tables'
        setError(message)
        setTables([])
        setActiveTable(null)
        setRecords([])
        setStats(null)
        setPagination((prev) => ({ ...prev, page: 1, total: 0 }))
      } finally {
        if (active) {
          setIsLoading(false)
        }
      }
    }

    void loadTables()

    return () => {
      active = false
    }
  }, [sessionId])

  React.useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (import.meta.env.PROD && event.origin !== window.location.origin) {
        return
      }
      const payload = normalizePostMessagePayload(event.data)
      if (!payload) return
      if (!shouldRefreshFromMessage(payload)) return
      refreshTable()
    }

    window.addEventListener('message', handleMessage)
    return () => {
      window.removeEventListener('message', handleMessage)
    }
  }, [refreshTable])

  React.useEffect(() => {
    let active = true

    if (!sessionId || !activeTable) {
      setRecords([])
      setStats(null)
      setPagination((prev) => ({ ...prev, total: 0, page: 1 }))
      return
    }

    const loadTableData = async () => {
      setIsLoading(true)
      setError(null)

      const offset = (pagination.page - 1) * pagination.pageSize

      try {
        const [queryResult, statsResult] = await Promise.allSettled([
          api.data.queryTable(sessionId, activeTable, {
            limit: pagination.pageSize,
            offset,
          }),
          api.data.getTableStats(sessionId, activeTable),
        ])

        if (!active) return

        if (queryResult.status === 'rejected') {
          throw queryResult.reason
        }

        const queryPayload = queryResult.value
        const nextRecords = Array.isArray(queryPayload.records)
          ? queryPayload.records.filter((item): item is Record<string, unknown> => isRecord(item))
          : []

        setRecords(nextRecords)

        let nextStats: AppDataTableStats | null = null
        if (statsResult.status === 'fulfilled') {
          const raw = statsResult.value
          const numeric: AppDataTableStats['numeric'] = {}
          const booleanStats: AppDataTableStats['boolean'] = {}

          if (isRecord(raw.numeric)) {
            Object.entries(raw.numeric).forEach(([key, value]) => {
              if (!isRecord(value)) return
              numeric[key] = {
                sum: toNumber(value.sum),
                avg: toNumber(value.avg),
                min: toNumber(value.min),
                max: toNumber(value.max),
              }
            })
          }

          if (isRecord(raw.boolean)) {
            Object.entries(raw.boolean).forEach(([column, value]) => {
              if (!isRecord(value)) return
              const distribution: Record<string, number> = {}
              Object.entries(value).forEach(([bucket, count]) => {
                const normalizedCount = toNumber(count)
                if (normalizedCount === null) return
                distribution[bucket] = normalizedCount
              })
              booleanStats[column] = distribution
            })
          }

          const count = toNumber(raw.count) ?? 0
          nextStats = {
            table: typeof raw.table === 'string' ? raw.table : activeTable,
            count,
            numeric,
            boolean: booleanStats,
          }
          setStats(nextStats)
        } else {
          setStats(null)
        }

        const totalFromQuery = toNumber(queryPayload.total)
        const totalFromStats = nextStats?.count ?? null
        const fallbackTotal = nextRecords.length + offset
        const nextTotal = Math.max(totalFromStats ?? 0, totalFromQuery ?? 0, fallbackTotal)

        setPagination((prev) => {
          const maxPage = Math.max(1, Math.ceil(nextTotal / prev.pageSize))
          if (prev.page > maxPage) {
            return {
              ...prev,
              total: nextTotal,
              page: maxPage,
            }
          }
          return {
            ...prev,
            total: nextTotal,
          }
        })
      } catch (err) {
        if (!active) return
        const message = err instanceof Error ? err.message : 'Failed to load table data'
        setError(message)
        setRecords([])
        setStats(null)
        setPagination((prev) => ({ ...prev, total: 0 }))
      } finally {
        if (active) setIsLoading(false)
      }
    }

    void loadTableData()

    return () => {
      active = false
    }
  }, [
    activeTable,
    pagination.page,
    pagination.pageSize,
    refreshToken,
    sessionId,
  ])

  return {
    tables,
    activeTable,
    records,
    stats,
    isLoading,
    error,
    selectTable,
    refreshTable,
    setPage,
    pagination,
  }
}

