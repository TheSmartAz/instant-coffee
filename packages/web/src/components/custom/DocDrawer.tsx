import {
  ProductDocPanel,
  type ProductDocPanelProps,
} from '@/components/custom/ProductDocPanel'
import { Drawer, DrawerBody, DrawerContent } from '@/components/custom/Drawer'

export interface DocDrawerProps extends ProductDocPanelProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function DocDrawer({
  open,
  onOpenChange,
  ...panelProps
}: DocDrawerProps) {
  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent
        title="Product Doc"
        description="Review the current product requirements."
        className="sm:w-[min(100vw,44rem)]"
      >
        <DrawerBody>
          <ProductDocPanel {...panelProps} />
        </DrawerBody>
      </DrawerContent>
    </Drawer>
  )
}
