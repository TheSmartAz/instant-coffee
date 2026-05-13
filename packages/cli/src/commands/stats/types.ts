export interface TokenBucket {
  tokens: number
  cost_usd: number
  calls: number
}

export interface OverallStats {
  today: TokenBucket
  week: TokenBucket
  total: TokenBucket & {
    sessions: number
    pages?: number
  }
  by_agent?: Record<string, TokenBucket>
}

export interface SessionTimelineEntry {
  timestamp: string
  agent_type: string
  tokens: number
  cost_usd: number
}

export interface SessionStats {
  session_id: string
  title?: string
  created_at?: string
  total_tokens: number
  cost_usd: number
  calls?: number
  by_agent?: Record<string, TokenBucket>
  timeline?: SessionTimelineEntry[]
}
