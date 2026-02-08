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

const PROJECTS_CACHE_KEY = 'instant-coffee:projects-cache'
const PROJECTS_CACHE_TTL_MS = 30 * 60 * 1000

type CachedProject = {
  id: string
  name: string
  updatedAt: string
  versionCount: number
  messageCount?: number
  thumbnail?: string
}

type ProjectsCache = {
  savedAt: number
  projects: CachedProject[]
}

const loadProjectsCache = (): Project[] => {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(PROJECTS_CACHE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as ProjectsCache
    if (!parsed || !Array.isArray(parsed.projects)) return []
    if (
      typeof parsed.savedAt === 'number' &&
      Date.now() - parsed.savedAt > PROJECTS_CACHE_TTL_MS
    ) {
      return []
    }
    return parsed.projects.map((project) => ({
      id: project.id,
      name: project.name,
      updatedAt: toDate(project.updatedAt),
      versionCount: project.versionCount,
      messageCount: project.messageCount,
      thumbnail: project.thumbnail,
    }))
  } catch {
    return []
  }
}

const saveProjectsCache = (projects: Project[]) => {
  if (typeof window === 'undefined') return
  try {
    const payload: ProjectsCache = {
      savedAt: Date.now(),
      projects: projects.map((project) => ({
        id: project.id,
        name: project.name,
        updatedAt: project.updatedAt.toISOString(),
        versionCount: project.versionCount,
        messageCount: project.messageCount,
        thumbnail: project.thumbnail,
      })),
    }
    window.localStorage.setItem(PROJECTS_CACHE_KEY, JSON.stringify(payload))
  } catch {
    // ignore cache failures
  }
}

const mapSessionToProject = (session: ApiSession): Project => ({
  id: session.id,
  name: session.title ?? 'Untitled project',
  updatedAt: toDate(session.updated_at ?? session.updatedAt),
  versionCount: session.version_count ?? session.versionCount ?? 0,
  messageCount: session.message_count,
  thumbnail: session.thumbnail,
})

export function useProjects() {
  const cachedProjectsRef = React.useRef<Project[]>(loadProjectsCache())
  const cachedProjects = cachedProjectsRef.current

  const [projects, setProjects] = React.useState<Project[]>(cachedProjects)
  const [isLoading, setIsLoading] = React.useState(() => cachedProjects.length === 0)
  const [isCreating, setIsCreating] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const refresh = React.useCallback(async () => {
    if (projects.length === 0) setIsLoading(true)
    setError(null)
    try {
      const response = await api.sessions.list()
      const sessions = Array.isArray(response)
        ? response
        : response?.sessions ?? []
      const nextProjects = (sessions as ApiSession[]).map(mapSessionToProject)
      setProjects(nextProjects)
      saveProjectsCache(nextProjects)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load projects'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [projects.length])

  React.useEffect(() => {
    let active = true
    const load = async () => {
      if (cachedProjectsRef.current.length === 0) setIsLoading(true)
      try {
        const response = await api.sessions.list()
        if (!active) return
        const sessions = Array.isArray(response)
          ? response
          : response?.sessions ?? []
        const nextProjects = (sessions as ApiSession[]).map(mapSessionToProject)
        setProjects(nextProjects)
        saveProjectsCache(nextProjects)
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
        setProjects((prev) => {
          const next = [project, ...prev]
          saveProjectsCache(next)
          return next
        })
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
      setProjects((prev) => {
        const next = prev.filter((project) => !ids.includes(project.id))
        saveProjectsCache(next)
        return next
      })
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
