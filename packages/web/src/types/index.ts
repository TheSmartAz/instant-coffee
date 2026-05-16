import type { FileChange, PlanStep, PlanTaskSnapshot } from './events'

export type MessageRole = 'user' | 'assistant'

export type ChatStepStatus = 'in_progress' | 'done' | 'failed'

export interface ChatStep {
  id: string
  label: string
  status?: ChatStepStatus
  timestamp?: Date
  kind?: 'agent' | 'tool'
  key?: string
  toolName?: string
  toolInput?: Record<string, unknown>
  toolOutput?: unknown
  error?: string
  progressMessage?: string
  progressPercent?: number
}

export type ChatRunStatusStage = 'run' | 'implement' | 'build' | 'review' | 'policy'

export interface ChatRunStatus {
  eventType: string
  stage: ChatRunStatusStage
  runId?: string
  executionMode?: ExecutionMode
  phase?: string
  status?: string
  message?: string
  error?: string
  approvalId?: string
  command?: string
  reason?: string
  percent?: number
  summary?: Record<string, unknown>
  updatedAt?: string
}

export type RunStatusValue =
  | 'queued'
  | 'running'
  | 'waiting_input'
  | 'completed'
  | 'failed'
  | 'cancelled'

export interface RunReviewIssue {
  code?: string
  severity?: 'error' | 'warning' | string
  message?: string
  subject?: string | null
  details?: Record<string, unknown>
}

export interface RunVerificationCheck {
  name: string
  status: string
  passed?: boolean | null
  details?: Record<string, unknown>
}

export interface RunVerification {
  status: string
  passed?: boolean | null
  checks: RunVerificationCheck[]
  evidence: string[]
  summary: Record<string, unknown>
  profile?: {
    recommended_commands?: Array<Record<string, unknown>>
    risk_flags?: string[]
    memory_keys?: string[]
  }
  last_run?: {
    status: string
    passed: boolean
    commands: Array<{
      name: string
      command: string
      scope: string
      status: string
      exit_code?: number | null
      duration_ms: number
      output_summary: string
      failures: Array<Record<string, unknown>>
    }>
    risk_flags: string[]
    started_at?: string | null
    completed_at?: string | null
  } | null
  fix_attempts?: Array<{
    attempt: number
    status: string
    prompt: string
    failures: Array<Record<string, unknown>>
    engine?: Record<string, unknown> | null
    verification?: RunVerification['last_run']
    change_summary?: {
      status: string
      changed_files: string[]
      file_count: number
      risk_level: 'low' | 'medium' | 'high' | string
      risk_flags?: string[]
      verification_status?: string | null
      captured_at?: string | null
    } | null
    gate?: {
      status: string
      decision: string
      reasons?: string[]
      evaluated_at?: string | null
      approved?: boolean | null
      approved_at?: string | null
      reviewer?: {
        source?: string
        recommendation?: string
        summary?: string
        reasons?: string[]
        checklist?: string[]
        changed_files?: string[]
        verification_status?: string | null
        reviewed_at?: string | null
      } | null
    } | null
    error?: string | null
    started_at?: string | null
    completed_at?: string | null
  }>
  audit_trail?: Array<{
    type: string
    status: string
    message?: string
    attempt?: number | null
    command_count?: number | null
    failure_count?: number | null
    risk_flags?: string[]
    at?: string | null
  }>
  action_audit_trail?: Array<{
    type: string
    category: string
    status: string
    summary?: string
    attempt?: number | null
    command?: string | null
    scope?: string | null
    exit_code?: number | null
    duration_ms?: number | null
    file_count?: number | null
    risk_level?: string | null
    risk_flags?: string[]
    at?: string | null
  }>
}

export interface RunContextEvidence {
  memory_keys: string[]
  memory: Record<string, string>
}

