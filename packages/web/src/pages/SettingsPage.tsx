import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Bot, KeyRound, SlidersHorizontal, Sparkles, FolderOpen } from 'lucide-react'
import { ADMIN_TOKEN_STORAGE_KEY } from '@/api/client'
import { AppLayout, ContentArea, PageHeader } from '@/components/Layout'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { useSettings } from '@/hooks/useSettings'
import { toast } from '@/hooks/use-toast'

type SettingsSection = 'account' | 'model' | 'preferences'

const LAST_PROJECT_KEY = 'instant-coffee:last-project-id'

const sections: Array<{
  id: SettingsSection
  label: string
  description: string
  icon: React.ReactNode
}> = [
  {
    id: 'account',
    label: 'Account',
    description: 'Keys and admin access',
    icon: <KeyRound className="h-4 w-4" />,
  },
  {
    id: 'model',
    label: 'Model',
    description: 'Model and sampling controls',
    icon: <Bot className="h-4 w-4" />,
  },
  {
    id: 'preferences',
    label: 'Preferences',
    description: 'Local output and save behavior',
    icon: <SlidersHorizontal className="h-4 w-4" />,
  },
]

function SectionNav({
  activeSection,
  onChange,
}: {
  activeSection: SettingsSection
  onChange: (section: SettingsSection) => void
}) {
  return (
    <Card className="border-border/70 shadow-sm">
      <CardHeader>
        <CardTitle className="text-base">Sections</CardTitle>
        <CardDescription>Jump between configuration groups.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {sections.map((section) => (
          <button
            key={section.id}
            type="button"
            onClick={() => onChange(section.id)}
            aria-current={activeSection === section.id ? 'page' : undefined}
            className={cn(
              'flex w-full items-center gap-3 rounded-xl border px-3 py-3 text-left transition',
              activeSection === section.id
                ? 'border-primary/30 bg-primary/5 text-foreground'
                : 'border-border/60 bg-background text-muted-foreground hover:border-border hover:bg-muted/40'
            )}
          >
            <div
              className={cn(
                'rounded-lg border p-2',
                activeSection === section.id
                  ? 'border-primary/20 bg-primary/10 text-primary'
                  : 'border-border/60 bg-muted/50 text-muted-foreground'
              )}
            >
              {section.icon}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium">{section.label}</div>
              <div className="text-xs text-muted-foreground">{section.description}</div>
            </div>
          </button>
        ))}
      </CardContent>
    </Card>
  )
}

function ValueBadge({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/70 bg-muted/30 p-3">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-medium text-foreground">{value}</div>
    </div>
  )
}

