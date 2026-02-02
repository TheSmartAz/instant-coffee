import * as React from 'react'
import { diffLines } from 'diff'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type LineType = 'context' | 'added' | 'removed' | 'empty'
export type DiffViewMode = 'side-by-side' | 'unified'

export interface MarkdownDiffViewerProps {
  leftContent: string
  rightContent: string
  isLoading?: boolean
  error?: string | null
  isReady?: boolean
}

interface SideBySideRow {
  left: string
  right: string
  leftType: LineType
  rightType: LineType
}

interface UnifiedRow {
  value: string
  type: LineType
}

const STORAGE_KEY = 'instant-coffee:product-doc-diff-view'

const splitLines = (value: string) => {
  if (value === '') return ['']
  const lines = value.split('\n')
  if (lines.length > 1 && lines[lines.length - 1] === '') {
    lines.pop()
  }
  return lines
}

const lineClasses: Record<LineType, string> = {
  context: 'text-foreground',
  added:
    'bg-emerald-50 text-emerald-900 dark:bg-emerald-900/20 dark:text-emerald-200',
  removed:
    'bg-rose-50 text-rose-900 dark:bg-rose-900/20 dark:text-rose-200',
  empty: 'bg-muted/30 text-muted-foreground/60',
}

const buildSideBySideRows = (changes: ReturnType<typeof diffLines>): SideBySideRow[] => {
  const rows: SideBySideRow[] = []

  for (let index = 0; index < changes.length; index += 1) {
    const change = changes[index]

    if (change.removed && changes[index + 1]?.added) {
      const removedLines = splitLines(change.value)
      const addedLines = splitLines(changes[index + 1].value)
      const max = Math.max(removedLines.length, addedLines.length)

      for (let lineIndex = 0; lineIndex < max; lineIndex += 1) {
        rows.push({
          left: removedLines[lineIndex] ?? '',
          right: addedLines[lineIndex] ?? '',
          leftType: 'removed',
          rightType: 'added',
        })
      }

      index += 1
      continue
    }

    const lines = splitLines(change.value)

    if (change.added) {
      lines.forEach((line) => {
        rows.push({
          left: '',
          right: line,
          leftType: 'empty',
          rightType: 'added',
        })
      })
      continue
    }

    if (change.removed) {
      lines.forEach((line) => {
        rows.push({
          left: line,
          right: '',
          leftType: 'removed',
          rightType: 'empty',
        })
      })
      continue
    }

    lines.forEach((line) => {
      rows.push({
        left: line,
        right: line,
        leftType: 'context',
        rightType: 'context',
      })
    })
  }

  return rows
}

const buildUnifiedRows = (changes: ReturnType<typeof diffLines>): UnifiedRow[] => {
  const rows: UnifiedRow[] = []

  changes.forEach((change) => {
    const lines = splitLines(change.value)
    const type: LineType = change.added
      ? 'added'
      : change.removed
      ? 'removed'
      : 'context'

    lines.forEach((line) => {
      rows.push({
        value: line,
        type,
      })
    })
  })

  return rows
}

const getPrefix = (type: LineType) => {
  if (type === 'added') return '+'
  if (type === 'removed') return '-'
  return ' '
}

export function MarkdownDiffViewer({
  leftContent,
  rightContent,
  isLoading = false,
  error,
  isReady = true,
}: MarkdownDiffViewerProps) {
  const [viewMode, setViewMode] = React.useState<DiffViewMode>('side-by-side')

  React.useEffect(() => {
    if (typeof window === 'undefined') return
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored === 'side-by-side' || stored === 'unified') {
      setViewMode(stored)
    }
  }, [])

  React.useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(STORAGE_KEY, viewMode)
  }, [viewMode])

  const diffChanges = React.useMemo(
    () => diffLines(leftContent ?? '', rightContent ?? ''),
    [leftContent, rightContent]
  )

  const sideBySideRows = React.useMemo(
    () => buildSideBySideRows(diffChanges),
    [diffChanges]
  )

  const unifiedRows = React.useMemo(
    () => buildUnifiedRows(diffChanges),
    [diffChanges]
  )

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center rounded-md border border-border">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Generating comparison...
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center rounded-md border border-border">
        <div className="text-sm text-destructive">{error}</div>
      </div>
    )
  }

  if (!isReady) {
    return (
      <div className="flex h-full items-center justify-center rounded-md border border-border">
        <div className="text-sm text-muted-foreground">
          Select two versions to start the comparison.
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            Added
          </div>
          <div className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-rose-400" />
            Removed
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant={viewMode === 'side-by-side' ? 'secondary' : 'outline'}
            onClick={() => setViewMode('side-by-side')}
          >
            Side by side
          </Button>
          <Button
            type="button"
            size="sm"
            variant={viewMode === 'unified' ? 'secondary' : 'outline'}
            onClick={() => setViewMode('unified')}
          >
            Unified
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-auto rounded-md border border-border">
        {viewMode === 'side-by-side' ? (
          <div className="min-w-[640px] text-xs">
            <div className="grid grid-cols-1 border-b border-border bg-muted/40 text-[11px] font-medium text-muted-foreground md:grid-cols-2">
              <div className="px-3 py-2">Left content</div>
              <div className="px-3 py-2">Right content</div>
            </div>
            {sideBySideRows.map((row, index) => (
              <div
                key={`side-${index}`}
                className="grid grid-cols-1 border-b border-border/60 md:grid-cols-2"
              >
                <div
                  className={cn(
                    'px-3 py-1.5 font-mono whitespace-pre-wrap break-words',
                    lineClasses[row.leftType]
                  )}
                >
                  {row.left}
                </div>
                <div
                  className={cn(
                    'px-3 py-1.5 font-mono whitespace-pre-wrap break-words',
                    lineClasses[row.rightType]
                  )}
                >
                  {row.right}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs">
            {unifiedRows.map((row, index) => (
              <div
                key={`unified-${index}`}
                className={cn(
                  'flex border-b border-border/60 px-3 py-1.5 font-mono whitespace-pre-wrap break-words',
                  lineClasses[row.type]
                )}
              >
                <span className="mr-3 w-3 text-muted-foreground">
                  {getPrefix(row.type)}
                </span>
                <span className="flex-1">{row.value}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
