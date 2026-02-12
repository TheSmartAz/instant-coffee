import { memo, useState, useRef, useEffect, useMemo } from 'react'
import { ChevronRight, ChevronDown, Loader2, AlertCircle, Brain } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils'
import { InterviewWidget } from './InterviewWidget'
import { ProductDocUpdateCard } from './ProductDocUpdateCard'
import { ProductDocSummaryCard } from './ProductDocSummaryCard'
import { FileChangeCard } from './FileChangeCard'
import { PlanChecklist } from './PlanChecklist'
import { AgentStatusPanel } from './AgentStatusPanel'
import { ChatImageGrid } from './ChatImageGrid'
import type {
  ChatAction,
  ChatStep,
  InterviewActionPayload,
  InterviewBatch,
  MessageImage,
  MessageSegment,
  SubAgentInfo,
} from '@/types'
import type { FileChange, PlanStep, PlanTaskSnapshot } from '@/types/events'

export interface ChatMessageProps {
  role: 'user' | 'assistant'
  content: string
  timestamp?: Date
  isStreaming?: boolean
  steps?: ChatStep[]
  interview?: InterviewBatch
  action?: ChatAction
  productDocUpdated?: boolean
  productDocChangeSummary?: string
  productDocSectionName?: string
  productDocSectionContent?: string
  affectedPages?: string[]
  fileChanges?: FileChange[]
  plan?: PlanStep[]
  subAgents?: SubAgentInfo[]
  images?: MessageImage[]
  planTasks?: PlanTaskSnapshot[]
  segments?: MessageSegment[]
  onInterviewAction?: (payload: InterviewActionPayload) => void
  onTabChange?: (tab: 'preview' | 'code' | 'product-doc' | 'data') => void
}

/* ── Rich Tool Summary (collapsed by default, shows active tool) ── */

