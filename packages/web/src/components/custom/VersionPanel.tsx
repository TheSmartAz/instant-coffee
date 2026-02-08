import * as React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { formatDistanceToNow } from 'date-fns'
import { ChevronRight, ChevronLeft, Code, Eye, FileText, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import { api, type RequestError } from '@/api/client'
import { toast } from '@/hooks/use-toast'
import { usePageVersions } from '@/hooks/usePageVersions'
import { useSnapshots } from '@/hooks/useSnapshots'
import { useProductDocHistory } from '@/hooks/useProductDocHistory'
import { useVersionPin, type VersionPinType } from '@/hooks/useVersionPin'
import { PhoneFrame } from './PhoneFrame'
import { VersionTimeline, type VersionTimelineActionState } from './VersionTimeline'
import { PinnedLimitDialog, type PinnedLimitDialogItem } from './PinnedLimitDialog'
import type { PageVersion, ProductDocHistory, ProductDocHistoryResponse, ProjectSnapshot } from '@/types'

type VersionTab = 'preview' | 'code' | 'product-doc' | 'data'

interface PanelConfig {
  type: 'page' | 'snapshot' | 'product-doc'
  title: string
  subtitle: string
  icon: React.ComponentType<{ className?: string }>
  emptyMessage: string
}

export interface VersionPanelProps {
  sessionId?: string
  sessionTitle?: string | null
  selectedPageId?: string | null
  selectedPageTitle?: string | null
  activeTab: VersionTab
  isCollapsed: boolean
  onToggleCollapse: () => void
}

const toDate = (value?: string) => (value ? new Date(value) : new Date())

export function VersionPanel({
  sessionId,
  sessionTitle,
  selectedPageId,
  selectedPageTitle,
  activeTab,
  isCollapsed,
  onToggleCollapse,
}: VersionPanelProps) {
  const [actionState, setActionState] = React.useState<VersionTimelineActionState | null>(
    null
  )

  const {
    versions: pageVersions,
    currentVersionId: currentPageVersionId,
    isLoading: isLoadingPageVersions,
    refresh: refreshPageVersions,
  } = usePageVersions(selectedPageId ?? null, {
    enabled: Boolean(selectedPageId),
    includeReleased: true,
  })

  const {
    snapshots,
    isLoading: isLoadingSnapshots,
    refresh: refreshSnapshots,
  } = useSnapshots(sessionId, {
    enabled: Boolean(sessionId),
    includeReleased: true,
  })

  const {
    history: productDocHistory,
    isLoading: isLoadingProductDocHistory,
    refresh: refreshProductDocHistory,
  } = useProductDocHistory(sessionId, {
    enabled: Boolean(sessionId),
    includeReleased: true,
  })

  const { pin, unpin } = useVersionPin()

  const [previewOpen, setPreviewOpen] = React.useState(false)
  const [previewHtml, setPreviewHtml] = React.useState<string | null>(null)
  const [previewMeta, setPreviewMeta] = React.useState<PageVersion | null>(null)
  const [isPreviewLoading, setIsPreviewLoading] = React.useState(false)
  const previewContainerRef = React.useRef<HTMLDivElement | null>(null)
  const [previewScale, setPreviewScale] = React.useState(1)

  const [docOpen, setDocOpen] = React.useState(false)
  const [docDetail, setDocDetail] = React.useState<ProductDocHistoryResponse | null>(
    null
  )
  const [isDocLoading, setIsDocLoading] = React.useState(false)

  const [rollbackTarget, setRollbackTarget] = React.useState<ProjectSnapshot | null>(
    null
  )
  const [isRollbacking, setIsRollbacking] = React.useState(false)

  const [pinDialogOpen, setPinDialogOpen] = React.useState(false)
  const [pinDialogItems, setPinDialogItems] = React.useState<PinnedLimitDialogItem[]>(
    []
  )
  const [pendingPin, setPendingPin] = React.useState<{
    type: VersionPinType
    item: PinnedLimitDialogItem
    id: string | number
  } | null>(null)
  const [isResolvingPin, setIsResolvingPin] = React.useState(false)

  const panelConfig = React.useMemo<PanelConfig>(() => {
    if (activeTab === 'code') {
      return {
        type: 'snapshot',
        title: 'Code snapshots',
        subtitle: 'Versioned project snapshots',
        icon: Code,
        emptyMessage: sessionId ? 'No code snapshots yet' : 'Please create a project first',
      }
    }
    if (activeTab === 'product-doc') {
      return {
        type: 'product-doc',
        title: 'Product doc versions',
        subtitle: 'Requirements and document evolution',
        icon: FileText,
        emptyMessage: sessionId ? 'No doc history yet' : 'Please create a project first',
      }
    }
    return {
      type: 'page',
      title: 'Page versions',
      subtitle: 'History for the current page',
      icon: Eye,
      emptyMessage: selectedPageId ? 'No page history yet' : 'Select a page to view version history',
    }
  }, [activeTab, selectedPageId, sessionId])

  const pageVersionStats = React.useMemo(() => {
    let pinnedCount = 0
    let current: PageVersion | undefined
    for (const version of pageVersions) {
      if (version.isPinned) pinnedCount += 1
      if (version.id === currentPageVersionId) current = version
    }
    return { pinnedCount, current }
  }, [pageVersions, currentPageVersionId])

  const snapshotStats = React.useMemo(() => {
    let pinnedCount = 0
    for (const snapshot of snapshots) {
      if (snapshot.is_pinned) pinnedCount += 1
    }
    return { pinnedCount, latest: snapshots[0] }
  }, [snapshots])

  const productDocStats = React.useMemo(() => {
    let pinnedCount = 0
    for (const history of productDocHistory) {
      if (history.is_pinned) pinnedCount += 1
    }
    return { pinnedCount, latest: productDocHistory[0] }
  }, [productDocHistory])

  const panelStats = React.useMemo(() => {
    if (panelConfig.type === 'page') {
      return [
        { label: 'Current', value: pageVersionStats.current ? `v${pageVersionStats.current.version}` : '--' },
        { label: 'Pinned', value: String(pageVersionStats.pinnedCount) },
        { label: 'Total', value: String(pageVersions.length) },
      ]
    }
    if (panelConfig.type === 'snapshot') {
      return [
        {
          label: 'Latest',
          value: snapshotStats.latest ? `#${snapshotStats.latest.snapshot_number}` : '--',
        },
        { label: 'Pinned', value: String(snapshotStats.pinnedCount) },
        { label: 'Total', value: String(snapshots.length) },
      ]
    }
    return [
      { label: 'Latest', value: productDocStats.latest ? `v${productDocStats.latest.version}` : '--' },
      { label: 'Pinned', value: String(productDocStats.pinnedCount) },
      { label: 'Total', value: String(productDocHistory.length) },
    ]
  }, [
    panelConfig.type,
    pageVersions.length,
    snapshots.length,
    productDocHistory.length,
    pageVersionStats,
    snapshotStats,
    productDocStats,
  ])

  const contextLabel =
    panelConfig.type === 'page' ? 'Current page' : panelConfig.type === 'snapshot' ? 'Current project' : 'Current doc'
  const contextValue =
    panelConfig.type === 'page'
      ? selectedPageTitle ?? 'No page selected'
      : sessionTitle ?? (sessionId ? `Project ${sessionId.slice(0, 6)}` : 'No project yet')

  const handlePinDialogChange = React.useCallback((open: boolean) => {
    setPinDialogOpen(open)
    if (!open) {
      setPendingPin(null)
      setPinDialogItems([])
    }
  }, [])

  React.useEffect(() => {
    if (!previewContainerRef.current) return
    const updateScale = () => {
      if (!previewContainerRef.current) return
      const width = previewContainerRef.current.clientWidth
      const nextScale = Math.min(1, Math.max(0.6, width / 460))
      setPreviewScale(nextScale)
    }
    updateScale()
    const observer = new ResizeObserver(updateScale)
    observer.observe(previewContainerRef.current)
    return () => observer.disconnect()
  }, [previewOpen])

  const resetPreview = React.useCallback(() => {
    setPreviewHtml(null)
    setPreviewMeta(null)
    setIsPreviewLoading(false)
  }, [])

  const refreshByType = React.useCallback(
    async (type: VersionPinType) => {
      if (type === 'page') {
        await refreshPageVersions()
        return
      }
      if (type === 'snapshot') {
        await refreshSnapshots()
        return
      }
      await refreshProductDocHistory()
    },
    [refreshPageVersions, refreshSnapshots, refreshProductDocHistory]
  )

  const buildPinItem = React.useCallback(
    (
      type: VersionPinType,
      item: PageVersion | ProjectSnapshot | ProductDocHistory
    ): PinnedLimitDialogItem => {
      if (type === 'snapshot') {
        const snapshot = item as ProjectSnapshot
        return {
          id: snapshot.id,
          title: `Snapshot #${snapshot.snapshot_number}`,
          subtitle: snapshot.label ?? undefined,
          meta: `Created ${formatDistanceToNow(toDate(snapshot.created_at), {
            addSuffix: true,
          })}`,
        }
      }
      if (type === 'product-doc') {
        const history = item as ProductDocHistory
        return {
          id: history.id,
          title: `v${history.version}`,
          subtitle: history.change_summary,
          meta: `Created ${formatDistanceToNow(toDate(history.created_at), {
            addSuffix: true,
          })}`,
        }
      }
      const version = item as PageVersion
      return {
        id: version.id,
        title: `v${version.version}`,
        subtitle: version.description ?? undefined,
        meta: `Created ${formatDistanceToNow(version.createdAt, { addSuffix: true })}`,
      }
    },
    []
  )

  const getPinnedItems = React.useCallback(
    (type: VersionPinType) => {
      if (type === 'snapshot') {
        return snapshots.filter((snapshot) => snapshot.is_pinned)
      }
      if (type === 'product-doc') {
        return productDocHistory.filter((history) => history.is_pinned)
      }
      return pageVersions.filter((version) => version.isPinned)
    },
    [snapshots, productDocHistory, pageVersions]
  )

  const handlePin = React.useCallback(
    async (
      type: VersionPinType,
      item: PageVersion | ProjectSnapshot | ProductDocHistory
    ) => {
      const id =
        type === 'page'
          ? (item as PageVersion).id
          : (item as ProjectSnapshot | ProductDocHistory).id
      setActionState({ id, action: 'pin' })
      try {
        const result = await pin({
          type,
          id,
          pageId: type === 'page' ? selectedPageId ?? undefined : undefined,
          sessionId: type !== 'page' ? sessionId : undefined,
        })
        if (result.ok) {
          await refreshByType(type)
          toast({ title: 'Version pinned' })
          return
        }
        const pinned = getPinnedItems(type).map((pinnedItem) =>
          buildPinItem(type, pinnedItem)
        )
        setPendingPin({
          type,
          id,
          item: buildPinItem(type, item),
        })
        setPinDialogItems(pinned)
        setPinDialogOpen(true)
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to pin version. Please try again later.'
        toast({ title: 'Pin failed', description: message })
      } finally {
        setActionState(null)
      }
    },
    [
      pin,
      selectedPageId,
      sessionId,
      refreshByType,
      getPinnedItems,
      buildPinItem,
    ]
  )

  const handleUnpin = React.useCallback(
    async (
      type: VersionPinType,
      item: PageVersion | ProjectSnapshot | ProductDocHistory
    ) => {
      const id =
        type === 'page'
          ? (item as PageVersion).id
          : (item as ProjectSnapshot | ProductDocHistory).id
      setActionState({ id, action: 'unpin' })
      try {
        await unpin({
          type,
          id,
          pageId: type === 'page' ? selectedPageId ?? undefined : undefined,
          sessionId: type !== 'page' ? sessionId : undefined,
        })
        await refreshByType(type)
        toast({ title: 'Version unpinned' })
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to unpin version. Please try again later.'
        toast({ title: 'Unpin failed', description: message })
      } finally {
        setActionState(null)
      }
    },
    [unpin, selectedPageId, sessionId, refreshByType]
  )

  const handleResolvePin = React.useCallback(
    async (releaseId: string | number) => {
      if (!pendingPin) return
      setIsResolvingPin(true)
      try {
        await unpin({
          type: pendingPin.type,
          id: releaseId,
          pageId: pendingPin.type === 'page' ? selectedPageId ?? undefined : undefined,
          sessionId: pendingPin.type !== 'page' ? sessionId : undefined,
        })
        const result = await pin({
          type: pendingPin.type,
          id: pendingPin.id,
          pageId: pendingPin.type === 'page' ? selectedPageId ?? undefined : undefined,
          sessionId: pendingPin.type !== 'page' ? sessionId : undefined,
        })
        if (!result.ok) {
          toast({
            title: 'Pin failed',
            description: result.conflict.message ?? 'Failed to pin version',
          })
          return
        }
        await refreshByType(pendingPin.type)
        toast({ title: 'Pinned version updated' })
        setPinDialogOpen(false)
        setPendingPin(null)
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Operation failed. Please try again later.'
        toast({ title: 'Operation failed', description: message })
      } finally {
        setIsResolvingPin(false)
        setActionState(null)
      }
    },
    [pendingPin, unpin, pin, selectedPageId, sessionId, refreshByType]
  )

  const handlePreviewVersion = React.useCallback(
    async (version: PageVersion) => {
      if (!selectedPageId) return
      setPreviewOpen(true)
      setIsPreviewLoading(true)
      setPreviewMeta(version)
      setPreviewHtml(null)
      setActionState({ id: version.id, action: 'view' })
      try {
        const preview = await api.pages.previewVersion(selectedPageId, version.id)
        setPreviewHtml(preview.html ?? '')
      } catch (err) {
        const status = (err as RequestError)?.status
        if (status === 410) {
          toast({ title: 'This version was released and cannot be previewed' })
        } else {
          const message =
            err instanceof Error ? err.message : 'Failed to load preview. Please try again later.'
          toast({ title: 'Preview failed', description: message })
        }
        setPreviewOpen(false)
        resetPreview()
      } finally {
        setIsPreviewLoading(false)
        setActionState(null)
      }
    },
    [selectedPageId, resetPreview]
  )

  const handleViewProductDoc = React.useCallback(
    async (history: ProductDocHistory) => {
      if (!sessionId) return
      setDocOpen(true)
      setIsDocLoading(true)
      setDocDetail(null)
      setActionState({ id: history.id, action: 'view' })
      try {
        const detail = await api.productDocHistory.getProductDocHistoryVersion(
          sessionId,
          history.id
        )
        setDocDetail(detail)
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to load doc version. Please try again later.'
        toast({ title: 'Load failed', description: message })
        setDocOpen(false)
        setDocDetail(null)
      } finally {
        setIsDocLoading(false)
        setActionState(null)
      }
    },
    [sessionId]
  )

  const handleRollback = React.useCallback((snapshot: ProjectSnapshot) => {
    setRollbackTarget(snapshot)
  }, [])

  const confirmRollback = React.useCallback(async () => {
    if (!rollbackTarget || !sessionId) return
    setIsRollbacking(true)
    setActionState({ id: rollbackTarget.id, action: 'rollback' })
    try {
      await api.snapshots.rollbackToSnapshot(sessionId, rollbackTarget.id)
      toast({
        title: 'Rollback successful',
        description: `Rolled back to snapshot #${rollbackTarget.snapshot_number}`,
      })
      await Promise.all([
        refreshSnapshots(),
        refreshProductDocHistory(),
        refreshPageVersions(),
      ])
      setRollbackTarget(null)
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Rollback failed. Please try again later.'
      toast({ title: 'Rollback failed', description: message })
    } finally {
      setIsRollbacking(false)
      setActionState(null)
    }
  }, [
    rollbackTarget,
    sessionId,
    refreshSnapshots,
    refreshProductDocHistory,
    refreshPageVersions,
  ])

  return (
    <div
      className={cn(
        'flex h-full flex-col border-l border-border bg-gradient-to-b from-muted/40 via-background to-background transition-all duration-200 ease-in-out',
        isCollapsed ? 'w-14' : 'w-80'
      )}
      style={{ flexGrow: 0, flexShrink: 0 }}
    >
      <div
        className={cn(
          'flex h-14 items-center border-b border-border',
          isCollapsed ? 'justify-center px-2' : 'justify-between px-4'
        )}
      >
        {!isCollapsed ? (
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-muted/60 text-foreground">
              <panelConfig.icon className="h-4 w-4" />
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
                Version management
              </div>
              <div className="text-sm font-semibold text-foreground">
                {panelConfig.title}
              </div>
            </div>
          </div>
        ) : null}
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggleCollapse}
          aria-label={isCollapsed ? 'Expand versions panel' : 'Collapse versions panel'}
        >
          {isCollapsed ? (
            <ChevronLeft className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </Button>
      </div>

      {isCollapsed ? (
        <div className="flex flex-1 flex-col items-center justify-between py-4">
          <div className="flex flex-col items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-muted/60 text-foreground">
              <panelConfig.icon className="h-5 w-5" />
            </div>
            <div className="flex flex-col items-center gap-1 text-[10px] text-muted-foreground">
              <span className="uppercase tracking-[0.2em]">Focus</span>
              <span className="rounded-full bg-muted px-2 py-0.5 text-foreground">
                {panelConfig.type === 'page'
                  ? `${pageVersions.length} versions`
                  : panelConfig.type === 'snapshot'
                    ? `${snapshots.length} snapshots`
                    : `${productDocHistory.length} doc versions`}
              </span>
            </div>
          </div>
          <div className="text-[10px] text-muted-foreground">Versions</div>
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col gap-4 p-4">
          <div className="rounded-2xl border border-border/70 bg-background/80 p-4 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <panelConfig.icon className="h-3.5 w-3.5" />
                  <span>{contextLabel}</span>
                </div>
                <div className="text-sm font-semibold text-foreground truncate">
                  {contextValue}
                </div>
                <div className="text-xs text-muted-foreground">{panelConfig.subtitle}</div>
              </div>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2">
              {panelStats.map((stat) => (
                <div
                  key={stat.label}
                  className="rounded-xl border border-border/60 bg-muted/40 px-2 py-2 text-center"
                >
                  <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
                    {stat.label}
                  </div>
                  <div className="text-sm font-semibold text-foreground">{stat.value}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex min-h-0 flex-1">
            {panelConfig.type === 'page' ? (
              <VersionTimeline
                type="page"
                versions={pageVersions}
                currentId={currentPageVersionId ?? null}
                isLoading={isLoadingPageVersions}
                actions={['view', 'pin']}
                actionState={actionState}
                emptyMessage={panelConfig.emptyMessage}
                onView={(item) => handlePreviewVersion(item as PageVersion)}
                onPin={(item) => handlePin('page', item as PageVersion)}
                onUnpin={(item) => handleUnpin('page', item as PageVersion)}
              />
            ) : null}

            {panelConfig.type === 'snapshot' ? (
              <VersionTimeline
                type="snapshot"
                versions={snapshots}
                isLoading={isLoadingSnapshots}
                actions={['rollback', 'pin']}
                actionState={actionState}
                emptyMessage={panelConfig.emptyMessage}
                onRollback={(item) => handleRollback(item as ProjectSnapshot)}
                onPin={(item) => handlePin('snapshot', item as ProjectSnapshot)}
                onUnpin={(item) => handleUnpin('snapshot', item as ProjectSnapshot)}
              />
            ) : null}

            {panelConfig.type === 'product-doc' ? (
              <VersionTimeline
                type="product-doc"
                versions={productDocHistory}
                isLoading={isLoadingProductDocHistory}
                actions={['view', 'diff', 'pin']}
                actionState={actionState}
                emptyMessage={panelConfig.emptyMessage}
                onView={(item) => handleViewProductDoc(item as ProductDocHistory)}
                onDiff={() => {
                  toast({
                    title: 'Feature in progress',
                    description: 'Product doc comparison will ship in v05-F2',
                  })
                }}
                onPin={(item) => handlePin('product-doc', item as ProductDocHistory)}
                onUnpin={(item) => handleUnpin('product-doc', item as ProductDocHistory)}
              />
            ) : null}
          </div>
        </div>
      )}

      <PinnedLimitDialog
        open={pinDialogOpen}
        onOpenChange={handlePinDialogChange}
        pendingItem={pendingPin?.item ?? null}
        pinnedItems={pinDialogItems}
        onConfirm={handleResolvePin}
        isSubmitting={isResolvingPin}
      />

      <Dialog
        open={previewOpen}
        onOpenChange={(open) => {
          setPreviewOpen(open)
          if (!open) resetPreview()
        }}
      >
        <DialogContent className="max-w-5xl w-[92vw] h-[80vh]">
          <DialogHeader>
            <DialogTitle>
              {previewMeta ? `Page version v${previewMeta.version}` : 'Page preview'}
            </DialogTitle>
            <DialogDescription>
              {previewMeta?.description
                ? previewMeta.description
                : 'For viewing history only; it will not affect the current page'}
            </DialogDescription>
          </DialogHeader>

          <div
            ref={previewContainerRef}
            className="flex flex-1 items-center justify-center rounded-lg bg-muted/30 p-4"
          >
            {isPreviewLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading preview...
              </div>
            ) : (
              <PhoneFrame scale={previewScale}>
                <iframe
                  title="Version preview"
                  className="h-full w-full border-0 bg-background"
                  srcDoc={previewHtml ?? ''}
                />
              </PhoneFrame>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={docOpen}
        onOpenChange={(open) => {
          setDocOpen(open)
          if (!open) {
            setDocDetail(null)
            setIsDocLoading(false)
          }
        }}
      >
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>
              {docDetail ? `Doc version v${docDetail.version}` : 'Doc version'}
            </DialogTitle>
            <DialogDescription>
              {docDetail
                ? `Created ${formatDistanceToNow(toDate(docDetail.created_at), {
                    addSuffix: true,
                  })}`
                : 'View historical product doc content'}
            </DialogDescription>
          </DialogHeader>

          <ScrollArea className="max-h-[60vh] pr-4">
            {isDocLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading content...
              </div>
            ) : docDetail ? (
              <div className="markdown-content text-sm text-foreground">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {docDetail.content}
                </ReactMarkdown>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">No content</div>
            )}
          </ScrollArea>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={Boolean(rollbackTarget)}
        onOpenChange={(open) => {
          if (!open) setRollbackTarget(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm rollback to snapshot?</AlertDialogTitle>
            <AlertDialogDescription>
              {rollbackTarget ? (
                <div className="space-y-2 text-sm text-muted-foreground">
                  <div>
                    Will roll back to snapshot #{rollbackTarget.snapshot_number}
                    {rollbackTarget.label ? ` · ${rollbackTarget.label}` : ''}
                  </div>
                  <div>
                    Created{' '}
                    {formatDistanceToNow(toDate(rollbackTarget.created_at), {
                      addSuffix: true,
                    })}
                    , includes {rollbackTarget.page_count} pages
                  </div>
                </div>
              ) : null}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isRollbacking}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmRollback} disabled={isRollbacking}>
              {isRollbacking ? 'Rolling back...' : 'Confirm rollback'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
