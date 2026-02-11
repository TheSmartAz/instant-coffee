import * as React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { FileText, Loader2, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useProductDoc } from '@/hooks/useProductDoc'
import { useProductDocDiff } from '@/hooks/useProductDocDiff'
import { MarkdownDiffViewer } from '@/components/custom/MarkdownDiffViewer'
import { VersionDiffSelector } from '@/components/custom/VersionDiffSelector'
import type { ProductDoc, ProductDocHistory, ProductDocStatus } from '@/types'

export interface ProductDocPanelProps {
  sessionId: string
  onBuild?: () => void
  buildDisabled?: boolean
  productDoc?: ProductDoc | null
  isLoading?: boolean
  error?: string | null
}

const statusLabels: Record<ProductDocStatus, string> = {
  draft: 'Pending',
  confirmed: 'Confirmed',
  outdated: 'Outdated',
}

const statusClasses: Record<ProductDocStatus, string> = {
  draft: 'bg-orange-600 text-white ring-1 ring-orange-400/60 dark:bg-orange-500 dark:text-white dark:ring-orange-300/40',
  confirmed: 'bg-emerald-700 text-white ring-1 ring-emerald-500/60 dark:bg-emerald-600 dark:text-white dark:ring-emerald-400/40',
  outdated: 'bg-black text-white ring-1 ring-black/60',
}

function StatusBadge({ status }: { status: ProductDocStatus }) {
  return (
    <span
      className={cn(
        'rounded-md px-3 py-1 text-sm font-semibold leading-none',
        statusClasses[status]
      )}
    >
      {statusLabels[status]}
    </span>
  )
}

function ProductDocSkeleton() {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-6 py-4">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-semibold text-foreground">Product Doc</span>
        </div>
        <div className="h-5 w-12 animate-pulse rounded bg-muted" />
      </div>
      <div className="flex-1 space-y-3 p-6">
        <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
        <div className="h-4 w-1/2 animate-pulse rounded bg-muted" />
        <div className="h-4 w-5/6 animate-pulse rounded bg-muted" />
        <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
      </div>
    </div>
  )
}

function ProductDocEmpty() {
  return (
    <div className="flex h-full flex-col items-center justify-center p-6 text-center">
      <FileText className="mb-4 h-12 w-12 text-muted-foreground/50" />
      <p className="text-sm text-muted-foreground">
        The product doc will be generated after you start chatting
      </p>
    </div>
  )
}

