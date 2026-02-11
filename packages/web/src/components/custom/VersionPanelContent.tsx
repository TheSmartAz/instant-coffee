import { toast } from '@/hooks/use-toast'
import { VersionTimeline, type VersionTimelineActionState } from './VersionTimeline'
import type { PageVersion, ProductDocHistory, ProjectSnapshot } from '@/types'
import type { VersionPanelType } from './VersionPanelStats'

interface VersionPanelContentProps {
  panelType: VersionPanelType
  emptyMessage: string
  actionState: VersionTimelineActionState | null
  pageVersions: PageVersion[]
  currentPageVersionId: number | null
  isLoadingPageVersions: boolean
  onPreviewVersion: (version: PageVersion) => void
  onPageDiff: (pageId: string, pageTitle: string) => void
  onPinPage: (item: PageVersion) => void
  onUnpinPage: (item: PageVersion) => void
  snapshots: ProjectSnapshot[]
  isLoadingSnapshots: boolean
  onRollback: (snapshot: ProjectSnapshot) => void
  onPinSnapshot: (item: ProjectSnapshot) => void
  onUnpinSnapshot: (item: ProjectSnapshot) => void
  productDocHistory: ProductDocHistory[]
  isLoadingProductDocHistory: boolean
  onViewProductDoc: (history: ProductDocHistory) => void
  onPinProductDoc: (item: ProductDocHistory) => void
  onUnpinProductDoc: (item: ProductDocHistory) => void
}

export function VersionPanelContent({
  panelType,
  emptyMessage,
  actionState,
  pageVersions,
  currentPageVersionId,
  isLoadingPageVersions,
  onPreviewVersion,
  onPageDiff,
  onPinPage,
  onUnpinPage,
  snapshots,
  isLoadingSnapshots,
  onRollback,
  onPinSnapshot,
  onUnpinSnapshot,
  productDocHistory,
  isLoadingProductDocHistory,
  onViewProductDoc,
  onPinProductDoc,
  onUnpinProductDoc,
}: VersionPanelContentProps) {
  return (
    <div className="flex min-h-0 flex-1">
      {panelType === 'page' ? (
        <VersionTimeline
          type="page"
          versions={pageVersions}
          currentId={currentPageVersionId ?? null}
          isLoading={isLoadingPageVersions}
          actions={['view', 'diff', 'pin']}
          actionState={actionState}
          emptyMessage={emptyMessage}
          onView={(item) => onPreviewVersion(item as PageVersion)}
          onPageDiff={onPageDiff}
          onPin={(item) => onPinPage(item as PageVersion)}
          onUnpin={(item) => onUnpinPage(item as PageVersion)}
        />
      ) : null}

      {panelType === 'snapshot' ? (
        <VersionTimeline
          type="snapshot"
          versions={snapshots}
          isLoading={isLoadingSnapshots}
          actions={['rollback', 'pin']}
          actionState={actionState}
          emptyMessage={emptyMessage}
          onRollback={(item) => onRollback(item as ProjectSnapshot)}
          onPin={(item) => onPinSnapshot(item as ProjectSnapshot)}
          onUnpin={(item) => onUnpinSnapshot(item as ProjectSnapshot)}
        />
      ) : null}

      {panelType === 'product-doc' ? (
        <VersionTimeline
          type="product-doc"
          versions={productDocHistory}
          isLoading={isLoadingProductDocHistory}
          actions={['view', 'diff', 'pin']}
          actionState={actionState}
          emptyMessage={emptyMessage}
          onView={(item) => onViewProductDoc(item as ProductDocHistory)}
          onDiff={() => {
            toast({
              title: 'Feature in progress',
              description: 'Product doc comparison will ship in v05-F2',
            })
          }}
          onPin={(item) => onPinProductDoc(item as ProductDocHistory)}
          onUnpin={(item) => onUnpinProductDoc(item as ProductDocHistory)}
        />
      ) : null}
    </div>
  )
}
