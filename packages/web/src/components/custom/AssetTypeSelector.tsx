import { Image, Layers, Package, Palette } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { AssetType } from '@/types'

export interface AssetTypeSelectorProps {
  selected: AssetType | null
  onSelect: (type: AssetType) => void
  onCancel: () => void
}

const ASSET_TYPES: Array<{
  type: AssetType
  label: string
  description: string
  icon: typeof Image
}> = [
  {
    type: 'logo',
    label: 'Logo',
    description: 'Used in navigation, headers, or footers.',
    icon: Package,
  },
  {
    type: 'style_ref',
    label: 'Style reference',
    description: 'Extract color and typography direction.',
    icon: Palette,
  },
  {
    type: 'background',
    label: 'Background',
    description: 'Hero or section background imagery.',
    icon: Image,
  },
  {
    type: 'product_image',
    label: 'Product image',
    description: 'Primary product or content visuals.',
    icon: Layers,
  },
]

export function AssetTypeSelector({ selected, onSelect, onCancel }: AssetTypeSelectorProps) {
  return (
    <div className="space-y-4" data-testid="asset-type-selector">
      <div className="grid gap-3 sm:grid-cols-2">
        {ASSET_TYPES.map((asset) => {
          const Icon = asset.icon
          const isSelected = asset.type === selected
          return (
            <button
              key={asset.type}
              type="button"
              onClick={() => onSelect(asset.type)}
              data-testid={`asset-type-option-${asset.type}`}
              data-selected={isSelected ? 'true' : 'false'}
              className={cn(
                'flex items-start gap-3 rounded-lg border px-3 py-3 text-left transition',
                isSelected
                  ? 'border-primary bg-primary/5 shadow-sm'
                  : 'border-border hover:border-primary/40 hover:bg-muted/40'
              )}
            >
              <div
                className={cn(
                  'mt-0.5 flex h-9 w-9 items-center justify-center rounded-md',
                  isSelected ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'
                )}
              >
                <Icon className="h-4 w-4" />
              </div>
              <div>
                <div className="text-sm font-semibold text-foreground">
                  {asset.label}
                </div>
                <div className="text-xs text-muted-foreground">
                  {asset.description}
                </div>
              </div>
            </button>
          )
        })}
      </div>
      <div className="flex justify-end">
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
