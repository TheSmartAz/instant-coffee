import type {
  ChatAction,
  ChatStep,
  Message,
  SubAgentInfo,
} from '@/types'
import type { ToolCallEvent, ToolResultEvent } from '@/types/events'
import {
  buildAgentLabel,
  buildToolLabel,
} from '@/lib/stepLabels'
import {
  createId,
  safeJsonParse,
  extractProductDocUpdateFields,
  isEventPayload,
  isInterviewPayload,
  PRODUCT_DOC_ACTIONS,
  type InterviewPayloadLike,
} from '@/hooks/useChatUtils'

export interface StreamHandlerDeps {
  streamMessageIdRef: React.MutableRefObject<string | null>
  receivedEventRef: React.MutableRefObject<boolean>
  receivedDeltaRef: React.MutableRefObject<boolean>
  interviewModeRef: React.MutableRefObject<boolean>
  resumePendingRef: React.MutableRefObject<boolean>
  stopStream: () => void
  maybeNotifySessionCreated: (value: unknown) => void
  applyInterviewQuestions: (payload: InterviewPayloadLike) => boolean
  appendStep: (step: ChatStep, options?: { updateKey?: string }) => void
  updateMessageById: (id: string, updater: (msg: Message) => Message) => void
  dispatchProductDocEvent: (payload: {
    type: string
    doc_id?: string
    change_summary?: string
    section_name?: string
    section_content?: string
  }) => void
  handleActionTabSwitch: (action: ChatAction, slug?: string) => void
  onPreview?: (payload: { html?: string; previewUrl?: string | null }) => void
}

