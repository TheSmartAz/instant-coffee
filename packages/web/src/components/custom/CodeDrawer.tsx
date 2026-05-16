import type * as React from 'react'

import { CodePanel } from '@/components/custom/CodePanel'
import { Drawer, DrawerBody, DrawerContent } from '@/components/custom/Drawer'

export interface CodeDrawerProps
  extends Omit<React.ComponentProps<typeof CodePanel>, 'active'> {
  open: boolean
  onOpenChange: (open: boolean) => void
  active?: boolean
}

export function CodeDrawer({
  open,
  onOpenChange,
  active = true,
  sessionId,
}: CodeDrawerProps) {
  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent
        title="Code"
        description="Browse generated project files."
        className="sm:w-[min(100vw,52rem)]"
      >
        <DrawerBody>
          <CodePanel sessionId={sessionId} active={open && active} />
        </DrawerBody>
      </DrawerContent>
    </Drawer>
  )
}
