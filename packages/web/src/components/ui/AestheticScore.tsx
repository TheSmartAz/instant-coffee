import { cn } from '@/lib/utils'

const SCORE_COLORS = {
  excellent: '#22C55E',
  good: '#84CC16',
  fair: '#F59E0B',
  poor: '#EF4444',
}

const scoreTone = (value: number) => {
  if (value >= 85) return { label: 'Excellent', color: SCORE_COLORS.excellent }
  if (value >= 70) return { label: 'Good', color: SCORE_COLORS.good }
  if (value >= 60) return { label: 'Fair', color: SCORE_COLORS.fair }
  return { label: 'Poor', color: SCORE_COLORS.poor }
}

export interface ScoreGaugeProps {
  value: number
  label?: string
  className?: string
}

export const ScoreGauge = ({ value, label, className }: ScoreGaugeProps) => {
  const tone = scoreTone(value)
  return (
    <div className={cn('flex items-center gap-4', className)}>
      <div
        className="flex h-16 w-16 items-center justify-center rounded-full border-2"
        style={{ borderColor: tone.color }}
      >
        <span className="text-lg font-semibold" style={{ color: tone.color }}>
          {Math.round(value)}
        </span>
      </div>
      <div className="flex flex-col">
        <span className="text-xs uppercase tracking-wide text-muted-foreground">{label ?? 'Overall'}</span>
        <span className="text-sm font-semibold" style={{ color: tone.color }}>
          {tone.label}
        </span>
      </div>
    </div>
  )
}

export interface ScoreBarProps {
  label: string
  value: number
}

export const ScoreBar = ({ label, value }: ScoreBarProps) => {
  const tone = scoreTone(value)
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-semibold" style={{ color: tone.color }}>
          {Math.round(value)}
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-muted">
        <div
          className="h-2 rounded-full transition-all"
          style={{ width: `${Math.min(100, Math.max(0, value))}%`, backgroundColor: tone.color }}
        />
      </div>
    </div>
  )
}

export const SCORE_TONES = SCORE_COLORS
