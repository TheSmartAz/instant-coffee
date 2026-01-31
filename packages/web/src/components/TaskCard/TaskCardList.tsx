import * as React from 'react'
import type { ExecutionEvent } from '@/types/events'
import type { Task } from '@/types/plan'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useVirtualList } from '@/hooks/useVirtualList'
import { TaskCard } from './TaskCard'

interface TaskCardListProps {
  tasks: Task[]
  events: ExecutionEvent[]
}

const statusOrder: Record<string, number> = {
  in_progress: 0,
  retrying: 1,
  pending: 2,
  blocked: 3,
  done: 4,
  failed: 5,
  skipped: 6,
}

export function TaskCardList({ tasks, events }: TaskCardListProps) {
  const sortedTasks = React.useMemo(
    () =>
      [...tasks].sort(
        (a, b) => (statusOrder[a.status] ?? 99) - (statusOrder[b.status] ?? 99)
      ),
    [tasks]
  )

  const activeTasks = React.useMemo(
    () =>
      new Set(
        tasks
          .filter((task) => task.status === 'in_progress' || task.status === 'retrying')
          .map((task) => task.id)
      ),
    [tasks]
  )

  const rootRef = React.useRef<HTMLDivElement | null>(null)
  const [scrollElement, setScrollElement] = React.useState<HTMLDivElement | null>(null)

  React.useEffect(() => {
    const root = rootRef.current
    if (!root) return
    const viewport = root.querySelector(
      '[data-radix-scroll-area-viewport]'
    ) as HTMLDivElement | null
    if (!viewport) return
    setScrollElement(viewport)
  }, [])

  const { start, end, paddingTop, paddingBottom } = useVirtualList({
    count: sortedTasks.length,
    estimateSize: 180,
    overscan: 4,
    minItems: 20,
    scrollElement,
  })

  if (tasks.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-sm text-muted-foreground">
        No tasks yet.
      </div>
    )
  }

  const visibleTasks = sortedTasks.slice(start, end)

  return (
    <ScrollArea ref={rootRef} className="h-full">
      <div style={{ paddingTop, paddingBottom }} className="space-y-3 px-4 py-4">
        {visibleTasks.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            events={events}
            isActive={activeTasks.has(task.id)}
          />
        ))}
      </div>
    </ScrollArea>
  )
}