export function ProductDocPanel({
  sessionId,
  onBuild,
  buildDisabled = false,
  productDoc: productDocProp,
  isLoading: isLoadingProp,
  error: errorProp,
}: ProductDocPanelProps) {
  // Use props from parent (avoids duplicate API call) with hook fallback
  const hook = useProductDoc(sessionId, {
    enabled: productDocProp === undefined,
  })
  const productDoc = productDocProp !== undefined ? productDocProp : hook.productDoc
  const isLoading = isLoadingProp !== undefined ? isLoadingProp : hook.isLoading
  const error = errorProp !== undefined ? errorProp : hook.error
  const [diffOpen, setDiffOpen] = React.useState(false)
  const [history, setHistory] = React.useState<ProductDocHistory[]>([])
  const [historyLoading, setHistoryLoading] = React.useState(false)
  const [historyError, setHistoryError] = React.useState<string | null>(null)
  const [leftSelection, setLeftSelection] = React.useState('current')
  const [rightSelection, setRightSelection] = React.useState<string | undefined>(undefined)

  const historyIds = React.useMemo(
    () => history.map((item) => String(item.id)),
    [history]
  )

  React.useEffect(() => {
    if (!diffOpen) return
    let active = true

    const loadHistory = async () => {
      setHistoryLoading(true)
      setHistoryError(null)
      try {
        const response = await api.productDocHistory.getProductDocHistory(
          sessionId,
          { includeReleased: true }
        )
        if (!active) return
        setHistory(response.history ?? [])
      } catch (err) {
        if (!active) return
        const message =
          err instanceof Error ? err.message : 'Failed to load ProductDoc history'
        setHistoryError(message)
      } finally {
        if (active) setHistoryLoading(false)
      }
    }

    loadHistory()

    return () => {
      active = false
    }
  }, [diffOpen, sessionId])

  React.useEffect(() => {
    if (!diffOpen) return
    if (historyIds.length === 0) return

    if (!rightSelection || !historyIds.includes(rightSelection) || rightSelection === leftSelection) {
      const candidate = historyIds.find((id) => id !== leftSelection)
      setRightSelection(candidate)
    }
  }, [diffOpen, historyIds, leftSelection, rightSelection])

  React.useEffect(() => {
    if (!diffOpen) return
    if (leftSelection === 'current') return
    if (!historyIds.includes(leftSelection)) {
      setLeftSelection('current')
    }
  }, [diffOpen, historyIds, leftSelection])

  const diffReady = Boolean(leftSelection && rightSelection)
  const { leftContent, rightContent, isLoading: diffLoading, error: diffError } = useProductDocDiff(
    sessionId,
    leftSelection,
    rightSelection ?? null,
    {
      enabled: diffOpen && Boolean(productDoc),
      currentContent: productDoc?.content,
    }
  )

  if (isLoading) {
    return <ProductDocSkeleton />
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-center">
        <AlertCircle className="mb-4 h-12 w-12 text-destructive/50" />
        <p className="text-sm text-muted-foreground">Failed to load</p>
        <p className="mt-1 text-xs text-muted-foreground/70">{error}</p>
      </div>
    )
  }

  if (!productDoc) {
    return <ProductDocEmpty />
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-6 py-4">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-semibold text-foreground">Product Doc</span>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={productDoc.status} />
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setDiffOpen(true)}
          >
            Compare versions
          </Button>
        </div>
      </div>

      <Dialog open={diffOpen} onOpenChange={setDiffOpen}>
        <DialogContent className="flex h-[85vh] w-[95vw] max-w-6xl flex-col gap-4">
          <DialogHeader>
            <DialogTitle>Product Doc version comparison</DialogTitle>
            <DialogDescription>
              Select two versions to compare their Markdown content.
            </DialogDescription>
          </DialogHeader>

          <VersionDiffSelector
            versions={history}
            leftValue={leftSelection}
            rightValue={rightSelection}
            isLoading={historyLoading}
            error={historyError}
            onChange={({ left, right }) => {
              setLeftSelection(left)
              setRightSelection(right)
            }}
          />

          <div className="flex-1 overflow-hidden">
            <MarkdownDiffViewer
              leftContent={leftContent}
              rightContent={rightContent}
              isLoading={diffLoading}
              error={diffError}
              isReady={diffReady}
            />
          </div>
        </DialogContent>
      </Dialog>

      {/* Content */}
      <div className="relative flex-1 min-h-0">
        <div className="h-full overflow-y-auto px-6 pb-36 pt-6">
          <div className="markdown-content text-sm text-foreground">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
              h1: ({ children }) => (
                <h1 className="mb-4 text-2xl font-bold text-foreground">{children}</h1>
              ),
              h2: ({ children }) => (
                <h2 className="mb-3 mt-6 text-xl font-semibold text-foreground">{children}</h2>
              ),
              h3: ({ children }) => (
                <h3 className="mb-2 mt-4 text-lg font-medium text-foreground">{children}</h3>
              ),
              h4: ({ children }) => (
                <h4 className="mb-2 mt-4 text-base font-medium text-foreground">{children}</h4>
              ),
              p: ({ children }) => (
                <p className="mb-4 leading-relaxed text-foreground">{children}</p>
              ),
              ul: ({ children }) => (
                <ul className="mb-4 ml-6 list-disc space-y-2 text-foreground">{children}</ul>
              ),
              ol: ({ children }) => (
                <ol className="mb-4 ml-6 list-decimal space-y-2 text-foreground">{children}</ol>
              ),
              li: ({ children }) => (
                <li className="text-foreground">{children}</li>
              ),
              code: ({ className, children }) => {
                const isBlock = className?.includes('language-')
                if (isBlock) {
                  return (
                    <pre className="mb-4 overflow-x-auto rounded-lg bg-muted p-3 text-xs text-foreground">
                      <code>{children}</code>
                    </pre>
                  )
                }
                return (
                  <code className="rounded bg-muted px-1.5 py-0.5 text-xs text-foreground">
                    {children}
                  </code>
                )
              },
              strong: ({ children }) => (
                <strong className="font-semibold text-foreground">{children}</strong>
              ),
              blockquote: ({ children }) => (
                <blockquote className="mb-4 border-l-4 border-muted-foreground/30 pl-4 italic text-muted-foreground">
                  {children}
                </blockquote>
              ),
              a: ({ href, children }) => (
                <a
                  href={href}
                  className="text-primary underline underline-offset-4 hover:text-primary/80"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {children}
                </a>
              ),
              hr: () => <hr className="my-6 border-border" />,
              table: ({ children }) => (
                <div className="mb-4 overflow-x-auto">
                  <table className="min-w-full border border-border text-sm">{children}</table>
                </div>
              ),
              thead: ({ children }) => (
                <thead className="bg-muted">{children}</thead>
              ),
              th: ({ children }) => (
                <th className="border border-border px-4 py-2 text-left font-medium text-foreground">
                  {children}
                </th>
              ),
              td: ({ children }) => (
                <td className="border border-border px-4 py-2 text-foreground">{children}</td>
              ),
            }}
          >
            {productDoc.content}
            </ReactMarkdown>
          </div>
        </div>
        <div className="pointer-events-none absolute bottom-0 left-0 right-0">
          <div className="relative overflow-hidden">
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-white/70 to-white dark:via-white/50 dark:to-white" />
            <div className="relative flex items-center justify-center bg-transparent px-6 pb-6 pt-12">
              <div className="pointer-events-auto">
                <Button
                  type="button"
                  size="lg"
                  onClick={onBuild}
                  disabled={!onBuild || buildDisabled || isLoading}
                  className="h-11 rounded-full bg-emerald-500 px-8 text-sm font-semibold text-white shadow-lg shadow-emerald-500/30 transition hover:bg-emerald-600 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {buildDisabled ? (
                    <span className="inline-flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Building...
                    </span>
                  ) : (
                    'Start Building'
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className="flex items-center justify-center border-t border-border bg-muted/30 px-6 py-3">
        <span className="text-xs text-muted-foreground">
          Edit this document via the chat on the left
        </span>
      </div>
    </div>
  )
}
