import * as React from 'react'
import { Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'

export interface ChatInputProps {
  onSend: (message: string, options?: { triggerInterview?: boolean }) => void
  disabled?: boolean
  placeholder?: string
  initialInterviewOn?: boolean
  showInterviewToggle?: boolean
}

export function ChatInput({
  onSend,
  disabled = false,
  placeholder = 'Describe what you want to build...',
  initialInterviewOn = false,
  showInterviewToggle = true,
}: ChatInputProps) {
  const [message, setMessage] = React.useState('')
  const [triggerInterview, setTriggerInterview] = React.useState(initialInterviewOn)
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)
  const prevInitialRef = React.useRef(initialInterviewOn)

  React.useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`
    }
  }, [message])

  React.useEffect(() => {
    if (!prevInitialRef.current && initialInterviewOn) {
      setTriggerInterview(true)
    }
    prevInitialRef.current = initialInterviewOn
  }, [initialInterviewOn])

  const handleSend = React.useCallback(() => {
    if (!message.trim() || disabled) return
    const shouldTriggerInterview = triggerInterview
    onSend(message.trim(), shouldTriggerInterview ? { triggerInterview: true } : undefined)
    setMessage('')
    setTriggerInterview(false)
  }, [message, disabled, onSend, triggerInterview])

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex w-full flex-col gap-2 rounded-2xl border border-border bg-background p-3 shadow-sm">
      <div className="flex items-end gap-2">
        <Textarea
          ref={textareaRef}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          aria-label="Message input"
          rows={1}
          className="min-h-[44px] flex-1 resize-none border-0 bg-transparent p-0 text-sm shadow-none focus-visible:ring-0"
        />
        <Button
          type="button"
          onClick={handleSend}
          disabled={disabled || !message.trim()}
          size="icon"
          className="h-10 w-10 shrink-0"
          aria-label="Send message"
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>
      {showInterviewToggle ? (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <Switch
              checked={triggerInterview}
              onCheckedChange={setTriggerInterview}
              disabled={disabled}
              aria-label="Trigger interview"
            />
            <span>Interview</span>
          </div>
        </div>
      ) : null}
    </div>
  )
}
