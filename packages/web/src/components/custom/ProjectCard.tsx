import type { ChangeEvent, KeyboardEvent } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { formatRelativeDate } from '@/lib/formatRelativeDate'
import { cn } from '@/lib/utils'
import { PhoneFrame } from './PhoneFrame'

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
      <CardContent className="p-4">
        <div className="flex flex-col items-center gap-3">
          <PhoneFrame scale={0.52} className="max-w-[200px]">
            {thumbnail ? (
              <img
                src={thumbnail}
                alt={`${name} preview`}
                loading="lazy"
                decoding="async"
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center bg-muted text-xs text-muted-foreground">
                No preview
              </div>
            )}
          </PhoneFrame>
          <div className="w-full space-y-1 text-left">
            <div className="text-sm font-semibold text-foreground">{name}</div>
            <div className="text-xs text-muted-foreground">
              {formatRelativeDate(updatedAt)} · {versionCount}{' '}
              {versionCount === 1 ? 'version' : 'versions'}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