export function createStreamDataHandler(deps: StreamHandlerDeps) {
  return (data: string) => {
    if (data === '[DONE]') {
      deps.stopStream()
      return
    }

    const payload = safeJsonParse(data)
    if (!payload || typeof payload !== 'object') return
    if ('session_id' in payload) {
      deps.maybeNotifySessionCreated((payload as { session_id?: unknown }).session_id)
    }
    if (isEventPayload(payload)) {
      deps.receivedEventRef.current = true
      if (payload.type === 'interview_question') {
        deps.applyInterviewQuestions(payload as InterviewPayloadLike)
        return
      }
      if (payload.type === 'refine_waiting' || payload.type === 'interrupt') {
        deps.resumePendingRef.current = true
        deps.interviewModeRef.current = false
      }
      if (payload.type.startsWith('agent_')) {
        const label = buildAgentLabel(payload)
        const step: ChatStep = {
          id: createId(),
          label,
          status:
            payload.type === 'agent_end'
              ? payload.status === 'success'
                ? 'done'
                : 'failed'
              : 'in_progress',
          kind: 'agent',
          key: payload.type === 'agent_progress' ? `agent:${payload.agent_id}` : undefined,
        }
        if (payload.type === 'agent_progress') {
          deps.appendStep(step, { updateKey: `agent:${payload.agent_id}` })
        } else if (payload.type === 'agent_start') {
          deps.appendStep(
            { ...step, key: `agent:${payload.agent_id}` },
            { updateKey: `agent:${payload.agent_id}` },
          )
        } else if (payload.type === 'agent_end') {
          deps.appendStep(step, { updateKey: `agent:${payload.agent_id}` })
        } else {
          deps.appendStep(step)
        }

        // Track sub-agent status on the message for AgentStatusPanel
        const messageId = deps.streamMessageIdRef.current
        if (messageId && (payload.type === 'agent_spawned' || payload.type === 'agent_end')) {
          deps.updateMessageById(messageId, (message) => {
            const existing = message.subAgents ?? []
            if (payload.type === 'agent_spawned') {
              const agentInfo: SubAgentInfo = {
                id: payload.agent_id ?? createId(),
                task: (payload.task_description ?? payload.task ?? '') as string,
                status: 'running',
              }
              return { ...message, subAgents: [...existing, agentInfo] }
            }
            // agent_end — update status
            const agentId = payload.agent_id as string
            const updated = existing.map((a) =>
              a.id === agentId
                ? {
                    ...a,
                    status: (payload.status === 'success' ? 'completed' : 'failed') as SubAgentInfo['status'],
                    summary: (payload.summary ?? '') as string,
                  }
                : a,
            )
            return { ...message, subAgents: updated }
          })
        }
      }
      if (payload.type.startsWith('tool_')) {
        const toolEvent = payload as ToolCallEvent | ToolResultEvent
        const toolKey = `tool:${toolEvent.agent_id}:${toolEvent.tool_name}`
        const step: ChatStep = {
          id: createId(),
          label: buildToolLabel(toolEvent),
          status:
            toolEvent.type === 'tool_call'
              ? 'in_progress'
              : toolEvent.success
                ? 'done'
                : 'failed',
          kind: 'tool',
        }
        if (toolEvent.type === 'tool_call') {
          deps.appendStep({ ...step, key: toolKey })
        } else {
          deps.appendStep(step, { updateKey: toolKey })
        }
      }
      // Handle files_changed events — attach to current message
      if (payload.type === 'files_changed') {
        const messageId = deps.streamMessageIdRef.current
        if (messageId && Array.isArray(payload.files)) {
          deps.updateMessageById(messageId, (message) => ({
            ...message,
            fileChanges: payload.files as Message['fileChanges'],
          }))
        }
      }
      // Handle plan_update events — attach to current message
      if (payload.type === 'plan_update') {
        const messageId = deps.streamMessageIdRef.current
        if (messageId && Array.isArray(payload.steps)) {
          deps.updateMessageById(messageId, (message) => ({
            ...message,
            plan: payload.steps as Message['plan'],
          }))
        }
      }
      // Handle bg_task events — dispatch for BackgroundTasksPanel
      if (
        payload.type === 'bg_task_started' ||
        payload.type === 'bg_task_completed' ||
        payload.type === 'bg_task_failed'
      ) {
        window.dispatchEvent(new CustomEvent('bg-task-event', { detail: payload }))
      }
      if (
        payload.type === 'product_doc_generated' ||
        payload.type === 'product_doc_updated' ||
        payload.type === 'product_doc_confirmed' ||
        payload.type === 'product_doc_outdated'
      ) {
        if (payload.type === 'product_doc_updated') {
          const messageId = deps.streamMessageIdRef.current
          if (messageId) {
            const {
              changeSummary: productDocChangeSummary,
              sectionName: productDocSectionName,
              sectionContent: productDocSectionContent,
            } = extractProductDocUpdateFields(payload)

            deps.updateMessageById(messageId, (message) => ({
              ...message,
              action: message.action ?? 'product_doc_updated',
              productDocUpdated: true,
              productDocChangeSummary:
                productDocChangeSummary ?? message.productDocChangeSummary,
              productDocSectionName:
                productDocSectionName ?? message.productDocSectionName,
              productDocSectionContent:
                productDocSectionContent ?? message.productDocSectionContent,
            }))
          }
        }

        window.dispatchEvent(
          new CustomEvent('product-doc-event', { detail: payload }),
        )
      }
      if (
        payload.type === 'page_created' ||
        payload.type === 'page_version_created' ||
        payload.type === 'page_preview_ready'
      ) {
        window.dispatchEvent(
          new CustomEvent('page-event', { detail: payload }),
        )
      }
      if (payload.type === 'aesthetic_score') {
        window.dispatchEvent(
          new CustomEvent('aesthetic-score-event', { detail: payload }),
        )
      }
      if (
        payload.type === 'build_start' ||
        payload.type === 'build_progress' ||
        payload.type === 'build_complete' ||
        payload.type === 'build_failed'
      ) {
        window.dispatchEvent(new CustomEvent('build-event', { detail: payload }))
      }
      if (payload.type === 'multipage_decision_made') {
        window.dispatchEvent(
          new CustomEvent('multipage-decision-event', { detail: payload }),
        )
      }
      if (payload.type === 'sitemap_proposed') {
        window.dispatchEvent(
          new CustomEvent('sitemap-event', { detail: payload }),
        )
      }
      return
    }
    if (isInterviewPayload(payload) && deps.applyInterviewQuestions(payload)) {
      return
    }
    deps.receivedEventRef.current = true

    if (typeof (payload as { phase?: string }).phase === 'string') {
      deps.interviewModeRef.current = (payload as { phase?: string }).phase === 'interview'
    }

    const messageId = deps.streamMessageIdRef.current
    const contentDelta =
      payload.delta ?? payload.token ?? payload.content ?? payload.message ?? payload.text
    const fullContent =
      payload.full_content ?? payload.fullContent ?? payload.output ?? payload.result
    const done =
      payload.done ||
      payload.type === 'done' ||
      payload.is_complete === true ||
      payload.isComplete === true

    const action = payload.action as ChatAction | undefined
    const activePageSlug =
      (payload.active_page_slug ?? payload.activePageSlug) as string | undefined
    const affectedPages =
      (payload.affected_pages ?? payload.affectedPages) as string[] | undefined
    const {
      changeSummary: productDocChangeSummary,
      sectionName: productDocSectionName,
      sectionContent: productDocSectionContent,
    } = extractProductDocUpdateFields(payload)
    const productDocUpdatedFromFlag =
      typeof (payload as { product_doc_updated?: unknown }).product_doc_updated ===
      'boolean'
        ? (payload as { product_doc_updated?: boolean }).product_doc_updated === true
        : false
    const productDocUpdated =
      productDocUpdatedFromFlag || action === 'product_doc_updated'

    if (action && PRODUCT_DOC_ACTIONS.has(action)) {
      deps.dispatchProductDocEvent({
        type: action,
        change_summary: productDocChangeSummary,
        section_name: productDocSectionName,
        section_content: productDocSectionContent,
      })
    } else if (productDocUpdated) {
      deps.dispatchProductDocEvent({
        type: 'product_doc_updated',
        change_summary: productDocChangeSummary,
        section_name: productDocSectionName,
        section_content: productDocSectionContent,
      })
    }

    const hasDelta =
      typeof (payload as { delta?: unknown }).delta === 'string' ||
      typeof (payload as { token?: unknown }).token === 'string'

    const messageFields = {
      action,
      productDocUpdated,
      productDocChangeSummary,
      productDocSectionName,
      productDocSectionContent,
      affectedPages,
      activePageSlug,
    }

    if (typeof fullContent === 'string' && messageId) {
      deps.receivedDeltaRef.current = false
      deps.updateMessageById(messageId, (message) => ({
        ...message,
        content: message.interview ? '' : fullContent,
        action: messageFields.action ?? message.action,
        productDocUpdated: messageFields.productDocUpdated || message.productDocUpdated,
        productDocChangeSummary:
          messageFields.productDocChangeSummary ?? message.productDocChangeSummary,
        productDocSectionName:
          messageFields.productDocSectionName ?? message.productDocSectionName,
        productDocSectionContent:
          messageFields.productDocSectionContent ?? message.productDocSectionContent,
        affectedPages: messageFields.affectedPages ?? message.affectedPages,
        activePageSlug: messageFields.activePageSlug ?? message.activePageSlug,
      }))
    } else if (typeof contentDelta === 'string' && messageId) {
      const fullMessage = (payload as { message?: unknown }).message
      if (typeof fullMessage === 'string' && deps.receivedDeltaRef.current) {
        deps.receivedDeltaRef.current = false
        deps.updateMessageById(messageId, (message) => ({
          ...message,
          content: message.interview ? '' : fullMessage,
          action: messageFields.action ?? message.action,
          productDocUpdated: messageFields.productDocUpdated || message.productDocUpdated,
          productDocChangeSummary:
            messageFields.productDocChangeSummary ?? message.productDocChangeSummary,
          productDocSectionName:
            messageFields.productDocSectionName ?? message.productDocSectionName,
          productDocSectionContent:
            messageFields.productDocSectionContent ?? message.productDocSectionContent,
          affectedPages: messageFields.affectedPages ?? message.affectedPages,
          activePageSlug: messageFields.activePageSlug ?? message.activePageSlug,
        }))
      } else {
        deps.updateMessageById(messageId, (message) => ({
          ...message,
          content: message.interview ? '' : `${message.content}${contentDelta}`,
          action: messageFields.action ?? message.action,
          productDocUpdated: messageFields.productDocUpdated || message.productDocUpdated,
          productDocChangeSummary:
            messageFields.productDocChangeSummary ?? message.productDocChangeSummary,
          productDocSectionName:
            messageFields.productDocSectionName ?? message.productDocSectionName,
          productDocSectionContent:
            messageFields.productDocSectionContent ?? message.productDocSectionContent,
          affectedPages: messageFields.affectedPages ?? message.affectedPages,
          activePageSlug: messageFields.activePageSlug ?? message.activePageSlug,
        }))
        if (hasDelta) {
          deps.receivedDeltaRef.current = true
        }
      }
    }

    if (payload.preview_html || payload.previewHtml) {
      deps.onPreview?.({ html: payload.preview_html ?? payload.previewHtml })
    }
    if (payload.preview_url || payload.previewUrl) {
      deps.onPreview?.({ previewUrl: payload.preview_url ?? payload.previewUrl })
    }

    if (done) {
      if (action) {
        deps.handleActionTabSwitch(action, activePageSlug)
      }
      deps.stopStream()
    }
  }
}