export interface SessionRunDetail {
  run_id: string
  session_id: string
  status: RunStatusValue
  execution_mode?: ExecutionMode | null
  executionMode?: ExecutionMode | null
  /** @deprecated use execution_mode or executionMode. */
  approval_mode?: ApprovalMode | null
  created_at?: string | null
  updated_at?: string | null
  started_at?: string | null
  finished_at?: string | null
  latest_error?: Record<string, unknown> | null
  metrics?: Record<string, unknown> | null
  checkpoint_thread?: string | null
  checkpoint_ns?: string | null
  waiting_reason?: string | null
  current_phase?: string | null
  phase_status?: string | null
  phase_metadata?: Record<string, unknown>
  phase_history?: Array<Record<string, unknown>>
  artifacts?: Record<string, unknown>
  fix_attempts?: number
  last_review?: Record<string, unknown> | null
  review_summary?: Record<string, unknown> | null
  review_issues?: RunReviewIssue[]
  verification?: RunVerification
  context?: RunContextEvidence
  heartbeat_at?: string | null
}

export interface SessionRunListResponse {
  runs: SessionRunDetail[]
  total: number
}

export interface RunEventResponse {
  id: number
  session_id: string
  run_id?: string | null
  event_id?: string | null
  seq: number
  type: string
  payload: Record<string, unknown>
  source: string
  created_at: string
}

export interface RunEventsResponse {
  events: RunEventResponse[]
  last_seq: number
  has_more: boolean
}

export type MessageSegment =
  | { type: 'text'; content: string }
  | { type: 'tool_group'; steps: ChatStep[] }

export interface MessageImage {
  data: string
  intent?: string
  name?: string
  width?: number
  height?: number
}

export type InterviewQuestionType = 'single' | 'multi' | 'text'

export interface InterviewOption {
  id: string
  label: string
}

export interface InterviewQuestion {
  id: string
  type: InterviewQuestionType
  title: string
  options?: InterviewOption[]
  allow_other?: boolean
  other_placeholder?: string
  placeholder?: string
}

export interface InterviewAnswer {
  id: string
  question: string
  type: InterviewQuestionType
  value: string | string[]
  label?: string
  labels?: string[]
  other?: string
  index?: number
}

export interface InterviewBatch {
  id: string
  prompt?: string
  questions: InterviewQuestion[]
  startIndex: number
  totalCount: number
  status?: 'active' | 'submitted' | 'skipped' | 'generated'
  answers?: InterviewAnswer[]
}

export interface InterviewSummary {
  items: InterviewAnswer[]
}

export type InterviewAction = 'submit' | 'skip' | 'generate'

export interface InterviewActionPayload {
  action: InterviewAction
  batchId: string
  answers: InterviewAnswer[]
}

// Disambiguation types for page selection
export interface DisambiguationOption {
  id: string
  slug: string
  title: string
  description?: string
}

export interface Disambiguation {
  prompt: string
  options: DisambiguationOption[]
}

export interface Message {
  id: string
  role: MessageRole
  content: string
  timestamp?: Date
  isStreaming?: boolean
  steps?: ChatStep[]
  interview?: InterviewBatch
  interviewSummary?: InterviewSummary
  action?: ChatAction
  productDocUpdated?: boolean
  productDocChangeSummary?: string
  productDocSectionName?: string
  productDocSectionContent?: string
  affectedPages?: string[]
  activePageSlug?: string
  disambiguation?: Disambiguation
  hidden?: boolean
  assets?: ChatAsset[]
  fileChanges?: FileChange[]
  plan?: PlanStep[]
  subAgents?: SubAgentInfo[]
  images?: MessageImage[]
  planTasks?: PlanTaskSnapshot[]
  segments?: MessageSegment[]
}

export interface SubAgentInfo {
  id: string
  task: string
  status: 'running' | 'completed' | 'failed'
  summary?: string
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
  thumbnail?: string | null
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

export interface Thread {
  id: string
  session_id: string
  title: string | null
  created_at: string
  updated_at: string
  message_count: number
}

export interface Settings {
  apiKey?: string
  hasApiKey?: boolean
  model?: string
  temperature?: number
  maxTokens?: number
  outputDir?: string
  autoSave?: boolean
}

export interface ModelOption {
  id: string
  label?: string
}

export type ChatAction =
  | 'product_doc_generated'
  | 'product_doc_updated'
  | 'product_doc_confirmed'
  | 'pages_generated'
  | 'page_refined'
  | 'multipage_suggested'
  | 'refine_waiting'
  | 'direct_reply'

export interface ChatResponse {
  session_id?: string
  message?: string

