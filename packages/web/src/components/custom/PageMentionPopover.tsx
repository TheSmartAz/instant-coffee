import * as React from 'react'
import type { Page } from '@/types'
import { cn } from '@/lib/utils'
import { filterPages } from '@/utils/chat'

export interface PageMentionPopoverProps {
  pages: Page[]
  query: string
  position: { x: number; y: number }
  placement?: 'top' | 'bottom'
  arrowOffset?: number
  selectedIndex?: number
  onSelect: (page: Page) => void
  onHoverIndex?: (index: number) => void
  className?: string
}

export const PageMentionPopover = React.forwardRef<HTMLDivElement, PageMentionPopoverProps>(
  function PageMentionPopover(
    {
      pages,
      query,
      position,
      placement = 'bottom',
      arrowOffset,
      selectedIndex = 0,
      onSelect,
      onHoverIndex,
      className,
    },
    ref
  ) {
  const filteredPages = React.useMemo(() => filterPages(pages, query), [pages, query])
  const arrowLeft = typeof arrowOffset === 'number' ? Math.max(8, arrowOffset) - 4 : null

  return (
    <div
      ref={ref}
      className={cn('fixed z-50 w-72 rounded-lg border border-border bg-background shadow-lg', className)}
      style={{ left: position.x, top: position.y }}
      role="listbox"
      aria-label="Page suggestions"
    >
      {arrowLeft !== null ? (
        <div
          className={cn(
            'pointer-events-none absolute h-2 w-2 rotate-45 border border-border bg-background shadow-sm',
            placement === 'top' ? 'bottom-[-4px]' : 'top-[-4px]'
          )}
          style={{ left: arrowLeft }}
        />
      ) : null}
      {filteredPages.length === 0 ? (
        <div className="px-3 py-2 text-xs text-muted-foreground">No matching pages</div>
      ) : (
        <ul className="max-h-56 overflow-y-auto py-1 text-sm">
          {filteredPages.map((page, index) => {
            const isActive = index === selectedIndex
            return (
              <li key={page.id} role="option" aria-selected={isActive}>
                <button
                  type="button"
                  onClick={() => onSelect(page)}
                  onMouseEnter={() => onHoverIndex?.(index)}
                  onMouseDown={(event) => event.preventDefault()}
                  className={cn(
                    'flex w-full items-center justify-between gap-2 px-3 py-2 text-left transition-colors duration-150',
                    isActive ? 'bg-muted text-foreground' : 'text-muted-foreground hover:bg-muted/60'
                  )}
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-foreground">
                      @{page.slug}
                    </div>
                    {page.title ? (
                      <div className="truncate text-xs text-muted-foreground">
                        {page.title}
                      </div>
                    ) : null}
                  </div>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
  }
)

PageMentionPopover.displayName = 'PageMentionPopover'
