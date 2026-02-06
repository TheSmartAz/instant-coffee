import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type { AestheticScore, AestheticSuggestion } from '@/types/aesthetic'
import { ScoreBar, ScoreGauge } from '@/components/ui/AestheticScore'

const DIMENSION_LABELS: Record<string, string> = {
  visualHierarchy: 'Visual hierarchy',
  colorHarmony: 'Color harmony',
  spacingConsistency: 'Spacing consistency',
  alignment: 'Alignment',
  readability: 'Readability',
  mobileAdaptation: 'Mobile adaptation',
}

const severityClass = (severity: string) => {
  switch (severity) {
    case 'critical':
      return 'bg-red-500/10 text-red-600 border-red-500/30'
    case 'warning':
      return 'bg-amber-500/10 text-amber-600 border-amber-500/30'
    default:
      return 'bg-blue-500/10 text-blue-600 border-blue-500/30'
  }
}

export interface AestheticScoreCardProps {
  score: AestheticScore
  expanded?: boolean
  onApplyFix?: (suggestion: AestheticSuggestion) => void
}

export const AestheticScoreCard = ({
  score,
  expanded = true,
  onApplyFix,
}: AestheticScoreCardProps) => {
  const dimensions = score.dimensions
  const dimensionEntries = Object.entries(dimensions)

  return (
    <Card className="shadow-none">
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <div>
          <CardTitle className="text-sm">Aesthetic score</CardTitle>
          <p className="text-xs text-muted-foreground">Visual quality assessment</p>
        </div>
        <Badge variant={score.passThreshold ? 'default' : 'secondary'}>
          {score.passThreshold ? 'Pass' : 'Needs work'}
        </Badge>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <ScoreGauge value={score.overall} />

        <div className="grid gap-3 sm:grid-cols-2">
          {dimensionEntries.map(([key, value]) => (
            <ScoreBar
              key={key}
              label={DIMENSION_LABELS[key] ?? key}
              value={value}
            />
          ))}
        </div>

        {expanded && score.suggestions.length > 0 ? (
          <div className="flex flex-col gap-3">
            <div className="text-xs font-semibold uppercase text-muted-foreground">Suggestions</div>
            <div className="flex flex-col gap-2">
              {score.suggestions.map((suggestion, index) => (
                <div
                  key={`${suggestion.dimension}-${index}`}
                  className="flex flex-col gap-2 rounded-lg border border-border p-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          'rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase',
                          severityClass(suggestion.severity)
                        )}
                      >
                        {suggestion.severity}
                      </span>
                      <span className="text-xs font-semibold text-foreground">
                        {DIMENSION_LABELS[suggestion.dimension] ?? suggestion.dimension}
                      </span>
                    </div>
                    {suggestion.autoFixable && onApplyFix ? (
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-6 px-2 text-[10px]"
                        onClick={() => onApplyFix(suggestion)}
                      >
                        Apply fix
                      </Button>
                    ) : null}
                  </div>
                  <p className="text-xs text-muted-foreground">{suggestion.message}</p>
                  {suggestion.location ? (
                    <div className="text-[10px] text-muted-foreground">
                      Location: {suggestion.location}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
