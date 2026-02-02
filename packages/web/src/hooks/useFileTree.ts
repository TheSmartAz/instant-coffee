import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { FileContent, FileTreeNode } from '../types'

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

  const fetchTree = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)
      const response = await api.files.getTree(sessionId)
      setTree(response.tree)
    } catch (err) {
      setError(err as Error)
      console.error('Failed to fetch file tree:', err)
    } finally {
      setIsLoading(false)
    }
  }, [sessionId])

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
        console.error('Failed to fetch file content:', err)
      } finally {
        setIsContentLoading(false)
      }
    },
    [sessionId, contentCache]
  )

  useEffect(() => {
    fetchTree()
  }, [fetchTree])

  return {
    tree,
    selectedFile,
    selectFile,
    isLoading,
    isContentLoading,
    error,
    refresh: fetchTree,
  }
}
