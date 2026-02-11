import * as React from 'react'
import { Loader2, FileText, ChevronDown, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { MarkdownDiffViewer } from '@/components/custom/MarkdownDiffViewer'
import { usePageDiff, usePageVersionsForDiff } from '@/hooks/usePageDiff'
import type { DiffViewMode } from '@/components/custom/MarkdownDiffViewer'

interface PageDiffViewerProps {
  sessionId: string | undefined
  pageId: string | undefined
  pageTitle?: string
  onClose?: () => void
  className?: string
}

export function PageDiffViewer({
  sessionId,
  pageId,
  pageTitle,
  onClose,
  className,
}: PageDiffViewerProps) {
  const [viewMode, setViewMode] = React.useState<DiffViewMode>('unified')
  const [versionA, setVersionA] = React.useState<number | null>(null)
  const [versionB, setVersionB] = React.useState<number | null>(null)
  const [showDiff, setShowDiff] = React.useState(false)

  // Fetch versions
  const { data: versionsData, isLoading: versionsLoading } = usePageVersionsForDiff(sessionId, pageId)
  const versions = React.useMemo(() => versionsData?.versions ?? [], [versionsData?.versions])

  // Fetch diff
  const {
    data: diffData,
    isLoading: diffLoading,
    refresh: refreshDiff,
  } = usePageDiff(sessionId, pageId, versionA, versionB)

  // Auto-select latest two versions when page is first loaded
  React.useEffect(() => {
    if (versions.length >= 2 && !versionA && !versionB) {
      // versionB is newest (index 0), versionA is previous (index 1)
      setVersionB(versions[0].version)
      setVersionA(versions[1].version)
      setShowDiff(true)
    }
  }, [versions, versionA, versionB])

  const handleRefreshDiff = () => {
    refreshDiff()
  }

  return (
    <div className={className}>
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-semibold">
            {pageTitle || 'Page'} Diff
          </span>
        </div>
        {onClose && (
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close diff viewer">
            ×
          </Button>
        )}
      </div>

      {/* Version selectors */}
      <div className="border-b border-border px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Compare</span>
            <Select
              value={versionA?.toString() || ""}
              onValueChange={(v) => setVersionA(parseInt(v))}
            >
              <SelectTrigger className="w-[140px] h-8">
                <SelectValue placeholder="Older version" />
              </SelectTrigger>
              <SelectContent>
                {versions.map((v: { id: string; version: number; description: string | null }) => (
                  <SelectItem key={v.id} value={v.version.toString()}>
                    v{v.version} {v.description && `- ${v.description}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <span className="text-muted-foreground">→</span>

            <Select
              value={versionB?.toString() || ""}
              onValueChange={(v) => setVersionB(parseInt(v))}
            >
              <SelectTrigger className="w-[140px] h-8">
                <SelectValue placeholder="Newer version" />
              </SelectTrigger>
              <SelectContent>
                {versions.map((v: { id: string; version: number; description: string | null }) => (
                  <SelectItem key={v.id} value={v.version.toString()}>
                    v{v.version} {v.description && `- ${v.description}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Button
              variant="outline"
              size="sm"
              className="h-8"
              onClick={() => setShowDiff(!showDiff)}
            >
              {showDiff ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            </Button>

            <Button
              variant="outline"
              size="sm"
              className="h-8"
              onClick={handleRefreshDiff}
              disabled={!versionA || !versionB}
            >
              {diffLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Refresh'}
            </Button>
          </div>

          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            {diffData?.stats && (
              <>
                <span>{diffData.stats.old_lines} lines</span>
                <span>→</span>
                <span>{diffData.stats.new_lines} lines</span>
              </>
            )}
          </div>
        </div>

        {/* View mode toggle */}
        {showDiff && (
          <div className="flex items-center gap-1 text-xs">
            <button
              className={`px-2 py-1 rounded ${
                viewMode === 'unified'
                  ? 'bg-accent text-accent-foreground'
                  : 'hover:bg-muted'
              }`}
              onClick={() => setViewMode('unified')}
            >
              Unified
            </button>
            <button
              className={`px-2 py-1 rounded ${
                viewMode === 'side-by-side'
                  ? 'bg-accent text-accent-foreground'
                  : 'hover:bg-muted'
              }`}
              onClick={() => setViewMode('side-by-side')}
            >
              Side by Side
            </button>
          </div>
        )}
      </div>

      {/* Content */}
      {versionsLoading ? (
        <div className="flex items-center justify-center p-8">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : versions.length === 0 ? (
        <div className="p-8 text-center text-sm text-muted-foreground">
          No versions available for this page yet.
        </div>
      ) : (
        <ScrollArea className="h-[400px]">
          {!showDiff ? (
            <div className="p-4 text-sm text-muted-foreground">
              Select two versions to compare the changes.
            </div>
          ) : (
            <MarkdownDiffViewer
              leftContent={diffData?.old_content || ''}
              rightContent={diffData?.new_content || ''}
              isLoading={diffLoading}
              error={!diffData && !diffLoading ? 'Failed to load diff' : null}
              isReady={!!diffData}
            />
          )}
        </ScrollArea>
      )}
    </div>
  )
}
