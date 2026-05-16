import { useState, type ChangeEvent, type KeyboardEvent } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { formatRelativeDate } from '@/lib/formatRelativeDate'
import { cn } from '@/lib/utils'

export interface ProjectCardProps {
  id: string
  name: string
  thumbnail?: string
  updatedAt: Date
  versionCount: number
  onClick?: () => void
  selectable?: boolean
  selected?: boolean
  onSelectChange?: (checked: boolean) => void
  badgeLabel?: string
}

export function ProjectCard({
  name,
  thumbnail,
  updatedAt,
  versionCount,
  onClick,
  selectable,
  selected,
  onSelectChange,
  badgeLabel,
}: ProjectCardProps) {
  const [previewFailed, setPreviewFailed] = useState(false)
  const showThumbnail = Boolean(thumbnail) && !previewFailed

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!onClick) return
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onClick()
    }
  }

  const handleSelectChange = (event: ChangeEvent<HTMLInputElement>) => {
    event.stopPropagation()
    onSelectChange?.(event.target.checked)
  }

  return (
    <Card
      onClick={onClick}
      onKeyDown={handleKeyDown}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : -1}
      className={cn(
        'group relative transition-shadow hover:shadow-subtle',
        onClick ? 'cursor-pointer hover:-translate-y-[1px]' : 'cursor-default'
      )}
    >
      {selectable ? (
        <div
          className="absolute left-3 top-3 z-10"
          onClick={(event) => event.stopPropagation()}
          onKeyDown={(event) => event.stopPropagation()}
        >
          <input
            type="checkbox"
            className="h-4 w-4 rounded border border-border text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            checked={Boolean(selected)}
            onChange={handleSelectChange}
            aria-label={`Select ${name}`}
          />
        </div>
      ) : null}
      {badgeLabel ? (
        <div className="absolute right-3 top-3 z-10">
          <Badge variant="secondary" className="rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wide">
            {badgeLabel}
          </Badge>
        </div>
      ) : null}
      <CardContent className="p-0">
        <div className="relative aspect-[9/14.625] w-full overflow-hidden rounded-lg bg-muted/40">
            {showThumbnail ? (
              <img
                src={thumbnail}
                alt={`${name} preview`}
                loading="lazy"
                decoding="async"
                onError={() => setPreviewFailed(true)}
                className="h-full w-full object-cover object-top"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground">
                No preview
              </div>
            )}
          <div className="absolute inset-x-0 bottom-0 h-[9.333%] border-t border-white/45 bg-white/82 px-3 pb-1.5 pt-1 text-black shadow-[0_-12px_28px_rgba(255,255,255,0.36)] backdrop-blur-md">
            <div className="flex h-full min-h-0 flex-col justify-end">
              <div className="truncate text-[13px] font-semibold leading-4 text-black">
                {name}
              </div>
              <div className="mt-0.5 truncate text-[10px] font-medium leading-3 text-black/65">
                {formatRelativeDate(updatedAt)} · {versionCount}{' '}
                {versionCount === 1 ? 'version' : 'versions'}
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
