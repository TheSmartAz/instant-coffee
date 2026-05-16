import { Drawer, DrawerBody, DrawerContent } from '@/components/custom/Drawer'
import { RunInspector } from '@/components/custom/RunInspector'
import type { ChatRunStatus } from '@/types'

export interface RunDetailsDrawerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  sessionId?: string
  runStatus?: ChatRunStatus | null
  onOpenBuildPreview?: () => void
}

export function RunDetailsDrawer({
  open,
  onOpenChange,
  sessionId,
  runStatus,
  onOpenBuildPreview,
}: RunDetailsDrawerProps) {
  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent
        title="Run details"
        description="Review run status, approvals, verification, and recovery actions."
        className="sm:w-[min(100vw,38rem)]"
      >
        <DrawerBody className="overflow-y-auto">
          <RunInspector
            sessionId={sessionId}
            runStatus={runStatus}
            onOpenBuildPreview={onOpenBuildPreview}
            presentation="drawer"
          />
        </DrawerBody>
      </DrawerContent>
    </Drawer>
  )
}