function RichToolSummary({ steps }: { steps: ChatStep[] }) {
  const [expanded, setExpanded] = useState(false)
  const doneCount = steps.filter((s) => s.status === 'done').length
  const activeTool = steps.find((s) => s.status === 'in_progress')
  const inProgress = Boolean(activeTool)

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
          <>
            <Loader2 className="h-3 w-3 animate-spin" />
            <span className="font-medium text-foreground">{activeTool?.toolName ?? activeTool?.label}</span>
          </>
        ) : (
          <span>
            {doneCount} tool{doneCount !== 1 ? 's' : ''} used
          </span>
        )}
      </button>
      {expanded ? (
        <div className="mt-1.5 space-y-1 pl-4 border-l border-border/50">
          {steps.map((step) => (
            <div key={step.id} className="space-y-0.5">
              <div
                className="flex items-center gap-2 text-xs text-muted-foreground"
              >
                {step.status === 'in_progress' ? (
                  <Loader2 className="h-3 w-3 animate-spin text-primary" />
                ) : step.status === 'failed' ? (
                  <AlertCircle className="h-3 w-3 text-destructive" />
                ) : (
                  <span className="h-3 w-3 text-center text-foreground">+</span>
                )}
                {step.toolName ? (
                  <span className="inline-flex items-center rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium">
                    {step.toolName}
                  </span>
                ) : null}
                <span className={cn(step.status === 'failed' && 'text-destructive')}>
                  {step.label}
                </span>
              </div>
              {step.status === 'in_progress' && step.progressMessage ? (
                <div className="ml-5 text-[10px] text-muted-foreground">
                  {step.progressMessage}
                  {step.progressPercent != null ? (
                    <div className="mt-0.5 h-1 w-24 rounded-full bg-muted overflow-hidden">
                      <div
                        className="h-full rounded-full bg-primary transition-all"
                        style={{ width: `${Math.min(100, step.progressPercent)}%` }}
                      />
                    </div>
                  ) : null}
                </div>
              ) : null}
              {step.status === 'failed' && step.error ? (
                <div className="ml-5 text-[10px] text-destructive">{step.error}</div>
              ) : null}
              {step.status === 'done' && step.toolOutput ? (
                <ToolOutputPreview output={step.toolOutput} />
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

/* ── Tool output preview (collapsible) ── */

function ToolOutputPreview({ output }: { output: Record<string, unknown> }) {
  const [open, setOpen] = useState(false)
  const preview = JSON.stringify(output, null, 2)
  if (preview.length < 10) return null

  return (
    <div className="ml-5">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="text-[10px] text-muted-foreground hover:text-foreground transition-colors"
      >
        {open ? 'Hide output' : 'Show output'}
      </button>
      {open ? (
        <pre className="mt-0.5 max-h-32 overflow-auto rounded bg-muted/50 p-1.5 text-[10px] text-muted-foreground">
          {preview.slice(0, 500)}
          {preview.length > 500 ? '...' : ''}
        </pre>
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

/* ── Parse <think> blocks from content ── */

function parseThinkingBlocks(content: string): { thinking: string; visible: string; thinkingComplete: boolean } {
  // Handle multiple <think>...</think> blocks and case variations
  const thinkRegex = /<think>([\s\S]*?)<\/think>/gi
  const thinkParts: string[] = []
  let visible = content

  // Extract all complete think blocks
  let match: RegExpExecArray | null
  while ((match = thinkRegex.exec(content)) !== null) {
    thinkParts.push(match[1])
  }
  // Remove complete blocks from visible
  visible = content.replace(/<think>[\s\S]*?<\/think>/gi, '')

  // Check for an unclosed <think> tag (still streaming)
  const lastOpen = visible.search(/<think>/i)
  if (lastOpen !== -1) {
    thinkParts.push(visible.slice(lastOpen + '<think>'.length))
    visible = visible.slice(0, lastOpen)
    return { thinking: thinkParts.join('\n'), visible, thinkingComplete: false }
  }

  if (thinkParts.length === 0) {
    return { thinking: '', visible: content, thinkingComplete: false }
  }

  return { thinking: thinkParts.join('\n'), visible, thinkingComplete: true }
}

/* ── Collapsible thinking block ── */

function ThinkingBlock({ content, isComplete, isStreaming }: { content: string; isComplete: boolean; isStreaming?: boolean }) {
  const [expanded, setExpanded] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const userScrolledRef = useRef(false)

  // Auto-scroll to bottom during streaming, unless user scrolled up
  useEffect(() => {
    const el = scrollRef.current
    if (!el || isComplete || userScrolledRef.current) return
    el.scrollTop = el.scrollHeight
  }, [content, isComplete])

  const handleScroll = () => {
    const el = scrollRef.current
    if (!el) return
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 30
    userScrolledRef.current = !isAtBottom
  }

  // Reset user scroll tracking when thinking completes
  useEffect(() => {
    if (isComplete) userScrolledRef.current = false
  }, [isComplete])

  if (!content) return null

  const showSpinner = !isComplete && isStreaming

  return (
    <div className="mb-2 rounded-lg border border-border/60 bg-muted/30">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center gap-2 px-3 py-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        {showSpinner ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground shrink-0" />
        ) : (
          <Brain className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        )}
        <span className="font-medium">
          {showSpinner ? 'Thinking...' : 'Thought process'}
        </span>
        {expanded ? (
          <ChevronDown className="ml-auto h-3 w-3" />
        ) : (
          <ChevronRight className="ml-auto h-3 w-3" />
        )}
      </button>
      {expanded ? (
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="max-h-60 overflow-y-auto border-t border-border/40 px-3 py-2 text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap"
        >
          {content}
          {showSpinner ? (
            <span className="ml-0.5 inline-block h-3 w-[2px] animate-pulse bg-muted-foreground align-text-bottom" />
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

/* ── Thinking spinner (no content yet) ── */

function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-2 py-1">
      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      <span className="text-sm text-muted-foreground">Thinking...</span>
    </div>
  )
}

/* ── Markdown block (reusable for segments) ── */

function MarkdownBlock({ content, isStreaming, showCursor }: { content: string; isStreaming?: boolean; showCursor?: boolean }) {
  const { thinking, visible, thinkingComplete } = useMemo(
    () => parseThinkingBlocks(content),
    [content]
  )
  const hasVisible = visible.trim().length > 0
  const hasThinking = thinking.length > 0

  return (
    <>
      {hasThinking ? (
        <ThinkingBlock content={thinking} isComplete={thinkingComplete} isStreaming={isStreaming} />
      ) : null}
      {hasVisible ? (
        <div className="prose prose-sm dark:prose-invert max-w-none text-foreground prose-headings:text-foreground prose-strong:text-foreground prose-a:text-accent prose-a:underline prose-code:text-foreground prose-blockquote:text-foreground/80 prose-li:marker:text-foreground/60 prose-headings:mt-4 prose-headings:mb-2 prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {visible}
          </ReactMarkdown>
          {showCursor ? <StreamingCursor /> : null}
        </div>
      ) : null}
    </>
  )
}

/* ── Main component ── */

export const ChatMessage = memo(function ChatMessage({
  role,
  content,
  isStreaming,
  steps,
  interview,
  action,
  productDocUpdated,
  productDocChangeSummary,
  productDocSectionName,
  productDocSectionContent,
  fileChanges,
  plan,
  subAgents,
  images,
  planTasks,
  segments,
  onInterviewAction,
  onTabChange,
}: ChatMessageProps) {
  const isUser = role === 'user'
  const hasSegments = segments && segments.length > 0
  const { thinking, visible, thinkingComplete } = useMemo(
    () => parseThinkingBlocks(content),
    [content]
  )
  const hasContent = visible.trim().length > 0
  const hasThinking = thinking.length > 0
  const hasSteps = steps && steps.length > 0
  const showThinking = isStreaming && !hasContent && !hasThinking && !interview && !hasSegments

  /* ── User bubble ── */
  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm text-primary-foreground">
          {images && images.length > 0 ? (
            <div className="mb-2">
              <ChatImageGrid images={images} />
            </div>
          ) : null}
          {content}
        </div>
      </div>
    )
  }

  /* ── Assistant flat layout ── */
  return (
    <div className="mx-auto w-full max-w-[95%]">
      {/* Thinking spinner */}
      {showThinking ? <ThinkingIndicator /> : null}

      {/* Segment-based rendering (interleaved text + tool groups) */}
      {hasSegments ? (
        segments.map((seg, i) => {
          const isLastSegment = i === segments.length - 1
          if (seg.type === 'text') {
            return (
              <MarkdownBlock
                key={i}
                content={seg.content}
                isStreaming={isStreaming}
                showCursor={isStreaming && isLastSegment}
              />
            )
          }
          return <RichToolSummary key={i} steps={seg.steps} />
        })
      ) : (
        <>
          {/* Collapsible thinking block */}
          {hasThinking ? (
            <ThinkingBlock content={thinking} isComplete={thinkingComplete} isStreaming={isStreaming} />
          ) : null}

          {/* Markdown content */}
          {hasContent ? (
            <div className="prose prose-sm dark:prose-invert max-w-none text-foreground prose-headings:text-foreground prose-strong:text-foreground prose-a:text-accent prose-a:underline prose-code:text-foreground prose-blockquote:text-foreground/80 prose-li:marker:text-foreground/60 prose-headings:mt-4 prose-headings:mb-2 prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {visible}
              </ReactMarkdown>
              {isStreaming ? <StreamingCursor /> : null}
            </div>
          ) : null}

          {/* Tool summary */}
          {hasSteps ? <RichToolSummary steps={steps} /> : null}
        </>
      )}

      {/* Interview widget — rendered after text so the intro message appears above */}
      {interview && onInterviewAction ? (
        <InterviewWidget batch={interview} onAction={onInterviewAction} />
      ) : null}

      {/* Plan checklist (simple steps mode) */}
      {plan && plan.length > 0 ? (
        <PlanChecklist steps={plan} />
      ) : null}

      {/* Plan tasks (rich task mode from plan_created) */}
      {planTasks && planTasks.length > 0 ? (
        <PlanChecklist tasks={planTasks} />
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
        <FileChangeCard files={fileChanges} />
      ) : null}

      {/* Product doc summary card (created / updated) */}
      {action === 'product_doc_generated' || action === 'product_doc_updated' ? (
        <ProductDocSummaryCard
          variant={action === 'product_doc_generated' ? 'created' : 'updated'}
          changeSummary={productDocChangeSummary}
          onShowFullDoc={onTabChange ? () => onTabChange('product-doc') : undefined}
        />
      ) : productDocUpdated && productDocSectionName && productDocSectionContent ? (
        <ProductDocUpdateCard
          sectionName={productDocSectionName}
          sectionContent={productDocSectionContent}
        />
      ) : null}
    </div>
  )
})
