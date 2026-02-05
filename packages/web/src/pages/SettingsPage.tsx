import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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

export function SettingsPage() {
  const navigate = useNavigate()
  const [activeSection, setActiveSection] = React.useState<SettingsSection>('account')
  const { settings, isLoading, error, updateSettings, modelOptions } = useSettings()
  const [draft, setDraft] = React.useState(settings)
  const [isSaving, setIsSaving] = React.useState(false)

  // Get the last visited project ID
  const lastProjectId = React.useMemo(() => {
    try {
      return localStorage.getItem(LAST_PROJECT_KEY)
    } catch {
      return null
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
      await updateSettings(draft)
      toast({ title: 'Settings saved' })
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col animate-in fade-in">
      <header className="flex items-center gap-3 border-b border-border px-6 py-4">
        {lastProjectId ? (
          <Button variant="ghost" size="icon" onClick={() => navigate(`/project/${lastProjectId}`)}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
        ) : null}
        <h1 className="text-lg font-semibold">Settings</h1>
      </header>
      <div className="mx-auto flex w-full max-w-5xl gap-6 px-6 py-10 flex-1">
      <nav className="w-48 space-y-2">
        {(['account', 'model', 'preferences'] as SettingsSection[]).map((section) => (
          <button
            key={section}
            type="button"
            onClick={() => setActiveSection(section)}
            aria-current={activeSection === section ? 'page' : undefined}
            className={cn(
              'w-full rounded-lg px-3 py-2 text-left text-sm font-medium transition',
              activeSection === section
                ? 'bg-muted text-foreground'
                : 'text-muted-foreground hover:bg-muted/60'
            )}
          >
            {section === 'account' ? 'Account' : section === 'model' ? 'Model' : 'Preferences'}
          </button>
        ))}
      </nav>

      <div className="flex-1 space-y-6">
        {error ? <div className="text-sm text-destructive">{error}</div> : null}
        {activeSection === 'account' ? (
          <Card>
            <CardHeader>
              <CardTitle>Account</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {isLoading ? (
                <div className="space-y-3">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-9 w-24" />
                </div>
              ) : (
                <>
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
                    {isSaving ? 'Saving...' : 'Save'}
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        ) : null}

        {activeSection === 'model' ? (
          <Card>
            <CardHeader>
              <CardTitle>Model Configuration</CardTitle>
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
                    {isSaving ? 'Saving...' : 'Save'}
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        ) : null}

        {activeSection === 'preferences' ? (
          <Card>
            <CardHeader>
              <CardTitle>Preferences</CardTitle>
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
                  <div className="flex items-center justify-between">
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
                    {isSaving ? 'Saving...' : 'Save'}
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        ) : null}
      </div>
    </div>
    </div>
  )
}
