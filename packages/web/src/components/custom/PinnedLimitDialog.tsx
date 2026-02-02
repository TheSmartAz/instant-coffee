import * as React from 'react'
import { Check } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export interface PinnedLimitDialogItem {
  id: string | number
  title: string
  subtitle?: string
  meta?: string
}

export interface PinnedLimitDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  pendingItem: PinnedLimitDialogItem | null
  pinnedItems: PinnedLimitDialogItem[]
  onConfirm: (releaseId: string | number) => void
  isSubmitting?: boolean
}

export function PinnedLimitDialog({
  open,
  onOpenChange,
  pendingItem,
  pinnedItems,
  onConfirm,
  isSubmitting = false,
}: PinnedLimitDialogProps) {
  const [selectedId, setSelectedId] = React.useState<string | number | null>(null)

  React.useEffect(() => {
    if (!open) {
      setSelectedId(null)
      return
    }
    if (pinnedItems.length > 0) {
      setSelectedId(pinnedItems[0].id)
    }
  }, [open, pinnedItems])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Pin limit reached</DialogTitle>
          <DialogDescription>
            You can pin up to 2 versions per category. Release one before pinning{' '}
            {pendingItem ? `"${pendingItem.title}"` : 'the new version'}.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          {pinnedItems.length === 0 ? (
            <div className="rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground">
              No pinned versions available to release.
            </div>
          ) : (
            pinnedItems.map((item) => {
              const isSelected = item.id === selectedId
              return (
                <button
                  key={item.id}
                  type="button"
                  className={cn(
                    'w-full rounded-lg border px-3 py-2 text-left transition',
                    isSelected
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:border-primary/50'
                  )}
                  onClick={() => setSelectedId(item.id)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-foreground">
                        {item.title}
                      </div>
                      {item.subtitle ? (
                        <div className="text-xs text-muted-foreground line-clamp-1">
                          {item.subtitle}
                        </div>
                      ) : null}
                      {item.meta ? (
                        <div className="text-xs text-muted-foreground/80">
                          {item.meta}
                        </div>
                      ) : null}
                    </div>
                    <div
                      className={cn(
                        'mt-0.5 flex h-6 w-6 items-center justify-center rounded-full border',
                        isSelected
                          ? 'border-primary bg-primary text-primary-foreground'
                          : 'border-muted-foreground/30 text-transparent'
                      )}
                    >
                      <Check className="h-3.5 w-3.5" />
                    </div>
                  </div>
                </button>
              )
            })
          )}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              if (selectedId !== null) onConfirm(selectedId)
            }}
            disabled={selectedId === null || isSubmitting || pinnedItems.length === 0}
          >
            {isSubmitting ? 'Processing...' : 'Release and pin'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
