import { Loader2, CheckCircle2, XCircle } from 'lucide-react'

export type AgentStatus = 'running' | 'completed' | 'failed'

export interface AgentInfo {
  id: string
  task: string
  status: AgentStatus
  message?: string
}

interface AgentStatusPanelProps {
  agents: AgentInfo[]
}

const summarizeAgentText = (value: string) => {
  const cleaned = value
    .replace(/<\/?think>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  if (cleaned.length <= 160) return cleaned
  return `${cleaned.slice(0, 157)}...`
}

const STATUS_CONFIG: Record<
  AgentStatus,
  { icon: typeof Loader2; className: string }
> = {
  running: { icon: Loader2, className: 'text-foreground animate-spin' },
  completed: { icon: CheckCircle2, className: 'text-foreground' },
  failed: { icon: XCircle, className: 'text-destructive' },
}

export function AgentStatusPanel({ agents }: AgentStatusPanelProps) {
  if (!agents.length) return null

  return (
    <div className="mt-2 rounded-lg border border-border/60 bg-muted/30 p-3">
      <div className="mb-1.5 text-xs font-medium text-muted-foreground">
        Sub-agents ({agents.length})
      </div>
      <div className="space-y-1.5">
        {agents.map((agent) => {
          const config = STATUS_CONFIG[agent.status] ?? STATUS_CONFIG.running
          const Icon = config.icon
          const message = summarizeAgentText(agent.message ?? agent.task)

          return (
            <div
              key={agent.id}
              className="flex min-w-0 items-center gap-2 text-xs"
            >
              <Icon className={`h-3.5 w-3.5 shrink-0 ${config.className}`} />
              <span
                className="min-w-0 flex-1 overflow-hidden break-words text-foreground"
                style={{
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                }}
                title={message}
              >
                {message}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
