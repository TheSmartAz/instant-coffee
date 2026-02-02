import { useState } from 'react'
import { ChevronRight, ChevronDown, File, FolderOpen, Folder } from 'lucide-react'
import { type FileTreeNode } from '../../types'
import { cn } from '../../lib/utils'

interface FileTreeProps {
  tree: FileTreeNode[]
  selectedPath: string | null
  onSelectFile: (path: string) => void
}

export function FileTree({ tree, selectedPath, onSelectFile }: FileTreeProps) {
  if (tree.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
        No files yet
      </div>
    )
  }

  return (
    <div className="file-tree">
      {tree.map((node) => (
        <FileTreeNode
          key={node.path}
          node={node}
          selectedPath={selectedPath}
          onSelectFile={onSelectFile}
          depth={0}
        />
      ))}
    </div>
  )
}

interface FileTreeNodeProps {
  node: FileTreeNode
  selectedPath: string | null
  onSelectFile: (path: string) => void
  depth: number
}

function FileTreeNode({ node, selectedPath, onSelectFile, depth }: FileTreeNodeProps) {
  const [expanded, setExpanded] = useState(depth === 0)

  const handleClick = () => {
    if (node.type === 'directory') {
      setExpanded((prev) => !prev)
    } else {
      onSelectFile(node.path)
    }
  }

  const isSelected = node.path === selectedPath
  const isDirectory = node.type === 'directory'

  return (
    <div>
      <div
        className={cn(
          'tree-item flex items-center gap-1.5 py-1.5 px-2 cursor-pointer text-sm rounded-sm transition-colors',
          'hover:bg-accent/50',
          isSelected && 'bg-accent text-accent-foreground',
          isDirectory && 'font-medium'
        )}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        onClick={handleClick}
      >
        {isDirectory ? (
          expanded ? (
            <ChevronDown className="h-4 w-4 shrink-0" />
          ) : (
            <ChevronRight className="h-4 w-4 shrink-0" />
          )
        ) : null}
        {getFileIcon(node, isDirectory, expanded)}
        <span className="truncate">{node.name}</span>
        {node.size !== undefined && !isDirectory && (
          <span className="ml-auto text-xs text-muted-foreground tabular-nums">
            {formatSize(node.size)}
          </span>
        )}
      </div>
      {isDirectory && expanded && node.children && (
        <div>
          {node.children.map((child) => (
            <FileTreeNode
              key={child.path}
              node={child}
              selectedPath={selectedPath}
              onSelectFile={onSelectFile}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function getFileIcon(
  node: FileTreeNode,
  isDirectory: boolean,
  expanded: boolean
): React.ReactNode {
  if (isDirectory) {
    return expanded ? (
      <FolderOpen className="h-4 w-4 shrink-0 text-blue-500" />
    ) : (
      <Folder className="h-4 w-4 shrink-0 text-blue-500" />
    )
  }

  const ext = node.name.split('.').pop()?.toLowerCase()
  const iconClassName = 'h-4 w-4 shrink-0'

  switch (ext) {
    case 'html':
      return <File className={cn(iconClassName, 'text-orange-500')} />
    case 'css':
      return <File className={cn(iconClassName, 'text-blue-500')} />
    case 'js':
      return <File className={cn(iconClassName, 'text-yellow-500')} />
    case 'md':
      return <File className={cn(iconClassName, 'text-purple-500')} />
    default:
      return <File className={cn(iconClassName, 'text-gray-500')} />
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}
