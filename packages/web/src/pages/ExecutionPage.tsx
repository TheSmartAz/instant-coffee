import * as React from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Clock3, Layers3, ListTodo, Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { AppLayout, ContentArea, PageHeader } from '@/components/Layout'
import { api } from '@/api/client'
import { useSSE } from '@/hooks/useSSE'
import { usePlan } from '@/hooks/usePlan'
import { EventList } from '@/components/EventFlow/EventList'
import { TaskCardList } from '@/components/TaskCard'
import { TokenDisplay } from '@/components/TokenDisplay'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { SessionTokenSummary } from '@/types'

function StatCard({
  label,
  value,
  description,
  icon,
}: {
  label: string
  value: string
  description: string
  icon: React.ReactNode
}) {
  return (
    <Card className="border-border/70 bg-card/80 shadow-sm">
      <CardContent className="flex items-start gap-3 p-4">
        <div className="rounded-lg border border-border bg-muted/60 p-2 text-muted-foreground">
          {icon}
        </div>
        <div className="min-w-0">
          <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </div>
          <div className="mt-1 text-2xl font-semibold text-foreground">{value}</div>
          <div className="mt-1 text-sm text-muted-foreground">{description}</div>
        </div>
      </CardContent>
    </Card>
  )
}

function formatTokenSummary(tokenUsage?: SessionTokenSummary) {
  if (!tokenUsage || tokenUsage.total.total_tokens === 0) {
    return '0 tokens'
  }
  return `${tokenUsage.total.total_tokens.toLocaleString()} tokens`
}

