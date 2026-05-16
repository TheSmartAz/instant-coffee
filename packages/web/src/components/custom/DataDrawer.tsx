import {
  DataTab,
  type DataTabProps,
} from '@/components/custom/DataTab'
import { Drawer, DrawerBody, DrawerContent } from '@/components/custom/Drawer'

export interface DataDrawerProps extends DataTabProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function DataDrawer({
  open,
  onOpenChange,
  ...dataTabProps
}: DataDrawerProps) {
  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent
        title="Data"
        description="Inspect generated app data."
        className="sm:w-[min(100vw,56rem)]"
      >
        <DrawerBody>
          <DataTab {...dataTabProps} />
        </DrawerBody>
      </DrawerContent>
    </Drawer>
  )
}