export function SettingsPage() {
  const navigate = useNavigate()
  const [activeSection, setActiveSection] = React.useState<SettingsSection>('account')
  const { settings, isLoading, error, updateSettings, modelOptions } = useSettings()
  const [draft, setDraft] = React.useState(settings)
  const [adminToken, setAdminToken] = React.useState('')
  const [isSaving, setIsSaving] = React.useState(false)

  const lastProjectId = React.useMemo(() => {
    try {
      return localStorage.getItem(LAST_PROJECT_KEY)
    } catch {
      return null
    }
  }, [])

  React.useEffect(() => {
    try {
      setAdminToken(localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) ?? '')
    } catch {
      setAdminToken('')
    }
  }, [])

  const availableModels = React.useMemo(() => {
    if (modelOptions.length > 0) return modelOptions
    if (draft.model) return [{ id: draft.model, label: draft.model }]
    return []
  }, [modelOptions, draft.model])

  React.useEffect(() => {
    setDraft(settings)
  }, [settings])

  const handleSave = async () => {
    setIsSaving(true)
    try {
      try {
        const trimmedToken = adminToken.trim()
        if (trimmedToken) {
          localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, trimmedToken)
        } else {
          localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY)
        }
      } catch {
        // Browser storage can be unavailable; save should still continue.
      }
      await updateSettings(draft)
      toast({ title: 'Settings saved' })
    } finally {
      setIsSaving(false)
    }
  }

  const sectionTitle =
    activeSection === 'account'
      ? 'Account'
      : activeSection === 'model'
        ? 'Model Configuration'
        : 'Preferences'

  const sectionDescription =
    activeSection === 'account'
      ? 'Store API access and admin credentials in one place.'
      : activeSection === 'model'
        ? 'Tune the default model and sampling behavior.'
        : 'Set output paths and autosave defaults.'

  return (
    <AppLayout className="animate-in fade-in">
      <PageHeader
        title="Settings"
        leading={
          <Button
            variant="ghost"
            size="icon"
            onClick={() => {
              if (window.history.length > 1) {
                navigate(-1)
                return
              }
              navigate(lastProjectId ? `/project/${lastProjectId}` : '/')
            }}
            aria-label="Back"
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
        }
      />

      <ContentArea className="overflow-hidden">
        <div className="mx-auto flex h-full w-full max-w-[1440px] flex-col gap-6 overflow-hidden px-4 py-6 sm:px-6 lg:px-8">
          <section className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)_320px]">
            <SectionNav activeSection={activeSection} onChange={setActiveSection} />

            <div className="space-y-4">
              <Card className="border-border/70 bg-gradient-to-br from-background to-muted/30 shadow-sm">
                <CardHeader>
                  <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    <Sparkles className="h-3.5 w-3.5" />
                    Configuration
                  </div>
                  <CardTitle className="text-2xl tracking-tight">{sectionTitle}</CardTitle>
                  <CardDescription className="max-w-2xl text-sm leading-6">
                    {sectionDescription}
                  </CardDescription>
                </CardHeader>
              </Card>

              {error ? (
                <div className="rounded-lg border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                  {error}
                </div>
              ) : null}

              {activeSection === 'account' ? (
                <Card className="border-border/70 shadow-sm">
                  <CardHeader>
                    <CardTitle className="text-base">Account Access</CardTitle>
                    <CardDescription>Credentials used by the backend and API client.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {isLoading ? (
                      <div className="space-y-3">
                        <Skeleton className="h-4 w-24" />
                        <Skeleton className="h-10 w-full" />
                        <Skeleton className="h-4 w-20" />
                        <Skeleton className="h-10 w-full" />
                        <Skeleton className="h-9 w-24" />
                      </div>
                    ) : (
                      <>
                        <div className="space-y-2">
                          <Label htmlFor="adminToken">Admin Token</Label>
                          <Input
                            id="adminToken"
                            type="password"
                            placeholder="Required when configured"
                            value={adminToken}
                            onChange={(event) => setAdminToken(event.target.value)}
                            disabled={isLoading}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="apiKey">API Key</Label>
                          <Input
                            id="apiKey"
                            type="password"
                            placeholder="sk-ant-..."
                            value={draft.apiKey ?? ''}
                            onChange={(event) =>
                              setDraft((prev) => ({ ...prev, apiKey: event.target.value }))
                            }
                            disabled={isLoading}
                          />
                        </div>
                        <Button onClick={handleSave} disabled={isLoading || isSaving}>
                          {isSaving ? 'Saving...' : 'Save changes'}
                        </Button>
                      </>
                    )}
                  </CardContent>
                </Card>
              ) : null}

              {activeSection === 'model' ? (
                <Card className="border-border/70 shadow-sm">
                  <CardHeader>
                    <CardTitle className="text-base">Model Controls</CardTitle>
                    <CardDescription>Choose the default model and tune sampling.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {isLoading ? (
                      <div className="space-y-4">
                        <Skeleton className="h-4 w-28" />
                        <Skeleton className="h-10 w-full" />
                        <Skeleton className="h-4 w-32" />
                        <Skeleton className="h-3 w-full" />
                        <Skeleton className="h-4 w-24" />
                        <Skeleton className="h-10 w-32" />
                      </div>
                    ) : (
                      <>
                        <div className="space-y-2">
                          <Label>Default Model</Label>
                          <Select
                            value={draft.model ?? 'sonnet-4'}
                            onValueChange={(value) =>
                              setDraft((prev) => ({ ...prev, model: value }))
                            }
                            disabled={isLoading}
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Select model" />
                            </SelectTrigger>
                            <SelectContent>
                              {availableModels.length > 0 ? (
                                availableModels.map((option) => (
                                  <SelectItem key={option.id} value={option.id}>
                                    {option.label ?? option.id}
                                  </SelectItem>
                                ))
                              ) : (
                                <SelectItem value={draft.model ?? 'default'} disabled>
                                  No models configured
                                </SelectItem>
                              )}
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <Label>Temperature</Label>
                          <Slider
                            value={[draft.temperature ?? 0.7]}
                            min={0}
                            max={1}
                            step={0.1}
                            onValueChange={(value) =>
                              setDraft((prev) => ({ ...prev, temperature: value[0] }))
                            }
                            disabled={isLoading}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="maxTokens">Max Tokens</Label>
                          <Input
                            id="maxTokens"
                            type="number"
                            placeholder="2048"
                            value={draft.maxTokens ?? ''}
                            onChange={(event) => {
                              const value = event.target.value
                              setDraft((prev) => ({
                                ...prev,
                                maxTokens: value ? Number(value) : undefined,
                              }))
                            }}
                            disabled={isLoading}
                          />
                        </div>
                        <Button onClick={handleSave} disabled={isLoading || isSaving}>
                          {isSaving ? 'Saving...' : 'Save changes'}
                        </Button>
                      </>
                    )}
                  </CardContent>
                </Card>
              ) : null}

              {activeSection === 'preferences' ? (
                <Card className="border-border/70 shadow-sm">
                  <CardHeader>
                    <CardTitle className="text-base">Workspace Preferences</CardTitle>
                    <CardDescription>Choose where generated files go and how they persist.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {isLoading ? (
                      <div className="space-y-4">
                        <Skeleton className="h-4 w-32" />
                        <Skeleton className="h-10 w-full" />
                        <Skeleton className="h-4 w-24" />
                        <Skeleton className="h-6 w-12" />
                        <Skeleton className="h-9 w-24" />
                      </div>
                    ) : (
                      <>
                        <div className="space-y-2">
                          <Label htmlFor="outputDir">Output Directory</Label>
                          <Input
                            id="outputDir"
                            placeholder="~/instant-coffee-output"
                            value={draft.outputDir ?? ''}
                            onChange={(event) =>
                              setDraft((prev) => ({
                                ...prev,
                                outputDir: event.target.value,
                              }))
                            }
                            disabled={isLoading}
                          />
                        </div>
                        <div className="flex items-center justify-between rounded-lg border border-border/70 bg-muted/20 p-4">
                          <div className="space-y-1">
                            <div className="text-sm font-medium">Auto-save</div>
                            <div className="text-xs text-muted-foreground">
                              Save versions after every change
                            </div>
                          </div>
                          <Switch
                            checked={draft.autoSave ?? false}
                            onCheckedChange={(value) =>
                              setDraft((prev) => ({ ...prev, autoSave: value }))
                            }
                            disabled={isLoading}
                          />
                        </div>
                        <Button onClick={handleSave} disabled={isLoading || isSaving}>
                          {isSaving ? 'Saving...' : 'Save changes'}
                        </Button>
                      </>
                    )}
                  </CardContent>
                </Card>
              ) : null}
            </div>

            <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
              <Card className="border-border/70 shadow-sm">
                <CardHeader>
                  <CardTitle className="text-base">Current Profile</CardTitle>
                  <CardDescription>What the app will use right now.</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3">
                  <ValueBadge label="Model" value={draft.model ?? 'sonnet-4'} />
                  <ValueBadge label="Temperature" value={(draft.temperature ?? 0.7).toFixed(1)} />
                  <ValueBadge label="Max tokens" value={(draft.maxTokens ?? 2048).toLocaleString()} />
                  <ValueBadge label="Auto-save" value={draft.autoSave ? 'Enabled' : 'Disabled'} />
                </CardContent>
              </Card>

              <Card className="border-border/70 shadow-sm">
                <CardHeader>
                  <CardTitle className="text-base">Storage</CardTitle>
                  <CardDescription>Where the workspace writes generated output.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-start gap-3 rounded-lg border border-border/70 bg-muted/20 p-3">
                    <FolderOpen className="mt-0.5 h-4 w-4 text-muted-foreground" />
                    <div className="min-w-0">
                      <div className="text-xs uppercase tracking-wide text-muted-foreground">
                        Output directory
                      </div>
                      <div className="mt-1 break-all text-sm text-foreground">
                        {draft.outputDir ?? 'Not set'}
                      </div>
                    </div>
                  </div>
                  <div className="rounded-lg border border-border/70 bg-muted/20 p-3 text-sm text-muted-foreground">
                    Settings are saved locally and mirrored to the backend when you press Save.
                  </div>
                </CardContent>
              </Card>
            </aside>
          </section>
        </div>
      </ContentArea>
    </AppLayout>
  )
}
