import * as React from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import type { Plan } from '@/types/plan'
import { ProgressBar } from '@/components/EventFlow/ProgressBar'
import { TodoItem, type TaskAction } from './TodoItem'

interface TodoPanelProps {
  plan: Plan | null
  isLoading?: boolean
  progress: { completed: number; total: number; percent: number }
  onTaskAction?: (taskId: string, action: TaskAction) => void
}

export function TodoPanel({
  plan,
  isLoading = false,
  progress,
  onTaskAction,
}: TodoPanelProps) {
  const [isCollapsed, setIsCollapsed] = React.useState(false)

  return (
    <div
      className={cn(
        'flex h-full flex-col border-r border-border bg-background transition-[width] duration-200',
        isCollapsed ? 'w-12' : 'w-[264px]'
      )}
    >
      <div className={cn('flex items-center border-b border-border py-4', isCollapsed ? 'justify-center px-2' : 'justify-between px-4')}>
        <span className={cn('text-sm font-semibold text-foreground', isCollapsed ? 'sr-only' : '')}>
          Todo
        </span>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setIsCollapsed((prev) => !prev)}
          aria-label={isCollapsed ? 'Expand todo panel' : 'Collapse todo panel'}
        >
          {isCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </Button>
      </div>

      {isCollapsed ? (
        <div className="flex flex-1 flex-col items-center gap-3 py-4">
          {plan?.tasks.length
            ? plan.tasks.map((task) => (
                <span
                  key={task.id}
                  className={cn(
                    'h-3 w-3 rounded-full border',
                    task.status === 'done'
                      ? 'border-emerald-500 bg-emerald-500'
                      : task.status === 'failed' || task.status === 'timeout'
                        ? 'border-destructive bg-destructive'
                      : task.status === 'in_progress'
                        ? 'border-primary bg-primary'
                          : 'border-border bg-background'
                  )}
                />
              ))
            : Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-3 w-3 rounded-full" />
              ))}
        </div>
      ) : (
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="space-y-2 px-4 py-3">
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Plan Goal
            </div>
            {isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-4/5" />
                <Skeleton className="h-4 w-3/5" />
              </div>
            ) : plan ? (
              <div className="text-sm font-medium text-foreground">{plan.goal}</div>
            ) : (
              <div className="text-sm text-muted-foreground">No plan yet.</div>
            )}

            <div className="space-y-2 pt-2">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Progress</span>
                <span>
                  {progress.completed}/{progress.total}
                </span>
              </div>
              <ProgressBar value={progress.percent} status="in_progress" />
            </div>
          </div>

          <ScrollArea className="flex-1 px-4 pb-4">
            <div className="space-y-3">
              {isLoading && !plan
                ? Array.from({ length: 4 }).map((_, index) => (
                    <Skeleton key={index} className="h-16 w-full" />
                  ))
                : plan?.tasks.length
                  ? plan.tasks.map((task) => (
                      <TodoItem key={task.id} task={task} onAction={onTaskAction} />
                    ))
                  : (
                      <div className="text-sm text-muted-foreground">
                        Waiting for tasks to arrive.
                      </div>
                    )}
            </div>
          </ScrollArea>
        </div>
      )}
    </div>
  )
}
