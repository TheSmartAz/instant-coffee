import * as React from 'react'
import { api } from '@/api/client'
import { toast } from '@/hooks/use-toast'
import type { Settings } from '@/types'

type ApiSettings = {
  api_key?: string
  model?: string
  temperature?: number
  max_tokens?: number
  output_dir?: string
  auto_save?: boolean
}

const defaultSettings: Settings = {
  model: 'sonnet-4',
  temperature: 0.7,
  maxTokens: 2048,
  autoSave: true,
}

const normalizeSettings = (data?: ApiSettings): Settings => ({
  apiKey: data?.api_key,
  model: data?.model ?? defaultSettings.model,
  temperature: data?.temperature ?? defaultSettings.temperature,
  maxTokens: data?.max_tokens ?? defaultSettings.maxTokens,
  outputDir: data?.output_dir,
  autoSave: data?.auto_save ?? defaultSettings.autoSave,
})

const serializeSettings = (settings: Settings) => ({
  api_key: settings.apiKey,
  model: settings.model,
  temperature: settings.temperature,
  max_tokens: settings.maxTokens,
  output_dir: settings.outputDir,
  auto_save: settings.autoSave,
})

export function useSettings() {
  const [settings, setSettings] = React.useState<Settings>(defaultSettings)
  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  const refresh = React.useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = (await api.settings.get()) as ApiSettings | undefined
      setSettings(normalizeSettings(response))
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load settings'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [])

  React.useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const response = (await api.settings.get()) as ApiSettings | undefined
        if (!active) return
        setSettings(normalizeSettings(response))
      } catch (err) {
        if (!active) return
        const message = err instanceof Error ? err.message : 'Failed to load settings'
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

  const updateSettings = React.useCallback(async (next: Settings) => {
    setError(null)
    try {
      const response = (await api.settings.update(serializeSettings(next))) as
        | ApiSettings
        | undefined
      const updated = normalizeSettings(response ?? serializeSettings(next))
      setSettings(updated)
      return updated
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update settings'
      setError(message)
      toast({ title: 'Failed to update settings', description: message })
      throw err
    }
  }, [])

  return {
    settings,
    isLoading,
    error,
    refresh,
    updateSettings,
    setSettings,
  }
}
