export type AestheticSeverity = 'info' | 'warning' | 'critical'

export type AestheticDimensionKey =
  | 'visualHierarchy'
  | 'colorHarmony'
  | 'spacingConsistency'
  | 'alignment'
  | 'readability'
  | 'mobileAdaptation'

export interface AestheticScoreDimensions {
  visualHierarchy: number
  colorHarmony: number
  spacingConsistency: number
  alignment: number
  readability: number
  mobileAdaptation: number
}

export interface AestheticSuggestion {
  dimension: AestheticDimensionKey | string
  severity: AestheticSeverity
  message: string
  location?: string
  autoFixable: boolean
}

export interface AestheticScore {
  overall: number
  dimensions: AestheticScoreDimensions
  suggestions: AestheticSuggestion[]
  passThreshold: boolean
}
