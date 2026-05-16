import { useEffect, useState } from 'react'
import { FileTree } from './FileTree'
import { FileViewer } from './FileViewer'
import { useFileTree } from '../../hooks/useFileTree'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { Button } from '../ui/button'
import { RefreshCw } from 'lucide-react'

interface CodePanelProps {
  sessionId: string
  active?: boolean
}

export function CodePanel({ sessionId, active = true }: CodePanelProps) {
  const { tree, selectedFile, selectFile, isLoading, isContentLoading, error, refresh } =
    useFileTree(sessionId)
  const [selectedPath, setSelectedPath] = useState<string | null>(null)

  const handleSelectFile = async (path: string) => {
    setSelectedPath(path)
    await selectFile(path)
  }

  const handleRefresh = async () => {
    await refresh()
    if (selectedPath) {
      await selectFile(selectedPath)
    }
  }

  useEffect(() => {
    if (!active) return
    void refresh()
  }, [active, refresh])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <p className="text-sm text-muted-foreground">Failed to load files</p>
        <Button variant="outline" size="sm" onClick={handleRefresh}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Retry
        </Button>
      </div>
    )
  }

  if (tree.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <p className="text-sm text-muted-foreground">No files yet</p>
        <Button variant="outline" size="sm" onClick={handleRefresh}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>
    )
  }

  return (
    <div className="code-panel flex h-full overflow-hidden">
      <div
        className={`file-tree-wrapper w-full shrink-0 overflow-hidden border-r bg-background flex-col md:flex md:w-56 ${
          selectedPath ? 'hidden md:flex' : 'flex'
        }`}
      >
        <div className="p-2 border-b flex items-center justify-between">
          <span className="text-xs font-medium text-muted-foreground uppercase">Files</span>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={handleRefresh}
            title="Refresh"
            aria-label="Refresh files"
          >
            <RefreshCw className="h-3 w-3" />
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto">
          <FileTree tree={tree} selectedPath={selectedPath} onSelectFile={handleSelectFile} />
        </div>
      </div>
      <div className={`min-w-0 flex-1 overflow-hidden ${selectedPath ? 'block' : 'hidden md:block'}`}>
        {selectedPath ? (
          <div className="flex items-center border-b bg-muted/30 px-2 py-2 md:hidden">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 gap-2 px-2 text-xs"
              onClick={() => setSelectedPath(null)}
            >
              <ArrowLeft className="h-4 w-4" />
              Files
            </Button>
          </div>
        ) : null}
        <FileViewer file={selectedFile} isLoading={isContentLoading} />
      </div>
    </div>
  )
}
