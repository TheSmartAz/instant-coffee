import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface PageHeaderProps extends Omit<HTMLAttributes<HTMLElement>, 'title'> {
  title?: ReactNode
  leading?: ReactNode
  trailing?: ReactNode
}

export function PageHeader({
  title,
  leading,
  trailing,
  children,
  className,
  ...props
}: PageHeaderProps) {
  return (
    <header
      className={cn('flex items-center justify-between border-b border-border px-6 py-4', className)}
      {...props}
    >
      <div className="flex min-w-0 items-center gap-3">
        {leading}
        {title ? <h1 className="truncate text-lg font-semibold text-foreground">{title}</h1> : null}
        {children}
      </div>
      {trailing}
    </header>
  )
}
