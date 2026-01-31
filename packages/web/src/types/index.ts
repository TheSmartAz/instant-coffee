export type MessageRole = 'user' | 'assistant'

export interface Message {
  id: string
  role: MessageRole
  content: string
  timestamp?: Date
  isStreaming?: boolean
}

export interface Version {
  id: string
  number: number
  createdAt: Date
  isCurrent: boolean
  description?: string
  previewUrl?: string
  previewHtml?: string
}

export interface Project {
  id: string
  name: string
  updatedAt: Date
  versionCount: number
  messageCount?: number
  thumbnail?: string
}

export interface SessionDetail {
  id: string
  title: string
  createdAt: Date
  updatedAt: Date
  currentVersion?: number
  previewUrl?: string
  previewHtml?: string
}

export interface Settings {
  apiKey?: string
  model?: string
  temperature?: number
  maxTokens?: number
  outputDir?: string
  autoSave?: boolean
}

export interface ChatResponse {
  message?: string
  preview_url?: string | null
  preview_html?: string | null
  action?: string | null
  session_id?: string
}

export interface TokenUsage {
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cost_usd: number
}

export interface AgentTokenUsage {
  agent_type: 'interview' | 'generation' | 'refinement' | string
  usage: TokenUsage
}

export interface SessionTokenSummary {
  total: TokenUsage
  by_agent: Record<string, TokenUsage>
}
