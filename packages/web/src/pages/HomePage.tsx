import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { ProjectCard } from '@/components/custom/ProjectCard'
import { Header } from '@/components/Layout/Header'
import { useProjects } from '@/hooks/useProjects'

export function HomePage() {
  const [inputValue, setInputValue] = React.useState('')
  const [isManaging, setIsManaging] = React.useState(false)
  const [selectedIds, setSelectedIds] = React.useState<Set<string>>(new Set())
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false)
  const [pendingDeleteIds, setPendingDeleteIds] = React.useState<string[]>([])
  const [pinnedIds, setPinnedIds] = React.useState<string[]>(() => {
    if (typeof window === 'undefined') return []
    try {
      const stored = window.localStorage.getItem('pinnedProjects')
      if (!stored) return []
      const parsed = JSON.parse(stored)
      return Array.isArray(parsed) ? parsed.filter((id) => typeof id === 'string') : []
    } catch {
      return []
    }
  })
  const navigate = useNavigate()
  const {
    projects,
    isLoading,
    isCreating,
    error,
    createProject,
    deleteProjects,
  } = useProjects()

  const handleCreate = async () => {
    if (!inputValue.trim()) return
    const created = await createProject(inputValue.trim())
    setInputValue('')
    if (created?.id) {
      navigate(`/project/${created.id}`)
    } else {
      navigate('/project/new')
    }
  }

  React.useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem('pinnedProjects', JSON.stringify(pinnedIds))
  }, [pinnedIds])

  React.useEffect(() => {
    if (!isManaging && selectedIds.size > 0) {
      setSelectedIds(new Set())
    }
  }, [isManaging, selectedIds.size])

  React.useEffect(() => {
    setPinnedIds((prev) => {
      const projectIds = new Set(projects.map((project) => project.id))
      const next = prev.filter((id) => projectIds.has(id))
      return next.length === prev.length ? prev : next
    })
  }, [projects])

  const pinnedSet = React.useMemo(() => new Set(pinnedIds), [pinnedIds])
  const pinnedProjects = React.useMemo(
    () => projects.filter((project) => pinnedSet.has(project.id)),
    [projects, pinnedSet]
  )
  const unpinnedProjects = React.useMemo(
    () => projects.filter((project) => !pinnedSet.has(project.id)),
    [projects, pinnedSet]
  )
  const selectedCount = selectedIds.size
  const selectedPinnedCount = React.useMemo(() => {
    let count = 0
    selectedIds.forEach((id) => {
      if (pinnedSet.has(id)) count += 1
    })
    return count
  }, [selectedIds, pinnedSet])
  const selectedUnpinnedCount = selectedCount - selectedPinnedCount

  const toggleSelected = (id: string, checked: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) {
        next.add(id)
      } else {
        next.delete(id)
      }
      return next
    })
  }

  const handleOpenDeleteDialog = () => {
    if (selectedIds.size === 0) return
    setPendingDeleteIds(Array.from(selectedIds))
    setDeleteDialogOpen(true)
  }

  const handleConfirmDelete = async () => {
    if (pendingDeleteIds.length === 0) return
    await deleteProjects(pendingDeleteIds)
    setPinnedIds((prev) => prev.filter((id) => !pendingDeleteIds.includes(id)))
    setSelectedIds(new Set())
    setPendingDeleteIds([])
    setDeleteDialogOpen(false)
  }

  const handleCancelDelete = () => {
    setDeleteDialogOpen(false)
    setPendingDeleteIds([])
  }

  const handleStickToTop = () => {
    if (selectedIds.size === 0) return
    setPinnedIds((prev) => {
      const existing = new Set(prev)
      const next = [...prev]
      projects.forEach((project) => {
        if (selectedIds.has(project.id) && !existing.has(project.id)) {
          existing.add(project.id)
          next.push(project.id)
        }
      })
      return next
    })
    setSelectedIds(new Set())
  }

  const handleUnstick = () => {
    if (selectedPinnedCount === 0) return
    setPinnedIds((prev) => prev.filter((id) => !selectedIds.has(id)))
    setSelectedIds(new Set())
  }

  return (
    <div className="flex min-h-screen flex-col animate-in fade-in">
      <Header />
      <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-12 px-6 py-12">
        <section className="flex flex-col items-center gap-6 text-center">
          <div className="text-3xl font-semibold text-foreground">
            What would you like to create today?
          </div>
          <div className="flex w-full max-w-xl flex-col gap-3 sm:flex-row">
            <Input
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              placeholder="Describe your next mobile experience..."
              className="h-12 text-sm"
            />
            <Button className="h-12 px-6" onClick={handleCreate} disabled={isCreating}>
              {isCreating ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Creating
                </span>
              ) : (
                'Create →'
              )}
            </Button>
          </div>
          {error ? (
            <div className="text-xs text-destructive">{error}</div>
          ) : null}
        </section>

        {pinnedProjects.length > 0 ? (
          <section className="space-y-4">
            <div className="text-lg font-semibold text-foreground">Stick to Top</div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {pinnedProjects.map((project) => (
                <ProjectCard
                  key={project.id}
                  {...project}
                  onClick={isManaging ? undefined : () => navigate(`/project/${project.id}`)}
                  selectable={isManaging}
                  selected={selectedIds.has(project.id)}
                  onSelectChange={(checked) => toggleSelected(project.id, checked)}
                  badgeLabel="Stick to Top"
                />
              ))}
            </div>
          </section>
        ) : null}

        <section className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-lg font-semibold text-foreground">Your Projects</div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant={isManaging ? 'secondary' : 'outline'}
                size="sm"
                onClick={() => setIsManaging((prev) => !prev)}
              >
                {isManaging ? 'Done' : 'Manage'}
              </Button>
              {isManaging ? (
                <>
                  <Button
                    variant="destructive"
                    size="sm"
                    disabled={selectedCount === 0}
                    onClick={handleOpenDeleteDialog}
                  >
                    Delete
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={selectedUnpinnedCount === 0}
                    onClick={handleStickToTop}
                  >
                    Stick to Top
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={selectedPinnedCount === 0}
                    onClick={handleUnstick}
                  >
                    Unstick
                  </Button>
                </>
              ) : null}
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {isLoading
              ? Array.from({ length: 6 }).map((_, index) => (
                  <Skeleton key={index} className="h-[320px] w-full rounded-xl" />
                ))
              : unpinnedProjects.map((project) => (
                  <ProjectCard
                    key={project.id}
                    {...project}
                    onClick={isManaging ? undefined : () => navigate(`/project/${project.id}`)}
                    selectable={isManaging}
                    selected={selectedIds.has(project.id)}
                    onSelectChange={(checked) => toggleSelected(project.id, checked)}
                  />
                ))}
          </div>
          {!isLoading && projects.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border p-6 text-sm text-muted-foreground">
              No projects yet. Start by describing your first mobile experience above.
            </div>
          ) : null}
        </section>
      </div>
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete projects?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete {pendingDeleteIds.length}{' '}
              {pendingDeleteIds.length === 1 ? 'project' : 'projects'}. This action cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={handleCancelDelete}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