export function ExecutionPage() {
  const { id } = useParams()
  const sessionId = id ?? ''
  const streamUrl = sessionId ? api.chat.streamUrl(sessionId) : ''
  const shortSessionId = sessionId ? sessionId.slice(0, 8) : ''

  const { plan, progress, tokenUsage, handleEvent } = usePlan()

  const sse = useSSE({
    url: streamUrl,
    sessionId,
    autoConnect: Boolean(sessionId),
    onEvent: handleEvent,
    onError: () => undefined,
  })

  const statusLabel =
    sse.connectionState === 'open'
      ? 'Live'
      : sse.connectionState === 'connecting'
        ? 'Connecting'
        : sse.connectionState === 'error'
          ? 'Disconnected'
          : undefined

  const planGoal = plan?.goal ?? 'Waiting for the next run update'
  const taskCount = plan?.tasks.length ?? 0
  const eventCount = sse.events.length
  const progressLabel = `${progress.completed}/${progress.total}`

  return (
    <AppLayout className="h-screen min-h-0">
      <PageHeader
        className="border-border/70 bg-background/80 backdrop-blur"
        leading={
          <Button
            variant="ghost"
            size="icon"
            asChild
            aria-label={sessionId ? 'Back to project' : 'Back to home'}
          >
            <Link to={sessionId ? `/project/${sessionId}` : '/'}>
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
        }
        trailing={
          statusLabel ? (
            <Badge variant="secondary" className="rounded-full px-3 py-1">
              {statusLabel}
            </Badge>
          ) : null
        }
      >
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-foreground">
            Run Progress
          </div>
          {shortSessionId ? (
            <div className="truncate text-xs text-muted-foreground">
              Project {shortSessionId}
            </div>
          ) : null}
        </div>
      </PageHeader>

      <ContentArea className="overflow-hidden">
        <div className="mx-auto flex h-full w-full max-w-[1600px] flex-col gap-4 overflow-hidden px-4 py-4 sm:px-6 lg:px-8">
          <section className="grid gap-4 lg:grid-cols-[minmax(0,1.7fr)_minmax(320px,0.9fr)]">
            <div className="space-y-4">
              <Card className="border-border/70 bg-gradient-to-br from-background to-muted/30 shadow-sm">
                <CardHeader className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline" className="rounded-full">
                      Execution
                    </Badge>
                    <Badge variant="secondary" className="rounded-full">
                      {statusLabel ?? 'Idle'}
                    </Badge>
                  </div>
                  <div className="space-y-2">
                    <CardTitle className="text-2xl font-semibold tracking-tight">
                      {planGoal}
                    </CardTitle>
                    <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
                      Track the live run, inspect the task queue, and compare milestone
                      events without switching pages.
                    </p>
                  </div>
                </CardHeader>
                <CardContent className="grid gap-4 md:grid-cols-3">
                  <StatCard
                    label="Progress"
                    value={progressLabel}
                    description={`${Math.round(progress.percent)}% complete`}
                    icon={<Zap className="h-4 w-4" />}
                  />
                  <StatCard
                    label="Tasks"
                    value={String(taskCount)}
                    description="Task cards in the current plan"
                    icon={<ListTodo className="h-4 w-4" />}
                  />
                  <StatCard
                    label="Events"
                    value={String(eventCount)}
                    description={statusLabel ? `Connection is ${statusLabel.toLowerCase()}` : 'No live connection yet'}
                    icon={<Clock3 className="h-4 w-4" />}
                  />
                </CardContent>
              </Card>

              <Card className="border-border/70 shadow-sm">
                <CardHeader className="border-b border-border/60 pb-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <CardTitle className="text-base">Live Stream</CardTitle>
                      <p className="text-sm text-muted-foreground">
                        Phase summary and detailed event stream.
                      </p>
                    </div>
                    {tokenUsage ? (
                      <div className="hidden sm:block">
                        <TokenDisplay usage={tokenUsage} showDetails={false} className="min-w-[260px]" />
                      </div>
                    ) : null}
                  </div>
                </CardHeader>
                <CardContent className="p-0">
                  <Tabs defaultValue="events" className="flex h-[calc(100vh-430px)] min-h-[480px] flex-col">
                    <div className="flex items-center justify-between border-b border-border/60 px-4 py-3">
                      <TabsList>
                        <TabsTrigger value="events">Events</TabsTrigger>
                        <TabsTrigger value="tasks">Tasks</TabsTrigger>
                      </TabsList>
                      {statusLabel ? (
                        <span className="text-xs text-muted-foreground">{statusLabel}</span>
                      ) : null}
                    </div>
                    <TabsContent value="events" className="mt-0 flex-1 overflow-hidden">
                      <EventList
                        events={sse.events}
                        isLoading={sse.isLoading}
                        className="h-full"
                        emptyMessage="Waiting for execution events..."
                      />
                      {tokenUsage ? (
                        <div className="border-t border-border/60 p-4 sm:hidden">
                          <TokenDisplay usage={tokenUsage} showDetails={false} />
                        </div>
                      ) : null}
                    </TabsContent>
                    <TabsContent value="tasks" className="mt-0 flex-1 overflow-auto">
                      <div className="h-full p-4">
                        <TaskCardList tasks={plan?.tasks ?? []} events={sse.events} />
                      </div>
                    </TabsContent>
                  </Tabs>
                </CardContent>
              </Card>
            </div>

            <aside className="space-y-4 lg:sticky lg:top-4 lg:self-start">
              <Card className="border-border/70 shadow-sm">
                <CardHeader>
                  <CardTitle className="text-base">Run Snapshot</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Goal
                    </div>
                    <div className="mt-2 text-sm leading-6 text-foreground">{planGoal}</div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-lg border border-border/70 bg-muted/30 p-3">
                      <div className="text-xs text-muted-foreground">Completed</div>
                      <div className="mt-1 text-lg font-semibold">{progress.completed}</div>
                    </div>
                    <div className="rounded-lg border border-border/70 bg-muted/30 p-3">
                      <div className="text-xs text-muted-foreground">Total</div>
                      <div className="mt-1 text-lg font-semibold">{progress.total}</div>
                    </div>
                  </div>
                  <div className="rounded-lg border border-border/70 bg-muted/20 p-3">
                    <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      <Layers3 className="h-3.5 w-3.5" />
                      Connection
                    </div>
                    <div className="mt-2 text-sm text-foreground">
                      {statusLabel ?? 'Not connected'}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {sessionId ? `Session ${shortSessionId}` : 'No session selected'}
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="border-border/70 shadow-sm">
                <CardHeader>
                  <CardTitle className="text-base">Token Usage</CardTitle>
                </CardHeader>
                <CardContent>
                  {tokenUsage ? (
                    <TokenDisplay usage={tokenUsage} showDetails />
                  ) : (
                    <div className="text-sm text-muted-foreground">No token data yet.</div>
                  )}
                  <div className="mt-4 rounded-lg border border-border/70 bg-muted/20 p-3 text-sm text-muted-foreground">
                    {formatTokenSummary(tokenUsage)}
                  </div>
                </CardContent>
              </Card>
            </aside>
          </section>
        </div>
      </ContentArea>
    </AppLayout>
  )
}
