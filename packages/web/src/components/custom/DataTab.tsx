import * as React from 'react'
import { ChevronLeft, ChevronRight, RefreshCw, Database, BarChart3 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useAppData } from '@/hooks/useAppData'
import { api } from '@/api/client'

type DataViewMode = 'table' | 'dashboard'

export interface DataTabProps {
  sessionId?: string
}

const formatNumber = (value: unknown) => {
  if (typeof value === 'number' && Number.isFinite(value)) return value.toLocaleString()
  if (typeof value === 'string') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed.toLocaleString()
  }
  return '--'
}

const renderPrimitive = (value: unknown) => {
  if (value === null) return 'null'
  if (value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : 'NaN'
  if (typeof value === 'string') return value || '—'
  return String(value)
}

function JsonValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) {
    return <span className="text-muted-foreground">—</span>
  }

  if (typeof value === 'object') {
    const compact = JSON.stringify(value)
    const pretty = JSON.stringify(value, null, 2)
    if (!compact || !pretty) return <span className="text-muted-foreground">—</span>

    if (compact.length <= 80) {
      return <span className="font-mono text-xs break-all">{compact}</span>
    }

    return (
      <details className="group">
        <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
          JSON ({Array.isArray(value) ? `array:${value.length}` : `object:${Object.keys(value as Record<string, unknown>).length}`})
        </summary>
        <pre className="mt-2 max-h-40 overflow-auto rounded-md border bg-muted/20 p-2 text-[11px] leading-4">
          {pretty}
        </pre>
      </details>
    )
  }

  return <span className="break-all">{renderPrimitive(value)}</span>
}

