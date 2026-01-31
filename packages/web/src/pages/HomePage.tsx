import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ProjectCard } from '@/components/custom/ProjectCard'
import { Header } from '@/components/Layout/Header'
import { useProjects } from '@/hooks/useProjects'

export function HomePage() {
  const [inputValue, setInputValue] = React.useState('')
  const navigate = useNavigate()
  const { projects, isLoading, isCreating, error, createProject } = useProjects()

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

        <section className="space-y-4">
          <div className="text-lg font-semibold text-foreground">Your Projects</div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {isLoading
              ? Array.from({ length: 6 }).map((_, index) => (
                  <Skeleton key={index} className="h-[320px] w-full rounded-xl" />
                ))
              : projects.map((project) => (
                  <ProjectCard
                    key={project.id}
                    {...project}
                    onClick={() => navigate(`/project/${project.id}`)}
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
    </div>
  )
}
