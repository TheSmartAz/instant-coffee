import { formatDistanceToNow } from 'date-fns'
import { Loader2 } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

export interface Version {
  id: string
  number: number
  createdAt: Date
  isCurrent: boolean
}

export interface VersionTimelineProps {
  versions: Version[]
  onSelect: (versionId: string) => void
  onRevert?: (versionId: string) => void
  isLoading?: boolean
  revertingId?: string | null
}

export function VersionTimeline({
  versions,
  onSelect,
  onRevert,
  isLoading = false,
  revertingId = null,
}: VersionTimelineProps) {
  return (
    <ScrollArea className="h-full pr-3">
      <div className="relative space-y-4 pb-2">
        <div className="absolute left-[9px] top-2 h-full w-px bg-border" />
        {isLoading && versions.length === 0
          ? Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="relative flex items-start gap-3">
                <Skeleton className="mt-1 h-4 w-4 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-3 w-32" />
                </div>
                <Skeleton className="h-8 w-16" />
              </div>
            ))
          : null}
        {versions.map((version) => (
          <div key={version.id} className="relative flex items-start gap-3">
            <div
              className={cn(
                'mt-1 h-4 w-4 rounded-full border-2 border-border bg-background',
                version.isCurrent ? 'border-accent bg-accent' : ''
              )}
            />
            <button
              type="button"
              className="flex-1 text-left"
              onClick={() => onSelect(version.id)}
            >
              <div className="text-sm font-medium text-foreground">
                v{version.number}
              </div>
              <div className="text-xs text-muted-foreground">
                {formatDistanceToNow(version.createdAt, { addSuffix: true })}
              </div>
            </button>
            {onRevert && !version.isCurrent ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => onRevert(version.id)}
                disabled={isLoading || revertingId === version.id}
              >
                {revertingId === version.id ? (
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Reverting
                  </span>
                ) : (
                  'Revert'
                )}
              </Button>
            ) : null}
          </div>
        ))}
        {!isLoading && versions.length === 0 ? (
          <div className="px-2 text-sm text-muted-foreground">No versions yet.</div>
        ) : null}
      </div>
    </ScrollArea>
  )
}
