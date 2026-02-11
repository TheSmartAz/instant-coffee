import { memo, useState } from 'react'
import { ChevronRight, Loader2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils'
import { InterviewWidget } from './InterviewWidget'
import { ProductDocUpdateCard } from './ProductDocUpdateCard'
import { FileChangeCard } from './FileChangeCard'
import { PlanChecklist } from './PlanChecklist'
import { AgentStatusPanel } from './AgentStatusPanel'
import type {
  ChatAction,
  ChatStep,
  InterviewActionPayload,
  InterviewAnswer,
  InterviewBatch,
  InterviewSummary,
  SubAgentInfo,
} from '@/types'
import type { FileChange, PlanStep } from '@/types/events'

export interface ChatMessageProps {
  role: 'user' | 'assistant'
  content: string
  timestamp?: Date
  isStreaming?: boolean
  steps?: ChatStep[]
  interview?: InterviewBatch
  interviewSummary?: InterviewSummary
  action?: ChatAction
  productDocUpdated?: boolean
  productDocChangeSummary?: string
  productDocSectionName?: string
  productDocSectionContent?: string
  affectedPages?: string[]
  fileChanges?: FileChange[]
  plan?: PlanStep[]
  subAgents?: SubAgentInfo[]
  onInterviewAction?: (payload: InterviewActionPayload) => void
  onTabChange?: (tab: 'preview' | 'code' | 'product-doc' | 'data') => void
}

/* ── Tool summary (collapsed by default) ── */

function ToolSummary({ steps }: { steps: ChatStep[] }) {
  const [expanded, setExpanded] = useState(false)
  const doneCount = steps.filter((s) => s.status === 'done').length
  const inProgress = steps.some((s) => s.status === 'in_progress')

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <ChevronRight
          className={cn(
            'h-3 w-3 transition-transform',
            expanded && 'rotate-90'
          )}
        />
        {inProgress ? (
          <Loader2 className="h-3 w-3 animate-spin" />
        ) : null}
        <span>
          {doneCount} tool{doneCount !== 1 ? 's' : ''} used
        </span>
      </button>
      {expanded ? (
        <div className="mt-1.5 space-y-1 pl-4 border-l border-border/50">
          {steps.map((step) => (
            <div
              key={step.id}
              className="flex items-center gap-2 text-xs text-muted-foreground"
            >
              {step.status === 'in_progress' ? (
                <Loader2 className="h-3 w-3 animate-spin text-primary" />
              ) : step.status === 'failed' ? (
                <span className="h-3 w-3 text-center text-destructive">x</span>
              ) : (
                <span className="h-3 w-3 text-center text-emerald-500">+</span>
              )}
              <span>{step.label}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

/* ── Streaming cursor ── */

function StreamingCursor() {
  return (
    <span className="ml-0.5 inline-block h-4 w-[2px] animate-pulse bg-foreground align-text-bottom" />
  )
}

/* ── Thinking spinner ── */

function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-2 py-1">
      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      <span className="text-sm text-muted-foreground">Thinking...</span>
    </div>
  )
}

/* ── Interview answer summary (Q&A pairs) ── */

function InterviewSummaryDisplay({ items }: { items: InterviewAnswer[] }) {
  if (items.length === 0) return null
  return (
    <div className="mt-2 space-y-1.5">
      {items.map((item) => {
        const answer =
          item.labels?.join(', ') ?? item.label ?? String(item.value)
        return (
          <div key={item.id} className="text-sm">
            <span className="text-muted-foreground">{item.question}</span>
            <span className="text-muted-foreground"> — </span>
            <span className="font-semibold text-foreground">{answer}</span>
          </div>
        )
      })}
    </div>
  )
}

/* ── Main component ── */

export const ChatMessage = memo(function ChatMessage({
  role,
  content,
  isStreaming,
  steps,
  interview,
  interviewSummary,
  productDocUpdated,
  productDocSectionName,
  productDocSectionContent,
  fileChanges,
  plan,
  subAgents,
  onInterviewAction,
}: ChatMessageProps) {
  const isUser = role === 'user'
  const hasContent = content.trim().length > 0
  const hasSteps = steps && steps.length > 0
  const showThinking = isStreaming && !hasContent && !interview

  /* ── User bubble ── */
  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm text-primary-foreground">
          {content}
        </div>
      </div>
    )
  }

  /* ── Assistant flat layout ── */
  return (
    <div className="mx-auto w-full max-w-[95%]">
      {/* Interview widget */}
      {interview && onInterviewAction ? (
        <div className="mb-2">
          <InterviewWidget batch={interview} onAction={onInterviewAction} />
        </div>
      ) : null}

      {/* Interview answer summary */}
      {interviewSummary?.items?.length ? (
        <div className="mb-2">
          <InterviewSummaryDisplay items={interviewSummary.items} />
        </div>
      ) : null}

      {/* Thinking spinner */}
      {showThinking ? <ThinkingIndicator /> : null}

      {/* Markdown content */}
      {hasContent ? (
        <div className="prose prose-sm dark:prose-invert max-w-none text-sm leading-relaxed text-foreground">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {content}
          </ReactMarkdown>
          {isStreaming ? <StreamingCursor /> : null}
        </div>
      ) : null}

      {/* Tool summary */}
      {hasSteps ? <ToolSummary steps={steps} /> : null}

      {/* Plan checklist */}
      {plan && plan.length > 0 ? (
        <div className="mt-2">
          <PlanChecklist steps={plan} />
        </div>
      ) : null}

      {/* Sub-agent status */}
      {subAgents && subAgents.length > 0 ? (
        <AgentStatusPanel
          agents={subAgents.map((a) => ({
            id: a.id,
            task: a.task,
            status: a.status,
            message: a.summary,
          }))}
        />
      ) : null}

      {/* File changes */}
      {fileChanges && fileChanges.length > 0 ? (
        <div className="mt-2">
          <FileChangeCard files={fileChanges} />
        </div>
      ) : null}

      {/* Product doc update card */}
      {productDocUpdated && productDocSectionName && productDocSectionContent ? (
        <div className="mt-2">
          <ProductDocUpdateCard
            sectionName={productDocSectionName}
            sectionContent={productDocSectionContent}
          />
        </div>
      ) : null}
    </div>
  )
})
