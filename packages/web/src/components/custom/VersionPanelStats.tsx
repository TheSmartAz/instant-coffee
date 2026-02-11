import type { ComponentType } from 'react'

export type VersionPanelType = 'page' | 'snapshot' | 'product-doc'

export interface VersionPanelStat {
  label: string
  value: string
}

interface VersionPanelStatsProps {
  isCollapsed: boolean
  panelType: VersionPanelType
  countLabel: string
  icon: ComponentType<{ className?: string }>
  contextLabel: string
  contextValue: string
  subtitle: string
  stats: VersionPanelStat[]
}

export function VersionPanelStats({
  isCollapsed,
  panelType,
  countLabel,
  icon: Icon,
  contextLabel,
  contextValue,
  subtitle,
  stats,
}: VersionPanelStatsProps) {
  if (isCollapsed) {
    return (
      <div className="flex flex-1 flex-col items-center justify-between py-4">
        <div className="flex flex-col items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-muted/60 text-foreground">
            <Icon className="h-5 w-5" />
          </div>
          <div className="flex flex-col items-center gap-1 text-[10px] text-muted-foreground">
            <span className="uppercase tracking-[0.2em]">Focus</span>
            <span className="rounded-full bg-muted px-2 py-0.5 text-foreground">{countLabel}</span>
          </div>
        </div>
        <div className="text-[10px] text-muted-foreground">
          {panelType === 'snapshot' ? 'Snapshots' : 'Versions'}
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-2xl border border-border/70 bg-background/80 p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Icon className="h-3.5 w-3.5" />
            <span>{contextLabel}</span>
          </div>
          <div className="text-sm font-semibold text-foreground truncate">{contextValue}</div>
          <div className="text-xs text-muted-foreground">{subtitle}</div>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="rounded-xl border border-border/60 bg-muted/40 px-2 py-2 text-center"
          >
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
              {stat.label}
            </div>
            <div className="text-sm font-semibold text-foreground">{stat.value}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
