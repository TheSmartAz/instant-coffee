import { FileText, ArrowRight } from 'lucide-react'

export interface ProductDocSummaryCardProps {
  variant: 'created' | 'updated'
  changeSummary?: string
  onShowFullDoc?: () => void
}

export function ProductDocSummaryCard({
  variant,
  changeSummary,
  onShowFullDoc,
}: ProductDocSummaryCardProps) {
  const isCreated = variant === 'created'

  return (
    <div className="mt-2 rounded-lg border border-border/60 bg-muted/30 p-3">
      <div className="flex items-start gap-2.5">
        <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-muted">
          <FileText className="h-3.5 w-3.5 text-muted-foreground" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-foreground">
            {isCreated ? 'Product Doc created' : 'Product Doc updated'}
          </p>
          {changeSummary ? (
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              {changeSummary}
            </p>
          ) : null}
          {onShowFullDoc ? (
            <button
              type="button"
              onClick={onShowFullDoc}
              className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-foreground hover:text-foreground/80 transition-colors"
            >
              Show full Product Doc
              <ArrowRight className="h-3 w-3" />
            </button>
          ) : null}
        </div>
      </div>
    </div>
  )
}
