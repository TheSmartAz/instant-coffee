import { Coffee } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'

export function Header() {
  return (
    <header className="grid min-w-0 grid-cols-1 items-center gap-3 border-b border-border bg-background px-4 py-4 sm:px-6 lg:grid-cols-[1fr_auto_1fr]">
      <div className="flex min-w-0 items-center justify-center gap-2 lg:justify-start">
        <Coffee className="h-6 w-6 shrink-0 text-warning" />
        <span className="truncate text-lg font-semibold text-foreground">
          Instant Coffee
        </span>
      </div>
      <nav className="flex min-w-0 items-center justify-center gap-5" aria-label="Main navigation">
          {[
            { to: '/', label: 'Homepage' },
            { to: '/recent-projects', label: 'Recent projects' },
            { to: '/settings', label: 'Settings' },
          ].map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                cn(
                  'rounded-full px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
                  isActive && 'bg-muted text-foreground'
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
      </nav>
      <div className="hidden lg:block" aria-hidden="true" />
    </header>
  )
}
