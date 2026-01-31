import * as React from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { MainContent } from '@/components/Layout/MainContent'
import { api } from '@/api/client'
import { toast } from '@/hooks/use-toast'
import { useSSE } from '@/hooks/useSSE'
import { usePlan } from '@/hooks/usePlan'
import type { TaskAction } from '@/components/Todo'

export function ExecutionPage() {
  const { id } = useParams()
  const sessionId = id ?? ''
  const streamUrl = sessionId ? api.chat.streamUrl(sessionId) : ''

  const { plan, progress, tokenUsage, handleEvent, updateTaskStatus } = usePlan()

  const sse = useSSE({
    url: streamUrl,
    autoConnect: Boolean(sessionId),
    onEvent: handleEvent,
    onError: (error) => {
      toast({ title: 'SSE connection error', description: error.message })
    },
  })

  const statusLabel =
    sse.connectionState === 'open'
      ? 'Live'
      : sse.connectionState === 'connecting'
        ? 'Connecting'
        : sse.connectionState === 'error'
          ? 'Disconnected'
          : undefined

  const handleTaskAction = React.useCallback(
    async (taskId: string, action: TaskAction) => {
      try {
        if (action === 'retry') {
          await api.tasks.retry(taskId)
          updateTaskStatus(taskId, 'retrying')
          toast({ title: 'Retry requested', description: `Task ${taskId} queued.` })
        } else if (action === 'skip') {
          await api.tasks.skip(taskId)
          updateTaskStatus(taskId, 'skipped', { progress: 100 })
          toast({ title: 'Task skipped', description: `Task ${taskId} skipped.` })
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Action failed'
        toast({ title: 'Task action failed', description: message })
      }
    },
    [updateTaskStatus]
  )

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-border px-6 py-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" asChild>
            <Link to={sessionId ? `/project/${sessionId}` : '/'}>
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div className="text-sm font-semibold text-foreground">
            Execution Flow {sessionId ? `• ${sessionId}` : ''}
          </div>
        </div>
      </header>
      <div className="flex-1">
        <MainContent
          plan={plan}
          events={sse.events}
          isLoading={sse.isLoading}
          progress={progress}
          tokenUsage={tokenUsage}
          statusLabel={statusLabel}
          onTaskAction={handleTaskAction}
        />
      </div>
    </div>
  )
}
