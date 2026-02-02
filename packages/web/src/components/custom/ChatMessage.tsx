import { memo } from 'react'
import { ArrowRight } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { formatDistanceToNow } from 'date-fns'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { InterviewWidget } from './InterviewWidget'
import type { ChatStep, InterviewActionPayload, InterviewBatch, InterviewSummary, ChatAction, Disambiguation } from '@/types'

export interface ChatMessageProps {
  role: 'user' | 'assistant'
  content: string
  timestamp?: Date
  isStreaming?: boolean
  steps?: ChatStep[]
  interview?: InterviewBatch
  interviewSummary?: InterviewSummary
  action?: ChatAction
  affectedPages?: string[]
  disambiguation?: Disambiguation
  onInterviewAction?: (payload: InterviewActionPayload) => void
  onTabChange?: (tab: 'preview' | 'code' | 'product-doc') => void
  onDisambiguationSelect?: (option: { id: string; slug: string; title: string }) => void
}

export const ChatMessage = memo(function ChatMessage({
  role,
  content,
  timestamp,
  isStreaming,
  steps,
  interview,
  interviewSummary,
  action,
  affectedPages,
  disambiguation,
  onInterviewAction,
  onTabChange,
  onDisambiguationSelect,
}: ChatMessageProps) {
  const isAssistant = role === 'assistant'
  const hasSteps = Boolean(steps && steps.length > 0)
  const hasSummary = Boolean(interviewSummary && interviewSummary.items.length > 0)
  const hasInterview = Boolean(interview) && !hasSummary
  const hasDisambiguation = Boolean(disambiguation && disambiguation.options.length > 0)

  // Determine if we should show ProductDoc link
  const showProductDocLink =
    action === 'product_doc_generated' ||
    action === 'product_doc_updated'

  // Determine if we should show Preview link
  const showPreviewLink =
    action === 'pages_generated' ||
    action === 'page_refined'

  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-2">
      {isAssistant ? (
        <div className="w-full">
          <div className="mx-auto w-full max-w-3xl space-y-3 text-sm leading-relaxed text-foreground">
            {content ? (
              <div className="max-w-none">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    code({ className, children, ...props }) {
                      const isBlock = className?.includes('language-')
                      if (isBlock) {
                        return (
                          <pre className="overflow-x-auto rounded-lg bg-muted p-3 text-sm">
                            <code {...props}>{children}</code>
                          </pre>
                        )
                      }
                      return (
                        <code
                          className="rounded bg-muted px-1.5 py-0.5 text-xs text-foreground"
                          {...props}
                        >
                          {children}
                        </code>
                      )
                    },
                  }}
                >
                  {content}
                </ReactMarkdown>
                {isStreaming ? (
                  <span className="inline-flex items-center gap-1 pl-1 text-muted-foreground">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.2s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.1s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground" />
                  </span>
                ) : null}
              </div>
            ) : null}
            {!content && isStreaming ? (
              <span className="inline-flex items-center gap-1 text-muted-foreground">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.2s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.1s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground" />
              </span>
            ) : null}
            {hasInterview ? (
              <InterviewWidget
                batch={interview as InterviewBatch}
                onAction={(payload) => onInterviewAction?.(payload)}
              />
            ) : null}
            {hasSummary ? (
              <div className="rounded-lg border border-border/60 bg-muted/40 p-3">
                <div className="mb-2 flex items-center justify-between text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  <span>Answer summary</span>
                  <span>{interviewSummary?.items.length ?? 0} items</span>
                </div>
                <div className="space-y-2">
                  {(interviewSummary?.items ?? []).map((item, index) => (
                    <div
                      key={`${item.id}-${index}`}
                      className="rounded-md border border-border/60 bg-background/80 px-3 py-2"
                    >
                      <div className="text-[11px] text-muted-foreground">
                        Question {item.index ?? index + 1}: {item.question}
                      </div>
                      <div className="mt-1 text-sm font-medium text-foreground">
                        {item.labels?.join(', ') ?? item.label ?? String(item.value)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            {hasDisambiguation ? (
              <div className="rounded-lg border border-border/60 bg-muted/40 p-3">
                <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {disambiguation?.prompt || 'Select a page'}
                </div>
                <div className="flex flex-wrap gap-2">
                  {disambiguation?.options.map((option) => (
                    <Button
                      key={option.id}
                      variant="outline"
                      size="sm"
                      className="h-auto justify-start text-xs"
                      onClick={() => onDisambiguationSelect?.({
                        id: option.id,
                        slug: option.slug,
                        title: option.title,
                      })}
                    >
                      <div className="text-left">
                        <div className="font-medium">{option.title}</div>
                        {option.description ? (
                          <div className="text-muted-foreground">{option.description}</div>
                        ) : null}
                      </div>
                    </Button>
                  ))}
                </div>
              </div>
            ) : null}
            {showProductDocLink ? (
              <Button
                variant="outline"
                size="sm"
                className="h-8 gap-1 text-xs"
                onClick={() => onTabChange?.('product-doc')}
              >
                Open the Product Doc tab
                <ArrowRight className="h-3 w-3" />
              </Button>
            ) : null}
            {showPreviewLink ? (
              <Button
                variant="outline"
                size="sm"
                className="h-8 gap-1 text-xs"
                onClick={() => onTabChange?.('preview')}
              >
                View preview
                <ArrowRight className="h-3 w-3" />
              </Button>
            ) : null}
            {affectedPages && affectedPages.length > 0 ? (
              <div className="rounded-md border border-border/60 bg-muted/40 px-3 py-2">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Affected pages ({affectedPages.length})
                </div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {affectedPages.map((page, index) => (
                    <span
                      key={`${page}-${index}`}
                      className="inline-flex items-center rounded-full bg-background px-2 py-0.5 text-xs"
                    >
                      {page}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}
            {hasSteps ? (
              <div className="space-y-1 rounded-md border border-border/60 bg-background/60 px-3 py-2 text-xs text-muted-foreground">
                {steps?.map((step) => {
                  const statusClass =
                    step.status === 'done'
                      ? 'bg-emerald-500'
                      : step.status === 'failed'
                        ? 'bg-rose-500'
                        : 'bg-amber-500'
                  return (
                    <div key={step.id} className="flex items-start gap-2">
                      <span
                        className={cn('mt-1 h-1.5 w-1.5 rounded-full', statusClass)}
                      />
                      <span className="flex-1 leading-4">{step.label}</span>
                    </div>
                  )
                })}
              </div>
            ) : null}
            {timestamp ? (
              <div className="text-xs text-muted-foreground">
                {formatDistanceToNow(timestamp, { addSuffix: true })}
              </div>
            ) : null}
          </div>
        </div>
      ) : (
        <div className="flex w-full justify-end">
          <div className="flex max-w-[70%] flex-col items-end gap-1">
            <div className="w-full rounded-2xl bg-primary px-4 py-2 text-sm leading-relaxed text-primary-foreground shadow-sm">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ className, children, ...props }) {
                    const isBlock = className?.includes('language-')
                    if (isBlock) {
                      return (
                        <pre className="overflow-x-auto rounded-lg bg-primary-foreground/10 p-3 text-sm text-primary-foreground">
                          <code {...props}>{children}</code>
                        </pre>
                      )
                    }
                    return (
                      <code
                        className="rounded bg-primary-foreground/20 px-1.5 py-0.5 text-xs text-primary-foreground"
                        {...props}
                      >
                        {children}
                      </code>
                    )
                  },
                }}
              >
                {content}
              </ReactMarkdown>
            </div>
            {timestamp ? (
              <div className="text-xs text-muted-foreground">
                {formatDistanceToNow(timestamp, { addSuffix: true })}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
})
