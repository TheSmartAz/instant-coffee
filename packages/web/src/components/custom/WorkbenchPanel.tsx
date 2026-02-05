import * as React from 'react'
import { Eye, Code, FileText } from 'lucide-react'
import { cn } from '@/lib/utils'
import { PreviewPanel, type PageInfo } from './PreviewPanel'
import { CodePanel } from './CodePanel'
import { ProductDocPanel } from './ProductDocPanel'

export type WorkbenchTab = 'preview' | 'code' | 'product-doc'

export interface WorkbenchPanelProps {
  sessionId: string
  appMode?: boolean
  onAppModeChange?: (next: boolean) => void
  onBuildFromDoc?: () => void
  buildDisabled?: boolean
  previewVersion?: number | null
  productDocVersion?: number | null

  // Tab management
  activeTab: WorkbenchTab
  onTabChange: (tab: WorkbenchTab) => void

  // Preview tab props
  pages?: PageInfo[]
  selectedPageId?: string | null
  onSelectPage?: (pageId: string) => void
  previewHtml?: string | null
  previewUrl?: string | null
  isRefreshing?: boolean
  isExporting?: boolean
  onRefresh?: () => void
  onRefreshPage?: (pageId: string) => void
  onExport?: () => void
}

interface TabInfo {
  id: WorkbenchTab
  label: string
  icon: React.ComponentType<{ className?: string }>
}

const TABS: TabInfo[] = [
  { id: 'preview', label: 'Preview', icon: Eye },
  { id: 'code', label: 'Code', icon: Code },
  { id: 'product-doc', label: 'Product doc', icon: FileText },
]

export function WorkbenchPanel({
  sessionId,
  appMode,
  onAppModeChange,
  onBuildFromDoc,
  buildDisabled,
  previewVersion,
  productDocVersion,
  activeTab,
  onTabChange,
  pages,
  selectedPageId,
  onSelectPage,
  previewHtml,
  previewUrl,
  isRefreshing,
  isExporting,
  onRefresh,
  onRefreshPage,
  onExport,
}: WorkbenchPanelProps) {
  const handleTabChange = (tab: WorkbenchTab) => {
    onTabChange(tab)
  }

  const previewVersionLabel = previewVersion ? `v${previewVersion}` : null
  const productDocVersionLabel = productDocVersion ? `v${productDocVersion}` : null

  return (
    <div className="workbench-panel flex h-full flex-col overflow-hidden">
      {/* Tab Bar */}
      <div className="tab-bar flex h-14 items-center border-b border-border bg-muted/30 px-2">
        {TABS.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          const versionLabel =
            tab.id === 'preview'
              ? previewVersionLabel
              : tab.id === 'product-doc'
                ? productDocVersionLabel
                : null

          return (
            <button
              key={tab.id}
              type="button"
              className={cn(
                'tab flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors',
                'relative border-b-2 border-transparent',
                'hover:text-foreground',
                isActive
                  ? 'text-foreground border-primary'
                  : 'text-muted-foreground hover:bg-muted/50'
              )}
              onClick={() => handleTabChange(tab.id)}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
              {versionLabel ? (
                <span className="rounded-full bg-background px-2 py-0.5 text-[10px] font-semibold text-muted-foreground ring-1 ring-border">
                  {versionLabel}
                </span>
              ) : null}
            </button>
          )
        })}
      </div>

      {/* Tab Content */}
      <div className="workbench-content flex-1 overflow-hidden">
        <div className={cn('h-full', activeTab === 'preview' ? 'block' : 'hidden')}>
          <PreviewPanel
            sessionId={sessionId}
            appMode={appMode}
            onAppModeChange={onAppModeChange}
            htmlContent={previewHtml ?? undefined}
            previewUrl={previewUrl ?? undefined}
            onRefresh={onRefresh}
            onRefreshPage={onRefreshPage}
            onExport={onExport}
            isRefreshing={isRefreshing}
            isExporting={isExporting}
            pages={pages}
            selectedPageId={selectedPageId}
            onSelectPage={onSelectPage}
          />
        </div>

        <div className={cn('h-full', activeTab === 'code' ? 'block' : 'hidden')}>
          {sessionId ? (
            <CodePanel sessionId={sessionId} />
          ) : (
            <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
              Please create a project first
            </div>
          )}
        </div>

        <div className={cn('h-full', activeTab === 'product-doc' ? 'block' : 'hidden')}>
          {sessionId ? (
            <ProductDocPanel
              sessionId={sessionId}
              onBuild={onBuildFromDoc}
              buildDisabled={buildDisabled}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
              Please create a project first
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
