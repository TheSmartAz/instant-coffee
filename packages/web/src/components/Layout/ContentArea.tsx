import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface ContentAreaProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
}

export function ContentArea({ children, className, ...props }: ContentAreaProps) {
  return (
    <main className={cn('flex-1', className)} {...props}>
      {children}
    </main>
  )
}
