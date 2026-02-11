import { FileText, FilePlus, FileEdit, FileX } from 'lucide-react'
import type { FileChange } from '@/types/events'

const ACTION_CONFIG: Record<
  string,
  { icon: typeof FileText; label: string; className: string }
> = {
  created: {
    icon: FilePlus,
    label: 'Created',
    className: 'text-emerald-500',
  },
  modified: {
    icon: FileEdit,
    label: 'Modified',
    className: 'text-blue-500',
  },
  deleted: {
    icon: FileX,
    label: 'Deleted',
    className: 'text-red-500',
  },
}

interface FileChangeCardProps {
  files: FileChange[]
  onFileClick?: (path: string) => void
}

export function FileChangeCard({ files, onFileClick }: FileChangeCardProps) {
  if (!files.length) return null

  return (
    <div className="mt-2 rounded-lg border border-border/60 bg-muted/30 p-3">
      <div className="mb-1.5 text-xs font-medium text-muted-foreground">
        Files changed ({files.length})
      </div>
      <div className="space-y-1">
        {files.map((file, i) => {
          const config = ACTION_CONFIG[file.action] ?? ACTION_CONFIG.modified
          const Icon = config.icon
          const fileName = file.path.split('/').pop() ?? file.path

          return (
            <button
              key={`${file.path}-${i}`}
              type="button"
              onClick={() => onFileClick?.(file.path)}
              className="flex w-full items-center gap-2 rounded px-1.5 py-1 text-left text-xs hover:bg-muted/60 transition-colors"
            >
              <Icon className={`h-3.5 w-3.5 shrink-0 ${config.className}`} />
              <span className="truncate font-mono text-foreground">
                {fileName}
              </span>
              <span className={`ml-auto shrink-0 text-[10px] font-medium ${config.className}`}>
                {config.label}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
