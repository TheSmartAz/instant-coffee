import * as React from 'react'
import { api } from '@/api/client'
import type { AestheticScore, AestheticSuggestion } from '@/types/aesthetic'
import type { AestheticScoreEvent } from '@/types/events'

const DEFAULT_DIMENSIONS = {
  visualHierarchy: 0,
  colorHarmony: 0,
  spacingConsistency: 0,
  alignment: 0,
  readability: 0,
  mobileAdaptation: 0,
}

const toNumber = (value: unknown, fallback = 0) => {
  if (typeof value === 'number' && !Number.isNaN(value)) return value
  if (typeof value === 'string') {
    const parsed = Number(value)
    return Number.isNaN(parsed) ? fallback : parsed
  }
  return fallback
}

const toBoolean = (value: unknown, fallback = false) => {
  if (typeof value === 'boolean') return value
  if (typeof value === 'number') return value > 0
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase()
    if (normalized === 'true' || normalized === '1') return true
    if (normalized === 'false' || normalized === '0') return false
  }
  return fallback
}

const normalizeSuggestions = (value: unknown): AestheticSuggestion[] => {
  if (!Array.isArray(value)) return []
  const suggestions: AestheticSuggestion[] = []

  for (const entry of value) {
    if (!entry || typeof entry !== 'object') continue
    const raw = entry as Record<string, unknown>
    const message = typeof raw.message === 'string' ? raw.message : ''
    if (!message) continue
    const severity =
      raw.severity === 'warning' || raw.severity === 'critical'
        ? raw.severity
        : 'info'

    suggestions.push({
      dimension: typeof raw.dimension === 'string' ? raw.dimension : 'visualHierarchy',
      severity,
      message,
      location: typeof raw.location === 'string' ? raw.location : undefined,
      autoFixable: toBoolean(raw.autoFixable, false),
    })
  }

  return suggestions
}

export const normalizeAestheticScore = (value: unknown): AestheticScore | null => {
  if (!value || typeof value !== 'object') return null
  const raw = value as Record<string, unknown>
  const dims = raw.dimensions && typeof raw.dimensions === 'object'
    ? (raw.dimensions as Record<string, unknown>)
    : {}

  const normalizedDimensions = {
    visualHierarchy: toNumber(dims.visualHierarchy ?? dims.visual_hierarchy),
    colorHarmony: toNumber(dims.colorHarmony ?? dims.color_harmony),
    spacingConsistency: toNumber(dims.spacingConsistency ?? dims.spacing_consistency),
    alignment: toNumber(dims.alignment),
    readability: toNumber(dims.readability),
    mobileAdaptation: toNumber(dims.mobileAdaptation ?? dims.mobile_adaptation),
  }

  const suggestions = normalizeSuggestions(raw.suggestions)
  const overall = toNumber(raw.overall)
  const hasOverall = typeof raw.overall !== 'undefined'
  const computedOverall = Math.round(
    Object.values(normalizedDimensions).reduce((sum, val) => sum + val, 0) /
      Object.keys(DEFAULT_DIMENSIONS).length
  )

  return {
    overall: hasOverall ? overall : computedOverall,
    dimensions: normalizedDimensions,
    suggestions,
    passThreshold: toBoolean(raw.passThreshold ?? raw.pass_threshold, false),
  }
}

export const useAestheticScore = (sessionId?: string) => {
  const [score, setScore] = React.useState<AestheticScore | null>(null)

  React.useEffect(() => {
    if (!sessionId) {
      setScore(null)
      return
    }

    let active = true
    const loadMetadata = async () => {
      try {
        const metadata = await api.sessions.getMetadata(sessionId)
        if (!active || !metadata || typeof metadata !== 'object') return
        const payload = metadata as Record<string, unknown>
        const rawScore = payload.aesthetic_scores ?? payload.aestheticScores
        const normalized = normalizeAestheticScore(rawScore)
        if (normalized) setScore(normalized)
      } catch {
        // ignore metadata failures
      }
    }

    void loadMetadata()

    const handleEvent = (event: Event) => {
      const customEvent = event as CustomEvent<AestheticScoreEvent>
      const payload = customEvent.detail
      if (!payload || typeof payload !== 'object') return
      if (payload.session_id && payload.session_id !== sessionId) return
      const normalized = normalizeAestheticScore(payload.score)
      if (!normalized) return
      setScore(normalized)
    }

    window.addEventListener('aesthetic-score-event', handleEvent)
    return () => {
      active = false
      window.removeEventListener('aesthetic-score-event', handleEvent)
    }
  }, [sessionId])

  return { score, setScore }
}
