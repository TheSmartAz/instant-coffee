import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowDownAZ,
  ArrowUpAZ,
  CheckCircle2,
  Clock3,
  Layers3,
  Loader2,
  Pin,
  Plus,
  Search,
  Sparkles,
  Trash2,
  Wand2,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
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
import { AppLayout, ContentArea, Header } from '@/components/Layout'
import { useProjects } from '@/hooks/useProjects'

const quickStartTemplates = [
  {
    title: 'Product launch',
    description: 'A polished mobile landing page for a new product announcement.',
    prompt: 'Create a mobile-first product launch page with a sharp hero, feature proof, testimonials, pricing, and a final call to action.',
    icon: Sparkles,
  },
  {
    title: 'Event signup',
    description: 'Registration flow, schedule highlights, and attendee trust signals.',
    prompt: 'Create a mobile event signup page with event details, agenda, speaker highlights, registration form, and confirmation-focused call to action.',
    icon: Clock3,
  },
  {
    title: 'Local service',
    description: 'Service overview, booking prompts, social proof, and location cues.',
    prompt: 'Create a mobile local service page with service packages, reviews, service area, booking CTA, and contact details.',
    icon: Wand2,
  },
]

export function HomePage() {
  const [inputValue, setInputValue] = React.useState('')
  const [isManaging, setIsManaging] = React.useState(false)
  const [selectedIds, setSelectedIds] = React.useState<Set<string>>(new Set())
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false)
  const [searchQuery, setSearchQuery] = React.useState('')
  const [sortOrder, setSortOrder] = React.useState<'desc' | 'asc'>('desc')
  const [pendingDeleteIds, setPendingDeleteIds] = React.useState<string[]>([])
  const [isDeleting, setIsDeleting] = React.useState(false)
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
    refresh,
    createProject,
    deleteProjects,
  } = useProjects()

  const handleCreate = async (value = inputValue) => {
    const title = value.trim()
    if (!title) return
    const created = await createProject(title)
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
  const unpinnedProjects = React.useMemo(() => {
    let filtered = projects.filter((project) => !pinnedSet.has(project.id))
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase()
      filtered = filtered.filter((project) =>
        project.name.toLowerCase().includes(q)
      )
    }
    filtered.sort((a, b) =>
      sortOrder === 'desc'
        ? b.updatedAt.getTime() - a.updatedAt.getTime()
        : a.updatedAt.getTime() - b.updatedAt.getTime()
    )
    return filtered
  }, [projects, pinnedSet, searchQuery, sortOrder])
  const selectedCount = selectedIds.size
  const selectedPinnedCount = React.useMemo(() => {
    let count = 0
    selectedIds.forEach((id) => {
      if (pinnedSet.has(id)) count += 1
    })
    return count
  }, [selectedIds, pinnedSet])
  const selectedUnpinnedCount = selectedCount - selectedPinnedCount
  const hasProjects = projects.length > 0
  const hasSearchQuery = searchQuery.trim().length > 0
  const hiddenPinnedCount = React.useMemo(() => {
    if (!hasSearchQuery) return 0
    const q = searchQuery.trim().toLowerCase()
    return pinnedProjects.filter((project) => !project.name.toLowerCase().includes(q)).length
  }, [hasSearchQuery, pinnedProjects, searchQuery])
  const visibleProjectCount = pinnedProjects.length + unpinnedProjects.length
  const totalVersionCount = React.useMemo(
    () => projects.reduce((total, project) => total + project.versionCount, 0),
    [projects]
  )

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
    setIsDeleting(true)
    try {
      await deleteProjects(pendingDeleteIds)
      setPinnedIds((prev) => prev.filter((id) => !pendingDeleteIds.includes(id)))
      setSelectedIds(new Set())
      setPendingDeleteIds([])
      setDeleteDialogOpen(false)
    } finally {
      setIsDeleting(false)
    }
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
    <AppLayout className="animate-in fade-in">
      <Header />
      <ContentArea className="mx-auto flex w-full max-w-6xl flex-col gap-10 overflow-x-hidden px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
        <section className="grid min-w-0 gap-6 rounded-xl border border-border bg-card p-4 shadow-sm sm:gap-8 sm:p-8 lg:grid-cols-[minmax(0,1.3fr)_minmax(280px,360px)] lg:items-center">
          <div className="min-w-0 space-y-6">
            <div className="space-y-3">
              <Badge variant="secondary" className="max-w-full gap-1.5 rounded-full px-3 py-1">
                <Sparkles className="h-3.5 w-3.5" />
                <span className="truncate">Mobile-first site generator</span>
              </Badge>
              <div className="max-w-2xl text-3xl font-semibold leading-tight text-foreground sm:text-4xl">
                Start with a prompt, then keep every project moving.
              </div>
              <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
                Create a new mobile experience or jump back into recent work with pins,
                search, sorting, and bulk management intact.
              </p>
            </div>
            <div className="flex w-full max-w-2xl flex-col gap-3 sm:flex-row">
              <Input
                value={inputValue}
                onChange={(event) => setInputValue(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    void handleCreate()
                  }
                }}
                placeholder="Describe your next mobile experience..."
                className="h-12 min-w-0 text-sm"
              />
              <Button className="h-12 shrink-0 px-6" onClick={() => void handleCreate()} disabled={isCreating}>
                {isCreating ? (
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Creating
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-2">
                    <Plus className="h-4 w-4" />
                    Create
                  </span>
                )}
              </Button>
            </div>
            {error ? (
              <div className="flex flex-col gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive sm:flex-row sm:items-center sm:justify-between">
                <span>{error}</span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="border-destructive/30 text-destructive hover:text-destructive"
                  onClick={() => void refresh()}
                >
                  Retry
                </Button>
              </div>
            ) : null}
          </div>
          <div className="grid min-w-0 gap-3 sm:grid-cols-3 lg:grid-cols-1">
            <div className="rounded-lg border border-border bg-background p-4">
              <div className="flex min-w-0 items-center justify-between gap-3">
                <span className="truncate text-sm text-muted-foreground">Projects</span>
                <Layers3 className="h-4 w-4 shrink-0 text-muted-foreground" />
              </div>
              <div className="mt-2 truncate text-2xl font-semibold text-foreground">{projects.length}</div>
            </div>
            <div className="rounded-lg border border-border bg-background p-4">
              <div className="flex min-w-0 items-center justify-between gap-3">
                <span className="truncate text-sm text-muted-foreground">Pinned</span>
                <Pin className="h-4 w-4 shrink-0 text-muted-foreground" />
              </div>
              <div className="mt-2 truncate text-2xl font-semibold text-foreground">{pinnedProjects.length}</div>
            </div>
            <div className="rounded-lg border border-border bg-background p-4">
              <div className="flex min-w-0 items-center justify-between gap-3">
                <span className="truncate text-sm text-muted-foreground">Versions</span>
                <CheckCircle2 className="h-4 w-4 shrink-0 text-muted-foreground" />
              </div>
              <div className="mt-2 truncate text-2xl font-semibold text-foreground">{totalVersionCount}</div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex min-w-0 items-end justify-between gap-3">
            <div className="min-w-0">
              <div className="text-lg font-semibold text-foreground">Quick start templates</div>
              <p className="mt-1 text-sm text-muted-foreground">
                Start from a useful prompt, then refine it in the project workspace.
              </p>
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            {quickStartTemplates.map((template) => {
              const Icon = template.icon
              return (
                <button
                  key={template.title}
                  type="button"
                  className="group min-w-0 rounded-lg border border-border bg-card p-4 text-left shadow-sm transition hover:-translate-y-[1px] hover:shadow-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={() => void handleCreate(template.prompt)}
                  disabled={isCreating}
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-secondary text-secondary-foreground">
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="min-w-0 truncate font-medium text-foreground">{template.title}</span>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-muted-foreground">
                    {template.description}
                  </p>
                </button>
              )
            })}
          </div>
        </section>

        {pinnedProjects.length > 0 ? (
          <section className="space-y-4">
            <div className="flex min-w-0 items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-lg font-semibold text-foreground">Pinned projects</div>
                <p className="mt-1 text-sm text-muted-foreground">
                  High-priority work stays visible while you manage the rest.
                </p>
              </div>
              <Badge variant="outline" className="shrink-0 rounded-full">
                {pinnedProjects.length}
              </Badge>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {pinnedProjects.map((project) => (
                <ProjectCard
                  key={project.id}
                  {...project}
                  onClick={isManaging ? undefined : () => navigate(`/project/${project.id}`)}
                  selectable={isManaging}
                  selected={selectedIds.has(project.id)}
                  onSelectChange={(checked) => toggleSelected(project.id, checked)}
                  badgeLabel="Pinned"
                />
              ))}
            </div>
            {hiddenPinnedCount > 0 ? (
              <div className="text-xs text-muted-foreground">
                {hiddenPinnedCount} pinned {hiddenPinnedCount === 1 ? 'project does' : 'projects do'} not match the current search.
              </div>
            ) : null}
          </section>
        ) : null}

        <section className="space-y-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="min-w-0">
              <div className="text-lg font-semibold text-foreground">Recent projects</div>
              <p className="mt-1 text-sm text-muted-foreground">
                {hasProjects
                  ? `${visibleProjectCount} visible ${visibleProjectCount === 1 ? 'project' : 'projects'}${hasSearchQuery ? ' for this search' : ''}.`
                  : 'Your generated projects will appear here.'}
              </p>
            </div>
            <div className="flex min-w-0 flex-wrap items-center gap-2 lg:justify-end">
              <div className="relative min-w-0 flex-1 sm:flex-none">
                <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search projects..."
                  className="h-8 w-full min-w-0 pl-8 text-xs sm:w-48"
                />
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="min-w-0 text-xs"
                onClick={() => setSortOrder((prev) => (prev === 'desc' ? 'asc' : 'desc'))}
              >
                {sortOrder === 'desc' ? (
                  <>
                    <ArrowDownAZ className="h-3.5 w-3.5" />
                    <span className="truncate">Newest first</span>
                  </>
                ) : (
                  <>
                    <ArrowUpAZ className="h-3.5 w-3.5" />
                    <span className="truncate">Oldest first</span>
                  </>
                )}
              </Button>
              <Button
                variant={isManaging ? 'secondary' : 'outline'}
                size="sm"
                className="shrink-0"
                onClick={() => setIsManaging((prev) => !prev)}
              >
                {isManaging ? 'Done' : 'Manage'}
              </Button>
              {isManaging ? (
                <>
                  <Button
                    variant="destructive"
                    size="sm"
                    className="shrink-0"
                    disabled={selectedCount === 0}
                    onClick={handleOpenDeleteDialog}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Delete
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="shrink-0"
                    disabled={selectedUnpinnedCount === 0}
                    onClick={handleStickToTop}
                  >
                    <Pin className="h-3.5 w-3.5" />
                    Pin
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="shrink-0"
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
                  <div key={index} className="rounded-xl border border-border bg-card p-4 shadow-sm">
                    <Skeleton className="mx-auto h-[250px] w-[150px] rounded-[28px]" />
                    <Skeleton className="mt-4 h-4 w-3/4" />
                    <Skeleton className="mt-2 h-3 w-1/2" />
                  </div>
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
            <div className="rounded-xl border border-dashed border-border bg-card p-8 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
                <Sparkles className="h-5 w-5" />
              </div>
              <div className="mt-4 text-base font-semibold text-foreground">No projects yet</div>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
                Describe a mobile experience above or choose a quick-start template to create your first project.
              </p>
            </div>
          ) : null}
          {!isLoading && projects.length > 0 && unpinnedProjects.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-card p-8 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
                {hasSearchQuery ? <Search className="h-5 w-5" /> : <Pin className="h-5 w-5" />}
              </div>
              <div className="mt-4 text-base font-semibold text-foreground">
                {hasSearchQuery ? 'No matching recent projects' : 'All projects are pinned'}
              </div>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
                {hasSearchQuery
                  ? 'Try a different search, or clear the search field to see your full recent list.'
                  : 'Use Manage to unpin projects when you want them back in the recent list.'}
              </p>
            </div>
          ) : null}
        </section>
      </ContentArea>
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
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Deleting
                </span>
              ) : (
                'Delete'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppLayout>
  )
}
