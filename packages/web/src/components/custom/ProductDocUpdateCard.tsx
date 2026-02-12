import * as React from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface ProductDocUpdateCardProps {
  sectionName: string
  sectionContent: string
}

const FALLBACK_SECTION_NAME = 'Product Doc'
const FALLBACK_SECTION_CONTENT = 'No section preview was provided for this update.'

export function ProductDocUpdateCard({
  sectionName,
  sectionContent,
}: ProductDocUpdateCardProps) {
  const [expanded, setExpanded] = React.useState(false)

  const safeSectionName = sectionName.trim() || FALLBACK_SECTION_NAME
  const safeSectionContent = sectionContent.trim() || FALLBACK_SECTION_CONTENT

  return (
    <div className="mt-2 rounded-lg border border-border/60 bg-muted/30 p-3">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 text-left"
        onClick={() => setExpanded((prev) => !prev)}
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-2 text-sm font-medium text-foreground">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
          <span>Product Doc updated: {safeSectionName} section</span>
        </div>
        <span className="text-xs text-muted-foreground">
          {expanded ? 'Collapse' : 'Expand'}
        </span>
      </button>

      <div className={cn('grid transition-all', expanded ? 'grid-rows-[1fr] mt-3' : 'grid-rows-[0fr] mt-0')}>
        <div className="overflow-hidden">
          <div className="rounded-md border border-border/60 bg-background/80 p-3">
            <pre className="whitespace-pre-wrap break-words text-xs leading-relaxed text-foreground">
              {safeSectionContent}
            </pre>
          </div>
        </div>
      </div>
    </div>
  )
}
