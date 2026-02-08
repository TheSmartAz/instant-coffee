import type { CSSProperties } from 'react'

export interface TimelineCardProps {
  title: string
  time?: string
  description?: string
  badge?: string
  status?: string
  className?: string
  style?: CSSProperties
}

const TimelineCard = ({
  title,
  time,
  description,
  badge,
  status,
  className,
  style,
}: TimelineCardProps) => {
  return (
    <div className={['ic-card flex flex-col gap-2 p-4', className].filter(Boolean).join(' ')} style={style}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold">{title}</h3>
          {time && <p className="text-xs text-slate-400">{time}</p>}
        </div>
        {badge && <span className="rounded-full bg-brand-100 px-3 py-1 text-[10px] text-brand-700">{badge}</span>}
      </div>
      {description && <p className="text-xs text-slate-600">{description}</p>}
      {status && <p className="text-[10px] uppercase text-slate-400">{status}</p>}
    </div>
  )
}

export default TimelineCard
