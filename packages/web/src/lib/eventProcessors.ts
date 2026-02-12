import type { ChatStep, InterviewBatch, MessageSegment } from '@/types'
import {
  mergeInterviewAnswerList,
  normalizeInterviewAnswers,
  normalizeInterviewQuestions,
} from '@/lib/interviewUtils'
import { buildAgentLabel, buildToolLabel } from '@/lib/stepLabels'
import type { SessionEvent, ToolCallEvent, ToolResultEvent } from '@/types/events'

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value && typeof value === 'object')

const getString = (value: unknown) =>
  typeof value === 'string' ? value : undefined

const mapInterviewActionToStatus = (
  action?: string,
): InterviewBatch['status'] | undefined => {
  switch (action) {
    case 'generate_now':
      return 'generated'
    case 'skip_batch':
      return 'skipped'
    case 'submit_batch':
      return 'submitted'
    case 'update_answers':
      return 'active'
    default:
      return undefined
  }
}

const normalizeInterviewBatchActivity = (batches: InterviewBatch[]) => {
  if (batches.length === 0) return batches

  const latestBatch = batches[batches.length - 1]
  if (!latestBatch) return batches

  if (latestBatch.status === 'active') {
    for (let index = 0; index < batches.length - 1; index += 1) {
      if (batches[index].status === 'active') {
        batches[index].status = 'submitted'
      }
    }
    return batches
  }

  for (const batch of batches) {
    if (batch.status === 'active') {
      batch.status = 'submitted'
    }
  }

  return batches
}

export const buildInterviewBatchesFromEvents = (events: SessionEvent[]): InterviewBatch[] => {
  const sorted = [...events].sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0))
  const batches: InterviewBatch[] = []
  const byId = new Map<string, InterviewBatch>()
  let totalCount = 0
  let latestBatchId: string | null = null

  for (const event of sorted) {
    if (event.type !== 'interview_question' && event.type !== 'interview_answer') {
      continue
    }
    const payload = isRecord(event.payload) ? event.payload : {}

    if (event.type === 'interview_question') {
      const questions = normalizeInterviewQuestions(payload.questions)
      if (questions.length === 0) continue
      const batchId = String(
        payload.batch_id ?? payload.batchId ?? payload.id ?? `batch-${event.seq ?? batches.length + 1}`,
      )
      const prompt = getString(payload.message ?? payload.prompt)
      const startIndex = totalCount + 1
      totalCount += questions.length
      const batch: InterviewBatch = {
        id: batchId,
        prompt,
        questions,
        startIndex,
        totalCount,
        status: 'active',
      }
      batches.push(batch)
      byId.set(batchId, batch)
      latestBatchId = batchId
      continue
    }

    if (event.type === 'interview_answer') {
      const answers = normalizeInterviewAnswers(
        payload.answers ?? payload.answer ?? payload.responses ?? payload.response,
      )
      const batchIdRaw = payload.batch_id ?? payload.batchId ?? payload.id ?? latestBatchId
      if (!batchIdRaw) continue
      const batchId = String(batchIdRaw)
      const batch = byId.get(batchId)
      if (!batch) continue

      if (answers.length > 0) {
        const questionIndex = new Map(
          batch.questions.map((question, index) => [
            question.id,
            batch.startIndex + index,
          ]),
        )
        const enriched = answers.map((answer, index) => ({
          ...answer,
          question:
            batch.questions.find((q) => q.id === answer.id)?.title ?? answer.question,
          index:
            typeof answer.index === 'number'
              ? answer.index
              : questionIndex.get(answer.id) ?? batch.startIndex + index,
        }))
        batch.answers = mergeInterviewAnswerList(batch.answers, enriched)
      }

      const action = getString(payload.action)
      const status = mapInterviewActionToStatus(action)
      if (status && status !== 'active') {
        batch.status = status
        latestBatchId = null
      } else if (status) {
        batch.status = status
      }
    }
  }

  return normalizeInterviewBatchActivity(batches)
}

