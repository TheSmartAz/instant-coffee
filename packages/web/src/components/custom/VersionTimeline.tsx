import * as React from 'react'
import { Eye, Loader2, Pin, PinOff, RotateCcw } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { formatRelativeDate } from '@/lib/formatRelativeDate'
import { cn } from '@/lib/utils'
import type { PageVersion, ProductDocHistory, ProjectSnapshot, VersionSource } from '@/types'

export type VersionTimelineType = 'page' | 'snapshot' | 'product-doc'
export type VersionTimelineAction = 'view' | 'diff' | 'rollback' | 'pin'

export interface VersionTimelineActionState {
  id: string | number
  action: 'view' | 'diff' | 'rollback' | 'pin' | 'unpin'
}

export interface VersionTimelineProps {
  type: VersionTimelineType
  versions: Array<PageVersion | ProjectSnapshot | ProductDocHistory>
  currentId?: string | number | null
  actions?: VersionTimelineAction[]
  isLoading?: boolean
  emptyMessage?: string
  actionState?: VersionTimelineActionState | null
  onView?: (item: PageVersion | ProductDocHistory) => void
  onDiff?: (item: ProductDocHistory | PageVersion) => void
  onRollback?: (item: ProjectSnapshot) => void
  onPin?: (item: PageVersion | ProjectSnapshot | ProductDocHistory) => void
  onUnpin?: (item: PageVersion | ProjectSnapshot | ProductDocHistory) => void
  onPageDiff?: (pageId: string, pageTitle: string) => void  // New: for page diff
}

const sourceLabels: Record<VersionSource, string> = {
  auto: 'Automatic',
  manual: 'Manual',
  rollback: 'Rollback',
}

const toDate = (value?: string) => (value ? new Date(value) : new Date())

const getIsPinned = (
  type: VersionTimelineType,
  item: PageVersion | ProjectSnapshot | ProductDocHistory
) => {
  if (type === 'page') return Boolean((item as PageVersion).isPinned)
  return Boolean((item as ProjectSnapshot | ProductDocHistory).is_pinned)
}

const getIsReleased = (
  type: VersionTimelineType,
  item: PageVersion | ProjectSnapshot | ProductDocHistory
) => {
  if (type === 'page') return Boolean((item as PageVersion).isReleased)
  return Boolean((item as ProjectSnapshot | ProductDocHistory).is_released)
}

const getAvailable = (
  type: VersionTimelineType,
  item: PageVersion | ProjectSnapshot | ProductDocHistory
) => {
  if (type === 'page') return (item as PageVersion).available !== false
  return (item as ProjectSnapshot | ProductDocHistory).available !== false
}

const getSource = (
  type: VersionTimelineType,
  item: PageVersion | ProjectSnapshot | ProductDocHistory
) => {
  if (type === 'page') return (item as PageVersion).source
  return (item as ProjectSnapshot | ProductDocHistory).source
}

const getCreatedAt = (
  type: VersionTimelineType,
  item: PageVersion | ProjectSnapshot | ProductDocHistory
) => {
  if (type === 'page') return (item as PageVersion).createdAt
  return toDate((item as ProjectSnapshot | ProductDocHistory).created_at)
}

const getTitle = (
  type: VersionTimelineType,
  item: PageVersion | ProjectSnapshot | ProductDocHistory
) => {
  if (type === 'snapshot') {
    return `Snapshot #${(item as ProjectSnapshot).snapshot_number}`
  }
  const versionNumber =
    type === 'page'
      ? (item as PageVersion).version
      : (item as ProductDocHistory).version
  return `v${versionNumber}`
}

const getDescription = (
  type: VersionTimelineType,
  item: PageVersion | ProjectSnapshot | ProductDocHistory
) => {
  if (type === 'page') return (item as PageVersion).description
  if (type === 'snapshot') return (item as ProjectSnapshot).label
  return (item as ProductDocHistory).change_summary
}

const getMeta = (
  type: VersionTimelineType,
  item: PageVersion | ProjectSnapshot | ProductDocHistory
) => {
  if (type !== 'snapshot') return null
  const count = (item as ProjectSnapshot).page_count
  return typeof count === 'number' ? `Includes ${count} pages` : null
}