  // Preview
  preview_url?: string | null
  preview_html?: string | null
  active_page_slug?: string | null

  // ProductDoc state
  product_doc_updated?: boolean
  change_summary?: string | null
  changeSummary?: string | null
  section_name?: string | null
  sectionName?: string | null
  section_content?: string | null
  sectionContent?: string | null
  affected_pages?: string[]

  // Action
  action?: ChatAction | null

  // Token usage
  tokens_used?: number
}

export type ChatAttachmentType = 'image'

export interface ChatAttachment {
  type: ChatAttachmentType
  data: string
  name: string
  size: number
  mimeType?: string
  width?: number
  height?: number
  previewUrl?: string
}

export type AssetType = 'logo' | 'style_ref' | 'background' | 'product_image'

export interface AssetRef {
  id: string
  url: string
  type: string
  width?: number
  height?: number
}

export interface ChatAsset extends AssetRef {
  assetType: AssetType
  name?: string
  size?: number
  createdAt?: string
}

export type ChatStyleReferenceMode = 'full_mimic' | 'style_only'

export interface ChatStyleReference {
  mode: ChatStyleReferenceMode
  scope_pages?: string[]
}

export type ImageIntent = 'asset' | 'style_reference' | 'layout_reference' | 'screenshot'
export type ExecutionMode = 'plan' | 'agent' | 'auto'
export type ApprovalMode = ExecutionMode

export interface ChatRequestPayload {
  session_id?: string
  thread_id?: string
  message: string
  interview?: boolean
  generate_now?: boolean
  images?: string[]
  image_intent?: ImageIntent
  execution_mode?: ExecutionMode
  executionMode?: ExecutionMode
  /** @deprecated use execution_mode for API payloads and executionMode in UI code. */
  approval_mode?: ApprovalMode
  target_pages?: string[]
  mentioned_files?: string[]
  style_reference?: ChatStyleReference
  resume?: Record<string, unknown>
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

// ProductDoc Types
export type ProductDocStatus = 'draft' | 'confirmed' | 'outdated'

export interface ProductDoc {
  id: string
  sessionId: string
  content: string
  structured: ProductDocStructured
  version: number
  status: ProductDocStatus
  createdAt: Date
  updatedAt: Date
}

export interface ProductDocStructured {
  projectName: string
  description: string
  targetAudience: string
  goals: string[]
  features: ProductDocFeature[]
  designDirection: DesignDirection
  pages: ProductDocPage[]
  constraints: string[]
}

export interface ProductDocFeature {
  name: string
  description: string
  priority: 'must' | 'should' | 'nice'
}

export interface DesignDirection {
  style: string
  colorPreference: string
  tone: string
  referenceSites: string[]
}

export interface ProductDocPage {
  title: string
  slug: string
  purpose: string
  sections: string[]
  required: boolean
}

// Page & PageVersion Types (v04 multi-page support)
export interface Page {
  id: string
  sessionId: string
  title: string
  slug: string
  description: string
  orderIndex: number
  currentVersionId: number | null
  createdAt: Date
  updatedAt: Date
}

export type VersionSource = 'auto' | 'manual' | 'rollback'

export interface PageVersion {
  id: number
  pageId: string
  version: number
  description: string | null
  createdAt: Date
  source?: VersionSource
  isPinned?: boolean
  isReleased?: boolean
  available?: boolean
  fallbackUsed?: boolean
  previewable?: boolean
}

export interface PagePreview {
  pageId: string
  slug: string
  html: string
  version: number
}

// Versioning Types (v05)
export interface VersionMetadata {
  is_pinned: boolean
  is_released: boolean
  source: VersionSource
  created_at: string
  available: boolean
}

export interface ProjectSnapshot extends VersionMetadata {
  id: string
  session_id: string
  snapshot_number: number
  label: string | null
  page_count: number
}

export interface ProjectSnapshotListResponse {
  snapshots: ProjectSnapshot[]
  total?: number
}

export interface SnapshotRollbackResponse {
  message: string
  new_snapshot: ProjectSnapshot
  restored_pages: string[]
}

export interface SnapshotPinResponse {
  message?: string
  snapshot: ProjectSnapshot
  current_pinned?: string[]
}

export interface ProductDocHistory extends VersionMetadata {
  id: number
  product_doc_id: string
  version: number
  content?: string
  structured?: Record<string, unknown>
  change_summary: string
}

export interface ProductDocHistoryListResponse {
  history: ProductDocHistory[]
  total: number
  pinned_count: number
}

export interface ProductDocHistoryResponse extends ProductDocHistory {
  content: string
  structured: Record<string, unknown>
}

export interface ProductDocHistoryPinResponse {
  message?: string
  history?: ProductDocHistory
  current_pinned?: number[]
}

export interface PageVersionRecord extends VersionMetadata {
  id: number
  page_id: string
  version: number
  description: string | null
  fallback_used?: boolean
  previewable?: boolean
}

export interface PageVersionListResponse {
  versions: PageVersionRecord[]
  current_version_id?: number | null
}

export interface PageVersionPreview {
  id: number
  version: number
  html: string
  description: string | null
  fallback_used: boolean
  created_at: string
}

export interface PageVersionPinResponse {
  message?: string
  version: PageVersionRecord
}

// API Response Types
export interface SessionResponse {
  id: string
  title: string
  created_at: string
  updated_at: string
  current_version: number | null
  product_type: string | null
  complexity: string | null
  skill_id: string | null
  doc_tier: string | null
  style_reference_mode: string | null
  model_classifier: string | null
  model_writer: string | null
  model_expander: string | null
  model_validator: string | null
  model_style_refiner: string | null
  build_status: string | null
  message_count: number
  version_count: number
  preview_html?: string | null
  preview_url?: string
}

export interface SessionMetadataResponse {
  session_id: string
  graph_state: Record<string, unknown> | null
  build_status: 'pending' | 'building' | 'success' | 'failed'
  build_artifacts: Record<string, unknown> | null
  aesthetic_scores: Record<string, unknown> | null
  updated_at: string | null
}

export interface SessionRevertResponse {
  success: boolean
  current_version: number
  preview_url: string
  preview_html: string
}

export interface SettingsResponse {
  api_key: string
  has_api_key?: boolean
  model: string | null
  temperature: number | null
  max_tokens: number | null
  output_dir: string | null
  auto_save: boolean | null
  available_models: ModelOption[]
}

export interface ProductDocResponse {
  id: string
  session_id: string
  content: string
  structured: Record<string, unknown>
  version: number
  status: string
  created_at: string
  updated_at: string
}

export interface PageResponse {
  id: string
  session_id: string
  title: string
  slug: string
  description: string
  order_index: number
  current_version_id: number | null
  created_at: string
  updated_at: string
}

// File Tree Types (v04 Code Tab support)
export interface FileTreeNode {
  name: string
  path: string
  type: 'file' | 'directory'
  size?: number
  children?: FileTreeNode[]
}

export interface FileContent {
  path: string
  content: string
  language: string
  size: number
}

// Export Types (v04 export functionality)
export interface ExportManifest {
  version: string
  exported_at: string
  session_id: string
  product_doc: {
    status: string
    included: boolean
  }
  pages: ExportPageInfo[]
  assets: ExportAssetInfo[]
  global_style?: {
    primary_color?: string
    font_family?: string
  }
}

export interface ExportPageInfo {
  slug: string
  title: string
  path: string
  status: 'success' | 'failed'
  size?: number
  version?: number
  error?: string
}

export interface ExportAssetInfo {
  path: string
  size?: number
}