export { mapInterviewActionToStatus }

const STEP_EVENT_TYPES = new Set([
  'agent_start',
  'agent_progress',
  'agent_end',
  'tool_call',
  'tool_result',
])

export { STEP_EVENT_TYPES }

export const buildStepsFromEvents = (
  events: SessionEvent[],
): Map<string, { steps: ChatStep[]; segments: MessageSegment[] }> => {
  const grouped = new Map<string, SessionEvent[]>()
  for (const event of events) {
    if (!STEP_EVENT_TYPES.has(event.type)) continue
    const key = event.run_id ?? '__default__'
    const list = grouped.get(key)
    if (list) {
      list.push(event)
    } else {
      grouped.set(key, [event])
    }
  }

  const result = new Map<string, { steps: ChatStep[]; segments: MessageSegment[] }>()
  for (const [runId, group] of grouped) {
    const sorted = [...group].sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0))
    const steps: ChatStep[] = []
    for (const event of sorted) {
      const payload = event.payload ?? {}
      if (event.type === 'agent_start' || event.type === 'agent_progress' || event.type === 'agent_end') {
        const fakeEvent = {
          ...payload,
          type: event.type,
          timestamp: event.created_at,
          agent_id: payload.agent_id as string ?? '',
          agent_type: payload.agent_type as string ?? '',
          status: payload.status as string ?? 'success',
          message: payload.message as string ?? '',
          progress: payload.progress as number | undefined,
        }
        const label = buildAgentLabel(fakeEvent as Parameters<typeof buildAgentLabel>[0])
        steps.push({
          id: `step-${event.id}`,
          label,
          status:
            event.type === 'agent_end'
              ? (payload.status === 'success' ? 'done' : 'failed')
              : 'done',
          kind: 'agent',
        })
      } else if (event.type === 'tool_call' || event.type === 'tool_result') {
        const fakeEvent = {
          ...payload,
          type: event.type,
          timestamp: event.created_at,
          agent_id: payload.agent_id as string ?? '',
          tool_name: payload.tool_name as string ?? '',
          tool_input: payload.tool_input as Record<string, unknown> | undefined,
          tool_output: payload.tool_output as Record<string, unknown> | undefined,
          success: payload.success as boolean ?? true,
          error: payload.error as string | undefined,
        }
        const label = buildToolLabel(fakeEvent as ToolCallEvent | ToolResultEvent)
        steps.push({
          id: `step-${event.id}`,
          label,
          status:
            event.type === 'tool_call'
              ? 'done'
              : (fakeEvent.success ? 'done' : 'failed'),
          kind: 'tool',
          toolName: fakeEvent.tool_name || undefined,
          toolInput: fakeEvent.tool_input,
          toolOutput: fakeEvent.tool_output as ChatStep['toolOutput'],
          error: fakeEvent.error,
        })
      }
    }
    if (steps.length > 0) {
      // Put all steps into a single tool_group — during streaming, tools are
      // grouped together unless text appears between them.  Since we can't
      // reconstruct the original text interleaving from events alone, a single
      // group matches the streaming UX better than fragmenting by agent_id.
      const segments: MessageSegment[] = [{ type: 'tool_group', steps }]
      result.set(runId, { steps, segments })
    }
  }
  return result
}

/* ── Widget data reconstruction from events ── */

const WIDGET_EVENT_TYPES = new Set([
  'plan_update',
  'plan_created',
  'files_changed',
  'agent_spawned',
  'agent_end',
  'product_doc_generated',
  'product_doc_updated',
  'product_doc_confirmed',
])

interface WidgetData {
  plan?: Array<{ step: string; status: string }>
  planTasks?: Array<{ id: string; title: string; status: string; description?: string }>
  fileChanges?: Array<{ path: string; action: string; language?: string }>
  subAgents?: Array<{ id: string; task: string; status: 'running' | 'completed' | 'failed'; summary?: string }>
  action?: string
  productDocUpdated?: boolean
  productDocChangeSummary?: string
  productDocSectionName?: string
  productDocSectionContent?: string
}

