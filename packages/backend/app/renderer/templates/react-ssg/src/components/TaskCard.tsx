import type { CSSProperties } from 'react'

export interface TaskCardProps {
  title: string
  description?: string
  status?: string
  assignee?: string
  dueDate?: string
  tags?: string[]
  className?: string
  style?: CSSProperties
}

const TaskCard = ({
  title,
  description,
  status,
  assignee,
  dueDate,
  tags = [],
  className,
  style,
}: TaskCardProps) => {
  return (
    <div className={['ic-card flex flex-col gap-3 p-4', className].filter(Boolean).join(' ')} style={style}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">{title}</h3>
          {description && <p className="text-xs text-slate-500">{description}</p>}
        </div>
        {status && <span className="rounded-full bg-slate-100 px-3 py-1 text-[10px] uppercase">{status}</span>}
      </div>
      <div className="flex flex-wrap gap-2 text-xs text-slate-500">
        {assignee && <span>Assignee: {assignee}</span>}
        {dueDate && <span>Due: {dueDate}</span>}
      </div>
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {tags.map((tag) => (
            <span key={tag} className="rounded-full bg-slate-200 px-3 py-1 text-[10px]">
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default TaskCard