const getId = (
  type: VersionTimelineType,
  item: PageVersion | ProjectSnapshot | ProductDocHistory
) => {
  if (type === 'page') return (item as PageVersion).id
  return (item as ProjectSnapshot | ProductDocHistory).id
}

const getPreviewable = (item: PageVersion | ProjectSnapshot | ProductDocHistory) =>
  (item as PageVersion).previewable

export const VersionTimeline = React.memo(function VersionTimeline({
  type,
  versions,
  currentId,
  actions = [],
  isLoading = false,
  emptyMessage,
  actionState = null,
  onView,
  onDiff,
  onRollback,
  onPin,
  onUnpin,
  onPageDiff,
}: VersionTimelineProps) {
  const { pinnedItems, regularItems } = React.useMemo(() => {
    const pinned: Array<PageVersion | ProjectSnapshot | ProductDocHistory> = []
    const regular: Array<PageVersion | ProjectSnapshot | ProductDocHistory> = []
    for (const item of versions) {
      if (getIsPinned(type, item)) {
        pinned.push(item)
      } else {
        regular.push(item)
      }
    }
    return { pinnedItems: pinned, regularItems: regular }
  }, [type, versions])

  const groups = React.useMemo(
    () =>
      [
        { id: 'pinned', label: 'Pinned versions', items: pinnedItems },
        { id: 'regular', label: 'Version history', items: regularItems },
      ].filter((group) => group.items.length > 0),
    [pinnedItems, regularItems]
  )

  const actionButtonClass =
    'h-7 rounded-full px-3 text-xs font-medium transition-colors'

  return (
    <ScrollArea className="h-full pr-2">
      <div className="space-y-6 pb-4">
        {isLoading && versions.length === 0
          ? Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="rounded-2xl border border-border/60 bg-muted/20 p-4">
                <div className="flex items-start gap-3">
                  <Skeleton className="h-10 w-10 rounded-xl" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-28" />
                    <Skeleton className="h-3 w-40" />
                    <Skeleton className="h-3 w-24" />
                  </div>
                </div>
                <div className="mt-3 flex gap-2">
                  <Skeleton className="h-7 w-16 rounded-full" />
                  <Skeleton className="h-7 w-16 rounded-full" />
                </div>
              </div>
            ))
          : null}

        {groups.map((group) => (
          <div key={group.id} className="space-y-3">
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
              <span>{group.label}</span>
              <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-foreground">
                {group.items.length}
              </span>
            </div>

            <div className="relative pl-6">
              <div className="absolute left-[11px] top-0 h-full w-px bg-border/60" />
              {group.items.map((item, index) => {
                const id = getId(type, item)
                const isCurrent = currentId !== undefined && currentId === id
                const isPinned = getIsPinned(type, item)
                const isReleased = getIsReleased(type, item)
                const isAvailable = getAvailable(type, item)
                const source = getSource(type, item)
                const createdAt = getCreatedAt(type, item)
                const title = getTitle(type, item)
                const description = getDescription(type, item)
                const meta = getMeta(type, item)
                const previewable = type === 'page' ? getPreviewable(item) !== false : true
                const isUnavailable = isReleased || !isAvailable
                const showPinAction = actions.includes('pin')
                const showViewAction = actions.includes('view')
                const showDiffAction = actions.includes('diff')
                const showRollbackAction = actions.includes('rollback')

                return (
                  <div
                    key={id}
                    className={cn(
                      'group relative flex gap-4 py-3',
                      'border-b border-border/50 last:border-b-0',
                      'hover:bg-muted/30',
                      isUnavailable && 'opacity-60'
                    )}
                  >
                    <div className="relative">
                      <div
                        className={cn(
                          'mt-1 h-3 w-3 rounded-full border-2 border-border bg-background',
                          isCurrent &&
                            'h-4 w-4 border-primary bg-primary shadow-[0_0_0_4px_rgba(59,130,246,0.12)]',
                          isPinned && 'border-amber-400'
                        )}
                        style={isCurrent ? { transform: 'translate(-2px, -2px)' } : undefined}
                      />
                      {index === group.items.length - 1 ? (
                        <div className="absolute left-1/2 top-4 h-3 w-px -translate-x-1/2 bg-background" />
                      ) : null}
                    </div>

                    <div className="flex-1">
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <div className="text-sm font-semibold text-foreground">{title}</div>
                            {isCurrent ? (
                              <Badge className="text-[10px]">Current</Badge>
                            ) : null}
                            {isPinned ? (
                              <Badge className="bg-amber-100 text-[10px] text-amber-900">
                                Pinned
                              </Badge>
                            ) : null}
                            {isReleased ? (
                              <Badge
                                variant="outline"
                                className="text-[10px] text-muted-foreground"
                              >
                                {isAvailable ? 'Released' : 'Unavailable'}
                              </Badge>
                            ) : null}
                            {source ? (
                              <Badge variant="secondary" className="text-[10px]">
                                {sourceLabels[source] ?? source}
                              </Badge>
                            ) : null}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {formatRelativeDate(createdAt)}
                          </div>
                        </div>
                        <div className="text-[10px] text-muted-foreground">
                          {type === 'snapshot'
                            ? `#${(item as ProjectSnapshot).snapshot_number}`
                            : title}
                        </div>
                      </div>

                      {description ? (
                        <div className="mt-2 text-xs text-muted-foreground line-clamp-2">
                          {description}
                        </div>
                      ) : null}
                      {meta ? (
                        <div className="mt-2 text-xs text-muted-foreground/80">{meta}</div>
                      ) : null}

                      <div className="mt-3 flex flex-wrap gap-2">
                        {showViewAction ? (
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            className={actionButtonClass}
                            onClick={() => onView?.(item as PageVersion | ProductDocHistory)}
                            disabled={isUnavailable || (type === 'page' && !previewable)}
                            aria-label={`View ${title}`}
                          >
                            {actionState?.id === id && actionState.action === 'view' ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <span className="inline-flex items-center gap-1">
                                <Eye className="h-3.5 w-3.5" />
                                View
                              </span>
                            )}
                          </Button>
                        ) : null}

                        {showDiffAction ? (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className={actionButtonClass}
                            onClick={() => {
                              if (type === 'page') {
                                // Page diff - use onPageDiff callback
                                onPageDiff?.(
                                  (item as PageVersion).pageId,
                                  `v${(item as PageVersion).version}`
                                )
                              } else {
                                // Product doc diff - use onDiff callback
                                onDiff?.(item as ProductDocHistory)
                              }
                            }}
                            disabled={isUnavailable || actionState?.action === 'diff'}
                            aria-label={`Compare ${title}`}
                          >
                            {actionState?.id === id && actionState.action === 'diff' ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              'Compare'
                            )}
                          </Button>
                        ) : null}

                        {showRollbackAction ? (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className={actionButtonClass}
                            onClick={() => onRollback?.(item as ProjectSnapshot)}
                            disabled={isUnavailable}
                            aria-label={`Rollback to ${title}`}
                          >
                            {actionState?.id === id && actionState.action === 'rollback' ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <span className="inline-flex items-center gap-1">
                                <RotateCcw className="h-3.5 w-3.5" />
                                Rollback
                              </span>
                            )}
                          </Button>
                        ) : null}

                        {showPinAction ? (
                          <Button
                            type="button"
                            variant={isPinned ? 'ghost' : 'outline'}
                            size="sm"
                            className={actionButtonClass}
                            onClick={() =>
                              isPinned
                                ? onUnpin?.(
                                    item as PageVersion | ProjectSnapshot | ProductDocHistory
                                  )
                                : onPin?.(
                                    item as PageVersion | ProjectSnapshot | ProductDocHistory
                                  )
                            }
                            disabled={isUnavailable}
                            aria-label={`${isPinned ? 'Unpin' : 'Pin'} ${title}`}
                          >
                            {actionState?.id === id &&
                            (actionState.action === 'pin' || actionState.action === 'unpin') ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <span className="inline-flex items-center gap-1">
                                {isPinned ? (
                                  <>
                                    <PinOff className="h-3.5 w-3.5" />
                                    Unpin
                                  </>
                                ) : (
                                  <>
                                    <Pin className="h-3.5 w-3.5" />
                                    Pin
                                  </>
                                )}
                              </span>
                            )}
                          </Button>
                        ) : null}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        ))}

        {!isLoading && versions.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/70 bg-muted/20 px-4 py-8 text-center text-sm text-muted-foreground">
            {emptyMessage ?? 'No version history yet'}
          </div>
        ) : null}
      </div>
    </ScrollArea>
  )
})

VersionTimeline.displayName = 'VersionTimeline'
