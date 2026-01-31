import { memo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { formatDistanceToNow } from 'date-fns'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'

export interface ChatMessageProps {
  role: 'user' | 'assistant'
  content: string
  timestamp?: Date
  isStreaming?: boolean
}

export const ChatMessage = memo(function ChatMessage({
  role,
  content,
  timestamp,
  isStreaming,
}: ChatMessageProps) {
  const isAssistant = role === 'assistant'

  return (
    <div
      className={cn(
        'w-full border-b border-border animate-in fade-in slide-in-from-bottom-2',
        isAssistant ? 'bg-muted' : 'bg-background'
      )}
    >
      <div className="mx-auto flex max-w-4xl gap-4 px-6 py-6">
        <Avatar className="h-8 w-8 border border-border">
          <AvatarFallback className="bg-background text-xs font-semibold text-muted-foreground">
            {isAssistant ? 'AI' : 'You'}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1 space-y-2">
          <div className="max-w-none text-sm leading-relaxed text-foreground">
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
          {timestamp ? (
            <div className="text-xs text-muted-foreground">
              {formatDistanceToNow(timestamp, { addSuffix: true })}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
})
