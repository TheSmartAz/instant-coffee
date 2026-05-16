import * as React from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'

import { cn } from '@/lib/utils'

const Drawer = DialogPrimitive.Root
const DrawerTrigger = DialogPrimitive.Trigger
const DrawerClose = DialogPrimitive.Close

type DrawerSide = 'left' | 'right' | 'bottom'

export interface DrawerContentProps
  extends Omit<
    React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>,
    'title'
  > {
  title: React.ReactNode
  description?: React.ReactNode
  side?: DrawerSide
  showClose?: boolean
}

const sideClasses: Record<DrawerSide, string> = {
  left: 'left-0 top-0 h-dvh w-[min(100vw,42rem)] data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left',
  right: 'right-0 top-0 h-dvh w-[min(100vw,42rem)] data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right',
  bottom: 'bottom-0 left-0 max-h-[90dvh] w-full data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom',
}

const DrawerOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      'fixed inset-0 z-50 bg-black/50 data-[state=closed]:animate-out data-[state=open]:animate-in data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
      className
    )}
    {...props}
  />
))
DrawerOverlay.displayName = DialogPrimitive.Overlay.displayName

const DrawerContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  DrawerContentProps
>(
  (
    {
      className,
      children,
      title,
      description,
      side = 'right',
      showClose = true,
      ...props
    },
    ref
  ) => (
    <DialogPrimitive.Portal>
      <DrawerOverlay />
      <DialogPrimitive.Content
        ref={ref}
        className={cn(
          'fixed z-50 flex flex-col border-border bg-background shadow-xl outline-none duration-200 data-[state=closed]:animate-out data-[state=open]:animate-in',
          sideClasses[side],
          className
        )}
        {...props}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div className="min-w-0 space-y-1">
            <DialogPrimitive.Title className="truncate text-sm font-semibold text-foreground">
              {title}
            </DialogPrimitive.Title>
            {description ? (
              <DialogPrimitive.Description className="text-xs text-muted-foreground">
                {description}
              </DialogPrimitive.Description>
            ) : null}
          </div>
          {showClose ? (
            <DialogPrimitive.Close className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition hover:bg-muted hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background">
              <X className="h-4 w-4" />
              <span className="sr-only">Close drawer</span>
            </DialogPrimitive.Close>
          ) : null}
        </div>
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  )
)
DrawerContent.displayName = DialogPrimitive.Content.displayName

function DrawerBody({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('min-h-0 flex-1 overflow-hidden', className)}
      {...props}
    />
  )
}
DrawerBody.displayName = 'DrawerBody'

function DrawerFooter({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('border-t border-border px-5 py-4', className)}
      {...props}
    />
  )
}
DrawerFooter.displayName = 'DrawerFooter'

export {
  Drawer,
  DrawerBody,
  DrawerClose,
  DrawerContent,
  DrawerFooter,
  DrawerOverlay,
  DrawerTrigger,
}