export const buildWidgetDataFromEvents = (events: SessionEvent[]): WidgetData => {
  const sorted = [...events]
    .filter((e) => WIDGET_EVENT_TYPES.has(e.type))
    .sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0))

  const data: WidgetData = {}
  const agentMap = new Map<string, WidgetData['subAgents']>()

  for (const event of sorted) {
    const payload = isRecord(event.payload) ? event.payload : {}

    switch (event.type) {
      case 'plan_update': {
        const steps = Array.isArray(payload.steps) ? payload.steps : []
        if (steps.length > 0) {
          data.plan = (steps as Array<Record<string, unknown>>).map((s, i) => ({
            step: String(s.step || s.title || s.description || s.name || s.text || `Step ${i + 1}`),
            status: String(s.status ?? 'pending'),
          }))
        }
        break
      }
      case 'plan_created': {
        const plan = isRecord(payload.plan) ? payload.plan : payload
        const tasks = Array.isArray(plan.tasks) ? plan.tasks : []
        if (tasks.length > 0) {
          data.planTasks = (tasks as Array<Record<string, unknown>>).map((t) => ({
            id: String(t.id ?? ''),
            title: String(t.title ?? t.name ?? ''),
            status: String(t.status ?? 'pending'),
            description: getString(t.description),
          }))
        }
        break
      }
      case 'files_changed': {
        const files = Array.isArray(payload.files) ? payload.files : []
        if (files.length > 0) {
          data.fileChanges = (files as Array<Record<string, unknown>>).map((f) => ({
            path: String(f.path ?? ''),
            action: String(f.action ?? 'modified'),
            language: getString(f.language),
          }))
        }
        break
      }
      case 'agent_spawned': {
        const agentId = String(payload.agent_id ?? '')
        if (agentId) {
          const info = {
            id: agentId,
            task: String(payload.task_description ?? payload.task ?? ''),
            status: 'running' as const,
          }
          const existing = agentMap.get(agentId)
          if (existing) {
            const idx = existing.findIndex((a) => a.id === agentId)
            if (idx >= 0) existing[idx] = info
            else existing.push(info)
          } else {
            agentMap.set(agentId, [info])
          }
        }
        break
      }
      case 'agent_end': {
        const agentId = String(payload.agent_id ?? '')
        if (agentId) {
          for (const [, agents] of agentMap) {
            for (const agent of agents) {
              if (agent.id === agentId) {
                agent.status = payload.status === 'success' ? 'completed' : 'failed'
                agent.summary = getString(payload.summary) ?? ''
              }
            }
          }
        }
        break
      }
      case 'product_doc_generated':
        data.action = 'product_doc_generated'
        data.productDocUpdated = true
        data.productDocChangeSummary = getString(payload.change_summary) ?? getString(payload.changeSummary)
        break
      case 'product_doc_updated':
        data.action = data.action ?? 'product_doc_updated'
        data.productDocUpdated = true
        data.productDocChangeSummary = getString(payload.change_summary) ?? getString(payload.changeSummary) ?? data.productDocChangeSummary
        data.productDocSectionName = getString(payload.section_name) ?? getString(payload.sectionName) ?? data.productDocSectionName
        data.productDocSectionContent = getString(payload.section_content) ?? getString(payload.sectionContent) ?? data.productDocSectionContent
        break
      case 'product_doc_confirmed':
        data.action = data.action ?? 'product_doc_confirmed'
        break
    }
  }

  // Flatten agent map
  const allAgents: NonNullable<WidgetData['subAgents']> = []
  for (const [, agents] of agentMap) {
    allAgents.push(...agents)
  }
  if (allAgents.length > 0) {
    data.subAgents = allAgents
  }

  return data
}
