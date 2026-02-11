import type { ComponentType } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface VersionPanelHeaderProps {
  isCollapsed: boolean
  title: string
  icon: ComponentType<{ className?: string }>
  onToggleCollapse: () => void
}

export function VersionPanelHeader({
  isCollapsed,
  title,
  icon: Icon,
  onToggleCollapse,
}: VersionPanelHeaderProps) {
  return (
    <div
      className={cn(
        'flex h-14 items-center border-b border-border',
        isCollapsed ? 'justify-center px-2' : 'justify-between px-4'
      )}
    >
      {!isCollapsed ? (
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-muted/60 text-foreground">
            <Icon className="h-4 w-4" />
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
              Version management
            </div>
            <div className="text-sm font-semibold text-foreground">{title}</div>
          </div>
        </div>
      ) : null}
      <Button
        variant="ghost"
        size="icon"
        onClick={onToggleCollapse}
        aria-label={isCollapsed ? 'Expand versions panel' : 'Collapse versions panel'}
      >
        {isCollapsed ? (
          <ChevronLeft className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
      </Button>
    </div>
  )
}