function TablePagination({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const currentPage = Math.min(page, totalPages)
  const startPage = Math.max(1, currentPage - 2)
  const endPage = Math.min(totalPages, startPage + 4)
  const pages = []
  for (let p = startPage; p <= endPage; p += 1) {
    pages.push(p)
  }

  return (
    <div className="flex items-center justify-between gap-3 border-t border-border px-4 py-3">
      <div className="text-xs text-muted-foreground">Total {total.toLocaleString()} rows</div>
      <div className="flex items-center gap-1">
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="h-7 w-7"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
          aria-label="Previous page"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        {pages.map((p) => (
          <Button
            key={p}
            type="button"
            size="sm"
            variant={p === currentPage ? 'default' : 'ghost'}
            className="h-7 min-w-7 px-2 text-xs"
            onClick={() => onPageChange(p)}
          >
            {p}
          </Button>
        ))}
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="h-7 w-7"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
          aria-label="Next page"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex h-full min-h-[220px] items-center justify-center rounded-lg border border-dashed border-border bg-muted/10 p-6 text-center">
      <div className="max-w-sm space-y-2">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
    </div>
  )
}

function DashboardCard({ title, value, hint }: { title: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="text-xs text-muted-foreground">{title}</div>
      <div className="mt-1 text-2xl font-semibold tracking-tight">{value}</div>
      {hint ? <div className="mt-1 text-[11px] text-muted-foreground">{hint}</div> : null}
    </div>
  )
}

function BooleanDistribution({
  label,
  distribution,
}: {
  label: string
  distribution: Record<string, number>
}) {
  const total = Object.values(distribution).reduce((sum, count) => sum + count, 0)
  if (total <= 0) return null

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 text-xs font-medium text-muted-foreground">{label}</div>
      <div className="space-y-2">
        {Object.entries(distribution).map(([bucket, count]) => {
          const percentage = total > 0 ? (count / total) * 100 : 0
          return (
            <div key={`${label}-${bucket}`} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-foreground">{bucket}</span>
                <span className="text-muted-foreground">
                  {count} ({Math.round(percentage)}%)
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary/70"
                  style={{ width: `${Math.min(100, Math.max(0, percentage))}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function DataTab({ sessionId }: DataTabProps) {
  const [viewMode, setViewMode] = React.useState<DataViewMode>('table')
  const [tableCounts, setTableCounts] = React.useState<Record<string, number>>({})
  const {
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
  } = useAppData(sessionId, { pageSize: 25 })

  const currentTable = React.useMemo(
    () => tables.find((table) => table.name === activeTable) ?? null,
    [tables, activeTable]
  )

  const tableColumns = React.useMemo(() => {
    if (currentTable && currentTable.columns.length > 0) {
      return currentTable.columns.map((column) => column.name)
    }

    if (records.length === 0) return []
    const keys = new Set<string>()
    records.forEach((record) => {
      Object.keys(record).forEach((key) => keys.add(key))
    })
    return Array.from(keys)
  }, [currentTable, records])

  const numericCards = React.useMemo(() => {
    if (!stats?.numeric) return []
    return Object.entries(stats.numeric)
      .map(([name, aggregate]) => ({
        name,
        sum: aggregate.sum,
      }))
      .filter((item) => item.sum !== null)
      .slice(0, 6)
  }, [stats])

  const booleanDistributions = React.useMemo(() => {
    if (!stats?.boolean) return []
    return Object.entries(stats.boolean)
      .filter(([, distribution]) => Object.keys(distribution).length > 0)
      .slice(0, 4)
  }, [stats])

  const tableCountCards = React.useMemo(
    () =>
      tables.map((table) => {
        const isCurrent = table.name === activeTable
        const count = isCurrent
          ? stats?.count ?? pagination.total
          : tableCounts[table.name]
        return {
          name: table.name,
          count,
          isCurrent,
        }
      }),
    [activeTable, pagination.total, stats?.count, tableCounts, tables]
  )

  React.useEffect(() => {
    let active = true

    if (!sessionId || tables.length === 0) {
      setTableCounts({})
      return
    }

    const toCount = (value: unknown) => {
      if (typeof value === 'number' && Number.isFinite(value)) return value
      if (typeof value === 'string') {
        const parsed = Number(value)
        if (Number.isFinite(parsed)) return parsed
      }
      return 0
    }

    const loadAllCounts = async () => {
      const pairs = await Promise.all(
        tables.map(async (table) => {
          try {
            const tableStats = await api.data.getTableStats(sessionId, table.name)
            return [table.name, toCount(tableStats.count)] as const
          } catch {
            return [table.name, 0] as const
          }
        })
      )

      if (!active) return
      setTableCounts(Object.fromEntries(pairs))
    }

    void loadAllCounts()

    return () => {
      active = false
    }
  }, [sessionId, tables])

  const hasTables = tables.length > 0

  return (
    <div className="flex h-full flex-col" data-testid="data-tab">
      <div className="border-b border-border px-6 py-4">
        <div className="flex items-center justify-between gap-4">
          <div className="inline-flex items-center rounded-full border border-border bg-background p-0.5 text-xs font-semibold">
            <button
              type="button"
              data-testid="data-view-table"
              className={cn(
                'flex items-center gap-1.5 rounded-full px-3 py-1.5 transition',
                viewMode === 'table'
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
              onClick={() => setViewMode('table')}
            >
              <Database className="h-3.5 w-3.5" />
              Table View
            </button>
            <button
              type="button"
              data-testid="data-view-dashboard"
              className={cn(
                'flex items-center gap-1.5 rounded-full px-3 py-1.5 transition',
                viewMode === 'dashboard'
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
              onClick={() => setViewMode('dashboard')}
            >
              <BarChart3 className="h-3.5 w-3.5" />
              Dashboard View
            </button>
          </div>

          <div className="flex items-center gap-2">
            {error ? <Badge variant="destructive">{error}</Badge> : null}
            <Button
              type="button"
              data-testid="data-refresh"
              size="sm"
              variant="outline"
              onClick={refreshTable}
              disabled={isLoading || !sessionId}
              className="h-8 text-xs"
            >
              <RefreshCw className={cn('mr-1.5 h-3.5 w-3.5', isLoading ? 'animate-spin' : '')} />
              Refresh
            </Button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-4">
        {!sessionId ? (
          <EmptyState
            title="No active session"
            description="Create or open a session first to load app data."
          />
        ) : !hasTables ? (
          <EmptyState
            title={isLoading ? 'Loading data tables...' : 'No data tables yet'}
            description="Generate app data first, then this panel will show structured table records."
          />
        ) : viewMode === 'table' ? (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {tables.map((table) => (
                <Button
                  key={table.name}
                  type="button"
                  data-testid={`data-table-tab-${table.name}`}
                  size="sm"
                  variant={table.name === activeTable ? 'default' : 'outline'}
                  onClick={() => selectTable(table.name)}
                  className="h-8 text-xs"
                >
                  {table.name}
                </Button>
              ))}
            </div>

            {!activeTable ? (
              <EmptyState
                title="Select a table"
                description="Choose one table above to inspect records."
              />
            ) : (
              <div className="overflow-hidden rounded-lg border border-border bg-background">
                <div className="max-h-[52vh] overflow-auto">
                  <table className="w-full min-w-[680px] border-collapse text-sm" data-testid="data-grid">
                    <thead className="sticky top-0 z-10 bg-muted/80 backdrop-blur">
                      <tr className="border-b border-border">
                        {tableColumns.map((column) => (
                          <th
                            key={column}
                            className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                          >
                            {column}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {records.length === 0 ? (
                        <tr>
                          <td
                            colSpan={Math.max(1, tableColumns.length)}
                            className="px-3 py-8 text-center text-xs text-muted-foreground"
                          >
                            {isLoading ? 'Loading records...' : 'No records in this table.'}
                          </td>
                        </tr>
                      ) : (
                        records.map((record, index) => (
                          <tr
                            key={`${activeTable}-${pagination.page}-${index}`}
                            className="border-b border-border/60"
                            data-testid="data-grid-row"
                          >
                            {tableColumns.map((column) => (
                              <td key={`${index}-${column}`} className="max-w-[320px] px-3 py-2 align-top text-xs">
                                <JsonValue value={record[column]} />
                              </td>
                            ))}
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
                <TablePagination
                  page={pagination.page}
                  pageSize={pagination.pageSize}
                  total={pagination.total}
                  onPageChange={setPage}
                />
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <DashboardCard
                title="Current table"
                value={activeTable ?? '--'}
                hint={activeTable ? `${pagination.total.toLocaleString()} rows loaded` : 'No table selected'}
              />
              <DashboardCard
                title="Record count"
                value={formatNumber(stats?.count ?? pagination.total)}
              />
              <DashboardCard
                title="Tables"
                value={String(tables.length)}
              />
            </div>

            {tableCountCards.length > 0 ? (
              <div className="rounded-lg border border-border bg-card p-4" data-testid="data-dashboard-table-summary">
                <div className="mb-3 text-xs font-semibold uppercase text-muted-foreground">
                  Table Summary
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {tableCountCards.map((item) => (
                    <button
                      key={item.name}
                      type="button"
                      onClick={() => selectTable(item.name)}
                      className={cn(
                        'rounded-md border px-3 py-2 text-left transition',
                        item.isCurrent
                          ? 'border-primary/50 bg-primary/10'
                          : 'border-border hover:bg-muted/40'
                      )}
                    >
                      <div className="text-xs font-medium text-foreground">{item.name}</div>
                      <div className="text-[11px] text-muted-foreground">
                        {item.count === undefined ? '--' : `${item.count.toLocaleString()} rows`}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            {numericCards.length > 0 ? (
              <div className="rounded-lg border border-border bg-card p-4" data-testid="data-dashboard-numeric">
                <div className="mb-3 text-xs font-semibold uppercase text-muted-foreground">
                  Numeric Aggregates (SUM)
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {numericCards.map((item) => (
                    <DashboardCard
                      key={item.name}
                      title={item.name}
                      value={formatNumber(item.sum)}
                    />
                  ))}
                </div>
              </div>
            ) : (
              <EmptyState
                title="No numeric aggregates"
                description="Numeric stats will appear when the selected table has numeric columns."
              />
            )}

            {booleanDistributions.length > 0 ? (
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-2" data-testid="data-dashboard-boolean">
                {booleanDistributions.map(([label, distribution]) => (
                  <BooleanDistribution
                    key={label}
                    label={label}
                    distribution={distribution}
                  />
                ))}
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  )
}
