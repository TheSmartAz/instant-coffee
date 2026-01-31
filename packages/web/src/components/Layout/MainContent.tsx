import type { ExecutionEvent } from '@/types/events'
import type { Plan } from '@/types/plan'
import type { SessionTokenSummary } from '@/types'
import { EventList } from '@/components/EventFlow/EventList'
import { TaskCardList } from '@/components/TaskCard'
import { TokenDisplay } from '@/components/TokenDisplay'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { TodoPanel, type TaskAction } from '@/components/Todo'

interface MainContentProps {
  plan: Plan | null
  events: ExecutionEvent[]
  isLoading?: boolean
  progress: { completed: number; total: number; percent: number }
  tokenUsage?: SessionTokenSummary
  statusLabel?: string
  onTaskAction?: (taskId: string, action: TaskAction) => void
}

export function MainContent({
  plan,
  events,
  isLoading = false,
  progress,
  tokenUsage,
  statusLabel,
  onTaskAction,
}: MainContentProps) {
  const tasks = plan?.tasks ?? []
  const isDone = plan?.status === 'done'

  return (
    <div className="flex h-full">
      <TodoPanel plan={plan} isLoading={isLoading} progress={progress} onTaskAction={onTaskAction} />
      <div className="flex flex-1 flex-col">
        <Tabs defaultValue="events" className="flex h-full flex-col">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <TabsList>
              <TabsTrigger value="events">Events</TabsTrigger>
              <TabsTrigger value="tasks">Tasks</TabsTrigger>
            </TabsList>
            {statusLabel ? (
              <span className="text-xs text-muted-foreground">{statusLabel}</span>
            ) : null}
          </div>
          <TabsContent value="events" className="mt-0 flex-1 overflow-auto">
            <EventList
              events={events}
              isLoading={isLoading}
              className="min-h-full space-y-2 p-4"
              emptyMessage="Waiting for execution events..."
            />
            {isDone && tokenUsage ? (
              <div className="border-t border-border p-4">
                <TokenDisplay usage={tokenUsage} showDetails={false} />
              </div>
            ) : null}
          </TabsContent>
          <TabsContent value="tasks" className="mt-0 flex-1">
            <TaskCardList tasks={tasks} events={events} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
