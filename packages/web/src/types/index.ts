export type MessageRole = 'user' | 'assistant'

export type ChatStepStatus = 'in_progress' | 'done' | 'failed'

export interface ChatStep {
  id: string
  label: string
  status?: ChatStepStatus
  timestamp?: Date
  kind?: 'agent' | 'tool'
  key?: string
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
  affectedPages?: string[]
  activePageSlug?: string
  disambiguation?: Disambiguation
  hidden?: boolean
  assets?: ChatAsset[]
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

export interface ChatRequestPayload {
  session_id?: string
  message: string
  interview?: boolean
  generate_now?: boolean
  images?: string[]
  target_pages?: string[]
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
