import { Coffee, Plus } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'

export function Header() {
  const navigate = useNavigate()

  const handleNewSession = () => {
    navigate('/project/new')
  }

  return (
    <header className="flex min-w-0 items-center justify-between gap-3 border-b border-border bg-background px-4 py-4 sm:px-6">
      <div className="flex min-w-0 items-center gap-2">
        <Coffee className="h-6 w-6 shrink-0 text-warning" />
        <span className="truncate text-lg font-semibold text-foreground">
          Instant Coffee
        </span>
      </div>
      <Button
        variant="ghost"
        size="sm"
        onClick={handleNewSession}
        className="shrink-0 gap-1 text-muted-foreground hover:text-foreground"
      >
        <Plus className="h-4 w-4" />
        New session
      </Button>
    </header>
  )
}
