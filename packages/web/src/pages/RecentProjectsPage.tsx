import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowDownAZ,
  ArrowUpAZ,
  Loader2,
  Search,
  Sparkles,
  Trash2,
} from 'lucide-react'
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

export function RecentProjectsPage() {
  const navigate = useNavigate()
  const [isManaging, setIsManaging] = React.useState(false)
  const [selectedIds, setSelectedIds] = React.useState<Set<string>>(new Set())
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false)
  const [searchQuery, setSearchQuery] = React.useState('')
  const [sortOrder, setSortOrder] = React.useState<'desc' | 'asc'>('desc')
  const [pendingDeleteIds, setPendingDeleteIds] = React.useState<string[]>([])
  const [isDeleting, setIsDeleting] = React.useState(false)
  const {
    projects,
    isLoading,
    deleteProjects,
  } = useProjects()

  React.useEffect(() => {
    if (!isManaging && selectedIds.size > 0) {
      setSelectedIds(new Set())
    }
  }, [isManaging, selectedIds.size])

  const filteredProjects = React.useMemo(() => {
    let filtered = [...projects]
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
  }, [projects, searchQuery, sortOrder])

  const selectedCount = selectedIds.size
  const hasProjects = projects.length > 0
  const hasSearchQuery = searchQuery.trim().length > 0

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

  return (
    <AppLayout className="animate-in fade-in">
      <Header />
      <ContentArea className="mx-auto flex w-full max-w-6xl flex-col gap-6 overflow-x-hidden px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
        <section className="flex flex-col gap-4 border-b border-border pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <div className="text-3xl font-semibold tracking-tight text-foreground">
              Recent projects
            </div>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              Search, sort, open, or bulk-manage generated projects.
            </p>
          </div>
          <div className="flex min-w-0 flex-wrap items-center gap-2 lg:justify-end">
            <div className="relative min-w-0 flex-1 sm:flex-none">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search projects..."
                className="h-8 w-full min-w-0 pl-8 text-xs sm:w-56"
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
            ) : null}
          </div>
        </section>

        <section className="space-y-4">
          <p className="text-sm text-muted-foreground">
            {hasProjects
              ? `${filteredProjects.length} visible ${filteredProjects.length === 1 ? 'project' : 'projects'}${hasSearchQuery ? ' for this search' : ''}.`
              : 'Your generated projects will appear here.'}
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {isLoading
              ? Array.from({ length: 6 }).map((_, index) => (
                  <div key={index} className="rounded-xl border border-border bg-card p-4 shadow-sm">
                    <Skeleton className="mx-auto h-[250px] w-[150px] rounded-[28px]" />
                    <Skeleton className="mt-4 h-4 w-3/4" />
                    <Skeleton className="mt-2 h-3 w-1/2" />
                  </div>
                ))
              : filteredProjects.map((project) => (
                  <ProjectCard
                    key={project.id}
                    id={project.id}
                    name={project.name}
                    updatedAt={project.updatedAt}
                    versionCount={project.versionCount}
                    thumbnail={project.thumbnail ?? undefined}
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
                Start from the homepage prompt box to create your first project.
              </p>
            </div>
          ) : null}
          {!isLoading && projects.length > 0 && filteredProjects.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-card p-8 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
                <Search className="h-5 w-5" />
              </div>
              <div className="mt-4 text-base font-semibold text-foreground">
                No matching recent projects
              </div>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
                Try a different search, or clear the search field to see your full recent list.
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
