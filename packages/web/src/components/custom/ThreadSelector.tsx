import { Plus, ChevronDown, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import type { Thread } from '@/types'

function CoffeeIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M17 8h1a4 4 0 1 1 0 8h-1" />
      <path d="M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4Z" />
      <line x1="6" y1="2" x2="6" y2="4" />
      <line x1="10" y1="2" x2="10" y2="4" />
      <line x1="14" y1="2" x2="14" y2="4" />
    </svg>
  )
}

interface ThreadSelectorProps {
  threads: Thread[]
  activeThreadId: string | null
  onSwitchThread: (threadId: string) => void
  onNewThread: () => void
  onDeleteThread: (threadId: string) => void
}

export function ThreadSelector({
  threads,
  activeThreadId,
  onSwitchThread,
  onNewThread,
  onDeleteThread,
}: ThreadSelectorProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="flex-1 min-w-0 justify-start gap-2 h-10 px-3 text-sm font-normal"
        >
          <CoffeeIcon className="h-4 w-4 shrink-0 text-muted-foreground" />
          <span className="truncate">
            {threads.find((t) => t.id === activeThreadId)?.title
              || `Thread ${Math.max(threads.findIndex((t) => t.id === activeThreadId) + 1, 1)}`}
          </span>
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground ml-auto" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        className="w-[var(--radix-dropdown-menu-trigger-width,_14rem)]"
      >
        {threads.map((thread, index) => {
          const isActive = thread.id === activeThreadId
          const label = thread.title || `Thread ${index + 1}`
          return (
            <DropdownMenuItem
              key={thread.id}
              className={`h-[3rem] flex items-center justify-between gap-2 hover:!bg-muted focus:!bg-muted data-[highlighted]:!bg-muted ${index > 0 ? 'mt-1' : ''} ${isActive ? 'bg-accent' : ''}`}
              onSelect={() => onSwitchThread(thread.id)}
            >
              <div className="flex items-center gap-2 min-w-0">
                <CoffeeIcon className="h-4 w-4 shrink-0" />
                <span className="truncate">{label}</span>
              </div>
              {threads.length > 1 && (
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    e.preventDefault()
                    onDeleteThread(thread.id)
                  }}
                  className="shrink-0 text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
            </DropdownMenuItem>
          )
        })}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="h-[3rem] hover:!bg-muted focus:!bg-muted data-[highlighted]:!bg-muted"
          onSelect={onNewThread}
        >
          <Plus className="h-4 w-4 mr-2" />
          New thread
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
