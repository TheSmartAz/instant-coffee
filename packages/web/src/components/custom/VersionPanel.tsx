import { ChevronRight, ChevronLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import type { Version } from './VersionTimeline'
import { VersionTimeline } from './VersionTimeline'

export interface VersionPanelProps {
  versions: Version[]
  currentVersionId: string
  onSelectVersion: (id: string) => void
  onRevertVersion: (id: string) => void
  isCollapsed: boolean
  onToggleCollapse: () => void
  isLoading?: boolean
  revertingId?: string | null
}

export function VersionPanel({
  versions,
  currentVersionId,
  onSelectVersion,
  onRevertVersion,
  isCollapsed,
  onToggleCollapse,
  isLoading = false,
  revertingId = null,
}: VersionPanelProps) {
  return (
    <div
      className={cn(
        'flex h-full flex-col border-l border-border bg-background transition-all duration-200 ease-in-out',
        isCollapsed ? 'w-12' : 'w-64'
      )}
      style={{ flexGrow: 0, flexShrink: 0 }}
    >
      {/* Header */}
      <div
        className={cn(
          'flex items-center border-b border-border py-4',
          isCollapsed ? 'justify-center px-2' : 'justify-between px-4'
        )}
      >
        {!isCollapsed && (
          <span className="text-sm font-semibold">Versions</span>
        )}
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

      {/* Content */}
      {isCollapsed ? (
        // Collapsed: show version dots
        <div className="flex flex-1 flex-col items-center gap-3 py-4">
          {isLoading && versions.length === 0
            ? Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-3 w-3 rounded-full" />
              ))
            : versions.map((version) => (
                <button
                  key={version.id}
                  type="button"
                  onClick={() => onSelectVersion(version.id)}
                  className={cn(
                    'h-3 w-3 rounded-full border transition-colors',
                    version.id === currentVersionId
                      ? 'bg-accent border-accent'
                      : 'bg-background border-border hover:border-accent/50'
                  )}
                />
              ))}
        </div>
      ) : (
        // Expanded: show full timeline
        <div className="flex-1 overflow-y-auto">
          <div className="p-4">
            <VersionTimeline
              versions={versions}
              onSelect={onSelectVersion}
              onRevert={onRevertVersion}
              isLoading={isLoading}
              revertingId={revertingId}
            />
          </div>
        </div>
      )}
    </div>
  )
}
