import * as React from 'react'
import { List, Sparkles } from 'lucide-react'
import type { ExecutionEvent } from '@/types/events'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { EventItem } from './EventItem'
import { useVirtualList } from '@/hooks/useVirtualList'

export type EventDisplayMode = 'streaming' | 'phase'

interface EventListProps {
  events: ExecutionEvent[]
  isLoading?: boolean
  emptyMessage?: string
  className?: string
  displayMode?: EventDisplayMode
  onDisplayModeChange?: (mode: EventDisplayMode) => void
}

/**
 * Filter events based on display mode
 * - Phase mode: Show only agent_start, agent_end, task events, plan events, token_usage, done
 * - Streaming mode: Show all events including progress and tool calls
 */
function filterEventsByMode(
  events: ExecutionEvent[],
  mode: EventDisplayMode
): ExecutionEvent[] {
  if (mode === 'streaming') {
    return events
  }

  // Phase mode: filter out progress updates and intermediate events
  const phaseEventTypes: Set<string> = new Set([
    'agent_start',
    'agent_end',
    'plan_created',
    'plan_updated',
    'task_started',
    'task_done',
    'task_failed',
    'task_blocked',
    'task_skipped',
    'token_usage',
    'done',
    'error',
  ])

  return events.filter((event) => phaseEventTypes.has(event.type))
}

export function EventList({
  events,
  isLoading = false,
  emptyMessage = 'Waiting for execution events...',
  className,
  displayMode: controlledDisplayMode,
  onDisplayModeChange,
}: EventListProps) {
  const rootRef = React.useRef<HTMLDivElement | null>(null)
  const viewportRef = React.useRef<HTMLDivElement | null>(null)
  const [autoScroll, setAutoScroll] = React.useState(true)
  const [scrollElement, setScrollElement] = React.useState<HTMLDivElement | null>(null)

  // Internal state for display mode (uncontrolled)
  const [internalDisplayMode, setInternalDisplayMode] = React.useState<EventDisplayMode>('phase')
  const displayMode = controlledDisplayMode ?? internalDisplayMode

  const handleDisplayModeChange = (checked: boolean) => {
    const newMode: EventDisplayMode = checked ? 'streaming' : 'phase'
    if (onDisplayModeChange) {
      onDisplayModeChange(newMode)
    } else {
      setInternalDisplayMode(newMode)
    }
  }

  React.useEffect(() => {
    const root = rootRef.current
    if (!root) return
    const viewport = root.querySelector(
      '[data-radix-scroll-area-viewport]'
    ) as HTMLDivElement | null
    if (!viewport) return
    viewportRef.current = viewport
    setScrollElement(viewport)
  }, [])

  // Filter events based on display mode
  const filteredEvents = React.useMemo(() => {
    return filterEventsByMode(events, displayMode)
  }, [events, displayMode])

  const {
    start,
    end,
    paddingTop,
    paddingBottom,
    totalHeight,
    scrollTop,
    viewportHeight,
    shouldVirtualize,
  } = useVirtualList({
    count: filteredEvents.length,
    estimateSize: 92,
    overscan: 6,
    minItems: 30,
    scrollElement,
  })

  const effectiveTotalHeight =
    scrollElement && !shouldVirtualize ? scrollElement.scrollHeight : totalHeight

  React.useEffect(() => {
    if (!scrollElement) return
    const isAtBottom = effectiveTotalHeight - scrollTop - viewportHeight < 40
    setAutoScroll(isAtBottom)
  }, [scrollElement, scrollTop, viewportHeight, effectiveTotalHeight])

  React.useLayoutEffect(() => {
    if (!autoScroll || !viewportRef.current) return
    viewportRef.current.scrollTo({
      top: effectiveTotalHeight,
      behavior: 'smooth',
    })
  }, [autoScroll, filteredEvents, effectiveTotalHeight])

  if (isLoading && events.length === 0) {
    return (
      <div className="flex h-full flex-col gap-3 p-4">
        {Array.from({ length: 5 }).map((_, index) => (
          <Skeleton key={index} className="h-14 w-full" />
        ))}
      </div>
    )
  }

  if (!isLoading && events.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-sm text-muted-foreground">
        {emptyMessage}
      </div>
    )
  }

  const visibleEvents = filteredEvents.slice(start, end)

  return (
    <div className={className}>
      {/* Display Mode Toggle */}
      <div className="flex items-center justify-between border-b px-4 py-2">
        <div className="flex items-center gap-2">
          {displayMode === 'streaming' ? (
            <Sparkles className="h-4 w-4 text-primary" />
          ) : (
            <List className="h-4 w-4 text-muted-foreground" />
          )}
          <span className="text-xs font-medium">
            {displayMode === 'streaming' ? 'Real-time Events' : 'Phase Summary'}
          </span>
          <span className="text-xs text-muted-foreground">
            ({filteredEvents.length} events)
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Label htmlFor="display-mode-toggle" className="cursor-pointer text-xs">
            Detailed
          </Label>
          <Switch
            id="display-mode-toggle"
            checked={displayMode === 'streaming'}
            onCheckedChange={handleDisplayModeChange}
            className="scale-75"
          />
        </div>
      </div>

      <ScrollArea ref={rootRef} className="h-[calc(100%-44px)]">
        <div
          style={{ paddingTop, paddingBottom }}
          className="space-y-2 px-4 py-4"
        >
          {visibleEvents.map((event, index) => (
            <EventItem
              key={`${event.timestamp}-${start + index}`}
              event={event}
            />
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
