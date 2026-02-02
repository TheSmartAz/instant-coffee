import * as React from 'react'
import { api } from '@/api/client'
import { toast } from '@/hooks/use-toast'
import type { Project } from '@/types'

type ApiSession = {
  id: string
  title?: string
  updated_at?: string
  updatedAt?: string
  version_count?: number
  versionCount?: number
  message_count?: number
  thumbnail?: string
}

const toDate = (value?: string) => (value ? new Date(value) : new Date())

const mapSessionToProject = (session: ApiSession): Project => ({
  id: session.id,
  name: session.title ?? 'Untitled project',
  updatedAt: toDate(session.updated_at ?? session.updatedAt),
  versionCount: session.version_count ?? session.versionCount ?? 0,
  messageCount: session.message_count,
  thumbnail: session.thumbnail,
})

export function useProjects() {
  const [projects, setProjects] = React.useState<Project[]>([])
  const [isLoading, setIsLoading] = React.useState(true)
  const [isCreating, setIsCreating] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const refresh = React.useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await api.sessions.list()
      const sessions = Array.isArray(response)
        ? response
        : response?.sessions ?? []
      setProjects((sessions as ApiSession[]).map(mapSessionToProject))
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load projects'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [])

  React.useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const response = await api.sessions.list()
        if (!active) return
        const sessions = Array.isArray(response)
          ? response
          : response?.sessions ?? []
        setProjects((sessions as ApiSession[]).map(mapSessionToProject))
      } catch (err) {
        if (!active) return
        const message = err instanceof Error ? err.message : 'Failed to load projects'
        setError(message)
      } finally {
        if (active) setIsLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [])

  const createProject = React.useCallback(async (title: string) => {
    setIsCreating(true)
    setError(null)
    try {
      const response = await api.sessions.create({ title })
      const session = (response as ApiSession | undefined) ?? undefined
      if (session?.id) {
        const project = mapSessionToProject(session)
        setProjects((prev) => [project, ...prev])
        toast({ title: 'Project created', description: project.name })
        return project
      }
      await refresh()
      return undefined
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create project'
      setError(message)
      toast({ title: 'Failed to create project', description: message })
      return undefined
    } finally {
      setIsCreating(false)
    }
  }, [refresh])

  const deleteProjects = React.useCallback(async (ids: string[]) => {
    if (ids.length === 0) return
    setError(null)
    try {
      await Promise.all(ids.map((id) => api.sessions.remove(id)))
      setProjects((prev) => prev.filter((project) => !ids.includes(project.id)))
      toast({
        title: 'Projects deleted',
        description: `${ids.length} project${ids.length === 1 ? '' : 's'} removed.`,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete projects'
      setError(message)
      toast({ title: 'Failed to delete projects', description: message })
      await refresh()
    }
  }, [refresh])

  return {
    projects,
    isLoading,
    isCreating,
    error,
    refresh,
    createProject,
    deleteProjects,
    setProjects,
  }
}
