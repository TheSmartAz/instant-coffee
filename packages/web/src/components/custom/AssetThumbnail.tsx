import { Download, ExternalLink, X } from 'lucide-react'
import { resolveAssetUrl } from '@/api/assets'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { AssetType, ChatAsset } from '@/types'

export interface AssetThumbnailProps {
  asset: ChatAsset
  onRemove?: () => void
  className?: string
}

const ASSET_TYPE_LABELS: Record<AssetType, string> = {
  logo: 'Logo',
  style_ref: 'Style reference',
  background: 'Background',
  product_image: 'Product image',
}

export function AssetThumbnail({ asset, onRemove, className }: AssetThumbnailProps) {
  const imageUrl = asset.url ? resolveAssetUrl(asset.url) : ''
  const badgeLabel = ASSET_TYPE_LABELS[asset.assetType] ?? asset.assetType

  return (
    <div
      className={cn(
        'group relative h-24 w-24 shrink-0 overflow-hidden rounded-lg border border-border bg-muted/40',
        className
      )}
      data-testid="asset-thumbnail"
      data-asset-id={asset.id}
    >
      {imageUrl ? (
        <img
          src={imageUrl}
          alt={asset.name || badgeLabel}
          className="h-full w-full object-cover"
          loading="lazy"
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center text-[10px] text-muted-foreground">
          Asset
        </div>
      )}
      <div className="absolute left-2 top-2">
        <Badge variant="secondary" className="px-2 py-0 text-[10px]">
          {badgeLabel}
        </Badge>
      </div>
      {imageUrl ? (
        <div className="pointer-events-none absolute inset-x-2 bottom-2 flex items-center gap-1 opacity-0 transition group-hover:opacity-100">
          <a
            href={imageUrl}
            target="_blank"
            rel="noreferrer"
            className="pointer-events-auto inline-flex h-6 items-center gap-1 rounded-md bg-background/90 px-2 text-[10px] font-medium text-foreground shadow"
          >
            <ExternalLink className="h-3 w-3" />
            View
          </a>
          <a
            href={imageUrl}
            download
            className="pointer-events-auto inline-flex h-6 items-center gap-1 rounded-md bg-background/90 px-2 text-[10px] font-medium text-foreground shadow"
          >
            <Download className="h-3 w-3" />
            Save
          </a>
        </div>
      ) : null}
      {onRemove ? (
        <button
          type="button"
          onClick={onRemove}
          className="absolute right-1 top-1 inline-flex h-6 w-6 items-center justify-center rounded-full bg-background/90 text-muted-foreground opacity-0 shadow-sm transition group-hover:opacity-100 hover:text-foreground"
          aria-label={`Remove ${asset.name || badgeLabel}`}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      ) : null}
    </div>
  )
}
