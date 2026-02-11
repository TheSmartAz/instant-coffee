import * as React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Code, Eye, FileText, Loader2 } from 'lucide-react'
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
import { formatRelativeDate } from '@/lib/formatRelativeDate'
import { cn } from '@/lib/utils'
import { api } from '@/api/client'
import { toast } from '@/hooks/use-toast'
import { usePageVersions } from '@/hooks/usePageVersions'
import { useSnapshots } from '@/hooks/useSnapshots'
import { useProductDocHistory } from '@/hooks/useProductDocHistory'
import { useVersionPin, type VersionPinType } from '@/hooks/useVersionPin'
import { useAsyncAction } from '@/hooks/useAsyncAction'
import { PhoneFrame } from './PhoneFrame'
import { type VersionTimelineActionState } from './VersionTimeline'
import { PinnedLimitDialog, type PinnedLimitDialogItem } from './PinnedLimitDialog'
import { DiffViewDialog } from './DiffViewDialog'
import { VersionPanelHeader } from './VersionPanelHeader'
import { VersionPanelStats } from './VersionPanelStats'
import { VersionPanelContent } from './VersionPanelContent'
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
  const { runAction } = useAsyncAction()

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

  // Page diff dialog state
  const [pageDiffOpen, setPageDiffOpen] = React.useState(false)
  const [diffPageId, setDiffPageId] = React.useState<string | null>(null)
  const [diffPageTitle, setDiffPageTitle] = React.useState<string | null>(null)
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

  const collapsedCountLabel =
    panelConfig.type === 'page'
      ? `${pageVersions.length} versions`
      : panelConfig.type === 'snapshot'
        ? `${snapshots.length} snapshots`
        : `${productDocHistory.length} doc versions`

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
          meta: `Created ${formatRelativeDate(snapshot.created_at)}`,
        }
      }
      if (type === 'product-doc') {
        const history = item as ProductDocHistory
        return {
          id: history.id,
          title: `v${history.version}`,
          subtitle: history.change_summary,
          meta: `Created ${formatRelativeDate(history.created_at)}`,
        }
      }
      const version = item as PageVersion
      return {
        id: version.id,
        title: `v${version.version}`,
        subtitle: version.description ?? undefined,
        meta: `Created ${formatRelativeDate(version.createdAt)}`,
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
      await runAction(
        () =>
          pin({
            type,
            id,
            pageId: type === 'page' ? selectedPageId ?? undefined : undefined,
            sessionId: type !== 'page' ? sessionId : undefined,
          }),
        {
          onSuccess: async (result) => {
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
          },
          errorToast: (error) => ({
            title: 'Pin failed',
            description:
              error.message || 'Failed to pin version. Please try again later.',
          }),
          onFinally: () => {
            setActionState(null)
          },
        }
      )
    },
    [
      runAction,
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
      await runAction(
        () =>
          unpin({
            type,
            id,
            pageId: type === 'page' ? selectedPageId ?? undefined : undefined,
            sessionId: type !== 'page' ? sessionId : undefined,
          }),
        {
          onSuccess: async () => {
            await refreshByType(type)
          },
          successToast: { title: 'Version unpinned' },
          errorToast: (error) => ({
            title: 'Unpin failed',
            description:
              error.message || 'Failed to unpin version. Please try again later.',
          }),
          onFinally: () => {
            setActionState(null)
          },
        }
      )
    },
    [runAction, unpin, selectedPageId, sessionId, refreshByType]
  )

  const handleResolvePin = React.useCallback(
    async (releaseId: string | number) => {
      if (!pendingPin) return
      setIsResolvingPin(true)
      await runAction(
        async () => {
          await unpin({
            type: pendingPin.type,
            id: releaseId,
            pageId: pendingPin.type === 'page' ? selectedPageId ?? undefined : undefined,
            sessionId: pendingPin.type !== 'page' ? sessionId : undefined,
          })
          return pin({
            type: pendingPin.type,
            id: pendingPin.id,
            pageId: pendingPin.type === 'page' ? selectedPageId ?? undefined : undefined,
            sessionId: pendingPin.type !== 'page' ? sessionId : undefined,
          })
        },
        {
          onStart: () => {
            setActionState({ id: pendingPin.id, action: 'pin' })
          },
          onSuccess: async (result) => {
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
          },
          errorToast: (error) => ({
            title: 'Operation failed',
            description:
              error.message || 'Operation failed. Please try again later.',
          }),
          onFinally: () => {
            setIsResolvingPin(false)
            setActionState(null)
          },
        }
      )
    },
    [runAction, pendingPin, unpin, pin, selectedPageId, sessionId, refreshByType]
  )

  const handlePreviewVersion = React.useCallback(
    async (version: PageVersion) => {
      if (!selectedPageId) return
      setPreviewOpen(true)
      setIsPreviewLoading(true)
      setPreviewMeta(version)
      setPreviewHtml(null)
      setActionState({ id: version.id, action: 'view' })
      await runAction(
        () => api.pages.previewVersion(selectedPageId, version.id),
        {
          onSuccess: (preview) => {
            setPreviewHtml(preview.html ?? '')
          },
          onError: (error) => {
            if (error.status === 410) {
              toast({ title: 'This version was released and cannot be previewed' })
            }
            setPreviewOpen(false)
            resetPreview()
          },
          errorToast: (error) => {
            if (error.status === 410) {
              return null
            }
            return {
              title: 'Preview failed',
              description:
                error.message || 'Failed to load preview. Please try again later.',
            }
          },
          onFinally: () => {
            setIsPreviewLoading(false)
            setActionState(null)
          },
        }
      )
    },
    [runAction, selectedPageId, resetPreview]
  )

  const handleViewProductDoc = React.useCallback(
    async (history: ProductDocHistory) => {
      if (!sessionId) return
      setDocOpen(true)
      setIsDocLoading(true)
      setDocDetail(null)
      setActionState({ id: history.id, action: 'view' })
      await runAction(
        () => api.productDocHistory.getProductDocHistoryVersion(sessionId, history.id),
        {
          onSuccess: (detail) => {
            setDocDetail(detail)
          },
          onError: () => {
            setDocOpen(false)
            setDocDetail(null)
          },
          errorToast: (error) => ({
            title: 'Load failed',
            description:
              error.message || 'Failed to load doc version. Please try again later.',
          }),
          onFinally: () => {
            setIsDocLoading(false)
            setActionState(null)
          },
        }
      )
    },
    [runAction, sessionId]
  )

  const handleRollback = React.useCallback((snapshot: ProjectSnapshot) => {
    setRollbackTarget(snapshot)
  }, [])

  const confirmRollback = React.useCallback(async () => {
    if (!rollbackTarget || !sessionId) return
    setIsRollbacking(true)
    setActionState({ id: rollbackTarget.id, action: 'rollback' })
    await runAction(
      () => api.snapshots.rollbackToSnapshot(sessionId, rollbackTarget.id),
      {
        onSuccess: async () => {
          await Promise.all([
            refreshSnapshots(),
            refreshProductDocHistory(),
            refreshPageVersions(),
          ])
          setRollbackTarget(null)
        },
        successToast: {
          title: 'Rollback successful',
          description: `Rolled back to snapshot #${rollbackTarget.snapshot_number}`,
        },
        errorToast: (error) => ({
          title: 'Rollback failed',
          description:
            error.message || 'Rollback failed. Please try again later.',
        }),
        onFinally: () => {
          setIsRollbacking(false)
          setActionState(null)
        },
      }
    )
  }, [
    runAction,
    rollbackTarget,
    sessionId,
    refreshSnapshots,
    refreshProductDocHistory,
    refreshPageVersions,
  ])

  const handlePageDiff = React.useCallback((pageId: string, pageTitle: string) => {
    setDiffPageId(pageId)
    setDiffPageTitle(pageTitle)
    setPageDiffOpen(true)
  }, [])

  return (
    <div
      className={cn(
        'flex h-full flex-col border-l border-border bg-gradient-to-b from-muted/40 via-background to-background transition-all duration-200 ease-in-out',
        isCollapsed ? 'w-14' : 'w-80'
      )}
      style={{ flexGrow: 0, flexShrink: 0 }}
    >
      <VersionPanelHeader
        isCollapsed={isCollapsed}
        title={panelConfig.title}
        icon={panelConfig.icon}
        onToggleCollapse={onToggleCollapse}
      />

      {isCollapsed ? (
        <VersionPanelStats
          isCollapsed={isCollapsed}
          panelType={panelConfig.type}
          countLabel={collapsedCountLabel}
          icon={panelConfig.icon}
          contextLabel={contextLabel}
          contextValue={contextValue}
          subtitle={panelConfig.subtitle}
          stats={panelStats}
        />
      ) : (
        <div className="flex min-h-0 flex-1 flex-col gap-4 p-4">
          <VersionPanelStats
            isCollapsed={isCollapsed}
            panelType={panelConfig.type}
            countLabel={collapsedCountLabel}
            icon={panelConfig.icon}
            contextLabel={contextLabel}
            contextValue={contextValue}
            subtitle={panelConfig.subtitle}
            stats={panelStats}
          />

          <VersionPanelContent
            panelType={panelConfig.type}
            emptyMessage={panelConfig.emptyMessage}
            actionState={actionState}
            pageVersions={pageVersions}
            currentPageVersionId={currentPageVersionId}
            isLoadingPageVersions={isLoadingPageVersions}
            onPreviewVersion={handlePreviewVersion}
            onPageDiff={handlePageDiff}
            onPinPage={(item) => {
              void handlePin('page', item)
            }}
            onUnpinPage={(item) => {
              void handleUnpin('page', item)
            }}
            snapshots={snapshots}
            isLoadingSnapshots={isLoadingSnapshots}
            onRollback={handleRollback}
            onPinSnapshot={(item) => {
              void handlePin('snapshot', item)
            }}
            onUnpinSnapshot={(item) => {
              void handleUnpin('snapshot', item)
            }}
            productDocHistory={productDocHistory}
            isLoadingProductDocHistory={isLoadingProductDocHistory}
            onViewProductDoc={handleViewProductDoc}
            onPinProductDoc={(item) => {
              void handlePin('product-doc', item)
            }}
            onUnpinProductDoc={(item) => {
              void handleUnpin('product-doc', item)
            }}
          />
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
                ? `Created ${formatRelativeDate(docDetail.created_at)}`
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
                    {formatRelativeDate(rollbackTarget.created_at)}
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

      <DiffViewDialog
        open={pageDiffOpen}
        onOpenChange={setPageDiffOpen}
        sessionId={sessionId}
        pageId={diffPageId ?? undefined}
        pageTitle={diffPageTitle ?? undefined}
      />
    </div>
  )
}
