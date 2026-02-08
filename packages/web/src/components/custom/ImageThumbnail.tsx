import { X } from 'lucide-react'
import type { ChatAttachment } from '@/types'
import { cn } from '@/lib/utils'

export interface ImageThumbnailProps {
  attachment: ChatAttachment
  onRemove: () => void
  className?: string
}

const formatBytes = (bytes: number) => {
  if (!Number.isFinite(bytes)) return ''
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB']
  let value = bytes / 1024
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unitIndex]}`
}

export function ImageThumbnail({
  attachment,
  onRemove,
  className,
}: ImageThumbnailProps) {
  const sizeLabel = formatBytes(attachment.size)
  const dimensionLabel =
    attachment.width && attachment.height
      ? `${attachment.width}x${attachment.height}`
      : null
  const info = [sizeLabel, dimensionLabel].filter(Boolean).join(' • ')

  return (
    <div
      className={cn(
        'group relative h-20 w-20 shrink-0 overflow-hidden rounded-lg border border-border bg-muted/40',
        className
      )}
      data-testid="image-thumbnail"
    >
      {attachment.previewUrl ? (
        <img
          src={attachment.previewUrl}
          alt={attachment.name || 'Uploaded image'}
          className="h-full w-full object-cover"
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center text-[10px] text-muted-foreground">
          Image
        </div>
      )}
      <button
        type="button"
        onClick={onRemove}
        className="absolute right-1 top-1 inline-flex h-6 w-6 items-center justify-center rounded-full bg-background/90 text-muted-foreground opacity-0 shadow-sm transition group-hover:opacity-100 hover:text-foreground"
        aria-label={`Remove ${attachment.name || 'image'}`}
        data-testid="remove-image-button"
      >
        <X className="h-3.5 w-3.5" />
      </button>
      <div className="pointer-events-none absolute inset-0 flex items-end justify-start bg-gradient-to-t from-background/80 via-background/20 to-transparent opacity-0 transition group-hover:opacity-100">
        <div className="px-2 pb-2 text-[10px] font-medium text-foreground">
          <div className="truncate">{attachment.name || 'Image'}</div>
          {info ? <div className="text-[9px] text-muted-foreground">{info}</div> : null}
        </div>
      </div>
    </div>
  )
}
