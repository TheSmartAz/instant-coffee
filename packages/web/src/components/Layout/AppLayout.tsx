import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface AppLayoutProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
}

export function AppLayout({ children, className, ...props }: AppLayoutProps) {
  return (
    <div
      className={cn('flex min-h-screen flex-col bg-background text-foreground', className)}
      {...props}
    >
      {children}
    </div>
  )
}
