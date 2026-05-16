import {
  VersionPanel,
  type VersionPanelProps,
} from '@/components/custom/VersionPanel'
import { Drawer, DrawerBody, DrawerContent } from '@/components/custom/Drawer'

export interface VersionDrawerProps
  extends Omit<VersionPanelProps, 'isCollapsed' | 'onToggleCollapse' | 'presentation'> {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function VersionDrawer({
  open,
  onOpenChange,
  ...versionPanelProps
}: VersionDrawerProps) {
  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent
        title="Versions"
        description="Review page, code, and product doc history."
        className="sm:w-[min(100vw,34rem)]"
      >
        <DrawerBody>
          <VersionPanel
            {...versionPanelProps}
            isCollapsed={false}
            onToggleCollapse={() => onOpenChange(false)}
            presentation="drawer"
          />
        </DrawerBody>
      </DrawerContent>
    </Drawer>
  )
}
