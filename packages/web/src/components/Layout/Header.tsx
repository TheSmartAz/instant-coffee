import { Coffee, Plus } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'

export function Header() {
  const navigate = useNavigate()

  const handleNewSession = () => {
    navigate('/project/new')
  }

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-border bg-background">
      <div className="flex items-center gap-2">
        <Coffee className="w-6 h-6 text-amber-600" />
        <span className="text-lg font-semibold text-foreground">
          Instant Coffee
        </span>
      </div>
      <Button
        variant="ghost"
        size="sm"
        onClick={handleNewSession}
        className="flex items-center gap-1 text-muted-foreground hover:text-foreground"
      >
        <Plus className="w-4 h-4" />
        新会话
      </Button>
    </header>
  )
}
