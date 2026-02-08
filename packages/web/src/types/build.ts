export type BuildStatusType = 'idle' | 'pending' | 'building' | 'success' | 'failed'

export interface BuildProgress {
  step?: string
  percent?: number
  message?: string
}

export interface BuildState {
  status: BuildStatusType
  pages: string[]
  distPath?: string
  error?: string
  startedAt?: string
  completedAt?: string
  progress?: BuildProgress
}
