import type { KeyboardEvent } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { PhoneFrame } from './PhoneFrame'

export interface ProjectCardProps {
  id: string
  name: string
  thumbnail?: string
  updatedAt: Date
  versionCount: number
  onClick?: () => void
}

export function ProjectCard({
  name,
  thumbnail,
  updatedAt,
  versionCount,
  onClick,
}: ProjectCardProps) {
  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!onClick) return
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onClick()
    }
  }

  return (
    <Card
      onClick={onClick}
      onKeyDown={handleKeyDown}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : -1}
      className={cn(
        'group cursor-pointer transition-shadow hover:shadow-subtle',
        onClick ? 'hover:-translate-y-[1px]' : ''
      )}
    >
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
              {formatDistanceToNow(updatedAt, { addSuffix: true })} · {versionCount}{' '}
              {versionCount === 1 ? 'version' : 'versions'}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
