import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Clock3,
  Sparkles,
  Wand2,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ChatInput, type ChatInputProps } from '@/components/custom/ChatInput'
import { AppLayout, ContentArea, Header } from '@/components/Layout'
import { useProjects } from '@/hooks/useProjects'
import { saveHomePrompt } from '@/lib/homePromptStorage'

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
    title: 'Portfolio',
    description: 'Personal intro, project highlights, case studies, and contact CTA.',
    prompt: 'Create a mobile personal portfolio page with a strong intro, selected projects, case study previews, skills, testimonials, and a contact call to action.',
    icon: Wand2,
  },
  {
    title: 'E-commerce product',
    description: 'Single-product story, specs, reviews, and purchase CTA.',
    prompt: 'Create a mobile e-commerce product page with product imagery, key benefits, specifications, customer reviews, shipping details, and a strong purchase call to action.',
    icon: Sparkles,
  },
  {
    title: 'Fitness coach',
    description: 'Training plans, transformation proof, coach bio, and booking CTA.',
    prompt: 'Create a mobile fitness coach page with coaching packages, transformation stories, coach credentials, client testimonials, FAQs, and a consultation booking call to action.',
    icon: Wand2,
  },
  {
    title: 'Travel itinerary',
    description: 'Destination highlights, day-by-day plan, pricing, and inquiry CTA.',
    prompt: 'Create a mobile travel itinerary page with destination highlights, a day-by-day schedule, included experiences, pricing, traveler reviews, and an inquiry call to action.',
    icon: Clock3,
  },
  {
    title: 'Newsletter signup',
    description: 'Editorial promise, reader benefits, issue previews, and subscription.',
    prompt: 'Create a mobile newsletter signup page with a clear editorial promise, reader benefits, sample issue previews, social proof, and an email subscription form.',
    icon: Sparkles,
  },
  {
    title: 'Webinar registration',
    description: 'Topic, speakers, audience fit, schedule, and registration form.',
    prompt: 'Create a mobile webinar registration page with a strong topic hook, speaker bios, agenda, ideal audience, key takeaways, date and time, and a registration form.',
    icon: Clock3,
  },
  {
    title: 'Dashboard teaser',
    description: 'Metric previews, use cases, feature modules, and trial request.',
    prompt: 'Create a mobile dashboard product teaser page with key metric previews, use cases, feature modules, workflow benefits, customer proof, and a request demo call to action.',
    icon: Clock3,
  },
]

export function HomePage() {
  const navigate = useNavigate()
  const {
    isCreating,
    error,
    refresh,
    createProject,
  } = useProjects()

  const handleCreate = React.useCallback(async (value: string) => {
    const prompt = value.trim()
    if (!prompt) return
    const created = await createProject(undefined, { initialPrompt: prompt })
    if (created?.id) {
      saveHomePrompt(created.id, prompt)
      navigate(`/project/${created.id}`)
    } else {
      navigate('/project/new')
    }
  }, [createProject, navigate])

  const handleHomeInputSend = React.useCallback<ChatInputProps['onSend']>(
    (message) => {
      void handleCreate(message)
    },
    [handleCreate]
  )

  return (
    <AppLayout className="animate-in fade-in">
      <Header />
      <ContentArea className="mx-auto flex w-full max-w-6xl flex-col gap-10 overflow-x-hidden px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
        <section className="relative flex min-h-[560px] min-w-0 flex-col overflow-hidden rounded-xl border border-border bg-card p-4 shadow-sm sm:p-8 lg:p-10">
          <div className="flex min-w-0 flex-col items-center gap-6 text-center">
            <div className="flex min-w-0 flex-col items-center space-y-4">
              <Badge variant="secondary" className="max-w-full gap-1.5 rounded-full px-3 py-1">
                <Sparkles className="h-3.5 w-3.5" />
                <span className="truncate">Mobile-first site generator</span>
              </Badge>
              <div className="text-[2rem] font-semibold leading-[1.12] tracking-tight text-foreground sm:text-[2.75rem] lg:text-[3.25rem]">
                <span className="block">Start with a prompt,</span>
                <span className="block whitespace-nowrap">then keep every project moving.</span>
              </div>
              <p className="max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">
                Create a new mobile experience or jump back into recent work with
                search, sorting, and bulk management intact.
              </p>
            </div>
            {error ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive lg:max-w-sm">
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
          <div className="flex flex-1 min-w-0 items-center justify-center pt-10 pb-0 sm:pt-12">
            <div className="w-full max-w-4xl">
              <ChatInput
                onSend={handleHomeInputSend}
                disabled={isCreating}
                placeholder="Describe your next mobile experience..."
                size="hero"
              />
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

      </ContentArea>
    </AppLayout>
  )
}
