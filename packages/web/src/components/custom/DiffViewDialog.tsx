import {
  Dialog,
  DialogContent,
} from '@/components/ui/dialog'
import { PageDiffViewer } from './PageDiffViewer'

interface DiffViewDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  sessionId: string | undefined
  pageId: string | undefined
  pageTitle?: string
}

export function DiffViewDialog({
  open,
  onOpenChange,
  sessionId,
  pageId,
  pageTitle,
}: DiffViewDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl h-[80vh] p-0">
        <PageDiffViewer
          sessionId={sessionId}
          pageId={pageId}
          pageTitle={pageTitle}
          onClose={() => onOpenChange(false)}
          className="h-full flex flex-col"
        />
      </DialogContent>
    </Dialog>
  )
}
