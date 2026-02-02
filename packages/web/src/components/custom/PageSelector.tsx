import * as React from 'react'
import { cn } from '@/lib/utils'

export interface PageSelectorProps {
  pages: Array<{
    id: string
    title: string
    slug: string
  }>
  selectedPageId: string | null
  onSelectPage: (pageId: string) => void
}

export function PageSelector({
  pages,
  selectedPageId,
  onSelectPage,
}: PageSelectorProps) {
  if (pages.length <= 1) {
    return null
  }

  return (
    <div
      className="flex gap-1 overflow-x-auto border-b border-border px-4 py-2"
      style={{
        scrollbarWidth: 'none',
        msOverflowStyle: 'none',
      }}
    >
      <style>{`
        .page-selector-scroll::-webkit-scrollbar {
          display: none;
        }
      `}</style>
      {pages.map((page) => (
        <button
          key={page.id}
          className={cn(
            'px-3 py-1.5 text-sm rounded-md border border-transparent transition-all whitespace-nowrap',
            'hover:bg-muted hover:text-foreground',
            page.id === selectedPageId
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground bg-transparent'
          )}
          onClick={() => onSelectPage(page.id)}
          type="button"
        >
          {page.title}
        </button>
      ))}
    </div>
  )
}
