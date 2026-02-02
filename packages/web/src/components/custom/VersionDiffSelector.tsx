import * as React from 'react'
import { Loader2 } from 'lucide-react'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { cn } from '@/lib/utils'
import type { ProductDocHistory } from '@/types'

export interface VersionDiffSelectorProps {
  versions: ProductDocHistory[]
  leftValue: string
  rightValue?: string
  onChange: (next: { left: string; right?: string }) => void
  isLoading?: boolean
  error?: string | null
}

type DiffOption = {
  value: string
  label: string
  changeSummary?: string
  isReleased?: boolean
  isPinned?: boolean
}

const CURRENT_VALUE = 'current'

const buildOptionLabel = (option: DiffOption) => {
  const badges = [
    option.isReleased ? 'released' : null,
    option.isPinned ? 'pinned' : null,
  ].filter(Boolean)
  const badgeText = badges.length > 0 ? ` (${badges.join(', ')})` : ''
  const summaryText = option.changeSummary ? ` · ${option.changeSummary}` : ''
  return `${option.label}${badgeText}${summaryText}`
}

export function VersionDiffSelector({
  versions,
  leftValue,
  rightValue,
  onChange,
  isLoading = false,
  error,
}: VersionDiffSelectorProps) {
  const options = React.useMemo<DiffOption[]>(() => {
    const historyOptions = [...versions]
      .sort((a, b) => b.version - a.version)
      .map((version) => ({
        value: String(version.id),
        label: `v${version.version}`,
        changeSummary: version.change_summary,
        isReleased: version.is_released,
        isPinned: version.is_pinned,
      }))

    return [
      {
        value: CURRENT_VALUE,
        label: 'Current version',
      },
      ...historyOptions,
    ]
  }, [versions])

  const leftDisabled = isLoading || options.length === 0
  const rightDisabled = isLoading || options.length === 0

  return (
    <div className="space-y-2">
      <div className="flex flex-col gap-3 md:flex-row">
        <div className="flex-1 space-y-1">
          <div className="text-xs font-medium text-muted-foreground">Left version</div>
          <Select
            value={leftValue}
            onValueChange={(value) => onChange({ left: value, right: rightValue })}
            disabled={leftDisabled}
          >
            <SelectTrigger className="h-10">
              <SelectValue placeholder="Choose a version" />
            </SelectTrigger>
            <SelectContent>
              {options.map((option) => (
                <SelectItem
                  key={option.value}
                  value={option.value}
                  disabled={option.value === rightValue}
                >
                  <span className="line-clamp-1">{buildOptionLabel(option)}</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex-1 space-y-1">
          <div className="text-xs font-medium text-muted-foreground">Right version</div>
          <Select
            value={rightValue}
            onValueChange={(value) => onChange({ left: leftValue, right: value })}
            disabled={rightDisabled}
          >
            <SelectTrigger className="h-10">
              <SelectValue placeholder="Choose a version" />
            </SelectTrigger>
            <SelectContent>
              {options.map((option) => (
                <SelectItem
                  key={option.value}
                  value={option.value}
                  disabled={option.value === leftValue}
                >
                  <span className="line-clamp-1">{buildOptionLabel(option)}</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Loading version history...
        </div>
      )}

      {error && (
        <div className="text-xs text-destructive">
          {error}
        </div>
      )}

      {!isLoading && versions.length === 0 && (
        <div className={cn('text-xs text-muted-foreground', error && 'mt-1')}>
          No version history yet. Generate or update the doc to compare.
        </div>
      )}
    </div>
  )
}
