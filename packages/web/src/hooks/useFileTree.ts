import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import { notifyAsyncError } from '@/lib/notifyAsyncError'
import type { FileContent, FileTreeNode } from '../types'
import type { ExecutionEvent } from '../types/events'

interface UseFileTreeResult {
  tree: FileTreeNode[]
  selectedFile: FileContent | null
  selectFile: (path: string) => Promise<void>
  isLoading: boolean
  isContentLoading: boolean
  error: Error | null
  refresh: () => Promise<void>
}

export function useFileTree(sessionId: string): UseFileTreeResult {
  const [tree, setTree] = useState<FileTreeNode[]>([])
  const [selectedFile, setSelectedFile] = useState<FileContent | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isContentLoading, setIsContentLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [contentCache, setContentCache] = useState<Record<string, FileContent>>({})

  useEffect(() => {
    setTree([])
    setSelectedFile(null)
    setContentCache({})
    setError(null)
    setIsLoading(Boolean(sessionId))
  }, [sessionId])

  const fetchTree = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)
      const response = await api.files.getTree(sessionId)
      setTree(response.tree)
    } catch (err) {
      setError(err as Error)
      notifyAsyncError(err, {
        title: 'Failed to load files',
        loggerPrefix: 'Failed to fetch file tree:',
      })
    } finally {
      setIsLoading(false)
    }
  }, [sessionId])

  const refreshTree = useCallback(async () => {
    setContentCache({})
    setSelectedFile(null)
    await fetchTree()
  }, [fetchTree])

  const selectFile = useCallback(
    async (path: string) => {
      // Check cache first
      if (contentCache[path]) {
        setSelectedFile(contentCache[path])
        return
      }

      try {
        setIsContentLoading(true)
        setError(null)
        const content = await api.files.getContent(sessionId, path)
        setSelectedFile(content)
        setContentCache((prev) => ({ ...prev, [path]: content }))
      } catch (err) {
        setError(err as Error)
        notifyAsyncError(err, {
          title: 'Failed to load file content',
          loggerPrefix: 'Failed to fetch file content:',
        })
      } finally {
        setIsContentLoading(false)
      }
    },
    [sessionId, contentCache]
  )

  useEffect(() => {
    fetchTree()
  }, [fetchTree])

  useEffect(() => {
    if (!sessionId) return

    const handleBuildEvent = (event: Event) => {
      const customEvent = event as CustomEvent<ExecutionEvent>
      const detail = customEvent.detail
      if (!detail || typeof detail !== 'object') return
      if (detail.type !== 'build_complete') return

      const eventSessionId = (detail as { session_id?: unknown }).session_id
      if (typeof eventSessionId === 'string' && eventSessionId !== sessionId) return

      void refreshTree()
    }

    window.addEventListener('build-event', handleBuildEvent)
    return () => window.removeEventListener('build-event', handleBuildEvent)
  }, [refreshTree, sessionId])

  return {
    tree,
    selectedFile,
    selectFile,
    isLoading,
    isContentLoading,
    error,
    refresh: refreshTree,
  }
}
