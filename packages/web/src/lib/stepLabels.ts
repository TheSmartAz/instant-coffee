import type { ExecutionEvent, ToolCallEvent, ToolResultEvent } from '@/types/events'

const TOOL_SUMMARY_KEYS = [
  'path',
  'paths',
  'filename',
  'file',
  'url',
  'query',
  'pattern',
  'command',
  'expression',
  'name',
  'id',
  'preview_path',
  'version_path',
  'written_bytes',
  'version',
]

const SENSITIVE_KEYS = new Set([
  'content',
  'html',
  'data',
  'prompt',
  'message',
  'text',
  'code',
])

export const truncateText = (value: string, max = 96) => {
  if (value.length <= max) return value
  return `${value.slice(0, max)}...`
}

const summarizeValue = (value: unknown): string | null => {
  if (typeof value === 'string') return truncateText(value, 80)
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) {
    const items = value
      .slice(0, 2)
      .map((item) => summarizeValue(item))
      .filter((item): item is string => Boolean(item))
    return items.length ? `[${items.join(', ')}]` : null
  }
  return null
}

export const summarizeRecord = (input?: unknown): string | null => {
  if (!input) return null
  if (typeof input !== 'object' || Array.isArray(input)) {
    return summarizeValue(input)
  }

  const record = input as Record<string, unknown>
  const entries: string[] = []

  for (const key of TOOL_SUMMARY_KEYS) {
    if (!(key in record)) continue
    if (SENSITIVE_KEYS.has(key.toLowerCase())) continue
    const value = summarizeValue(record[key])
    if (!value) continue
    entries.push(`${key}=${value}`)
    if (entries.length >= 2) break
  }

  if (entries.length === 0) {
    for (const [key, value] of Object.entries(record)) {
      if (SENSITIVE_KEYS.has(key.toLowerCase())) continue
      const summary = summarizeValue(value)
      if (!summary) continue
      entries.push(`${key}=${summary}`)
      if (entries.length >= 2) break
    }
  }

  if (entries.length === 0 && typeof record.output === 'object' && record.output) {
    return summarizeRecord(record.output)
  }

  return entries.length ? entries.join(', ') : null
}

export const buildAgentLabel = (event: ExecutionEvent) => {
  if (event.type === 'agent_spawned') {
    const task = (event as { task_description?: string }).task_description
    return task ? `Sub-agent: ${truncateText(task, 80)}` : 'Sub-agent spawned'
  }
  if (event.type === 'agent_start') {
    return `${event.agent_type} agent started`
  }
  if (event.type === 'agent_progress') {
    const message = event.message ? `: ${truncateText(event.message, 80)}` : ''
    return `${event.agent_id}${message}`
  }
  if (event.type === 'agent_end') {
    return `${event.agent_id} ${event.status === 'success' ? 'completed' : 'failed'}`
  }
  return event.type
}

export const buildToolLabel = (event: ToolCallEvent | ToolResultEvent) => {
  const summarySource =
    event.type === 'tool_call' ? event.tool_input : event.tool_output
  const summary = summarizeRecord(summarySource)
  const base = summary ? `${event.tool_name} (${summary})` : event.tool_name
  if (event.type === 'tool_call') {
    return `Calling ${base}`
  }
  if (!event.success && event.error) {
    return `Result ${base} - ${truncateText(event.error, 80)}`
  }
  return `Result ${base}`
}
