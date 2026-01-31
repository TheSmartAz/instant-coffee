import * as React from 'react'
import { ChevronDown, ChevronRight, Coins } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { SessionTokenSummary, TokenUsage } from '@/types'

interface TokenDisplayProps {
  usage: SessionTokenSummary
  showDetails?: boolean
  className?: string
}

interface TokenUsageRowProps {
  label: string
  usage: TokenUsage
  showLabel?: boolean
  className?: string
}

function TokenUsageRow({ label, usage, showLabel = true, className }: TokenUsageRowProps) {
  return (
    <div className={cn('flex items-center justify-between gap-4 text-sm', className)}>
      {showLabel ? (
        <span className="text-muted-foreground">{label}</span>
      ) : (
        <span className="font-medium text-foreground">{label}</span>
      )}
      <div className="flex items-center gap-4">
        <span className="text-foreground">{usage.total_tokens.toLocaleString()} tokens</span>
        <span className="min-w-[60px] text-right font-mono text-emerald-600">
          ${usage.cost_usd.toFixed(4)}
        </span>
      </div>
    </div>
  )
}

interface TokenProgressBarProps {
  input: number
  output: number
  total: number
  className?: string
}

function TokenProgressBar({ input, output, total, className }: TokenProgressBarProps) {
  const inputPercent = total > 0 ? (input / total) * 100 : 0
  const outputPercent = total > 0 ? (output / total) * 100 : 0

  return (
    <div className={cn('flex h-2 w-full overflow-hidden rounded-full bg-muted', className)}>
      {inputPercent > 0 && (
        <div
          className="bg-blue-500"
          style={{ width: `${inputPercent}%` }}
          title={`Input: ${input.toLocaleString()} tokens`}
        />
      )}
      {outputPercent > 0 && (
        <div
          className="bg-emerald-500"
          style={{ width: `${outputPercent}%` }}
          title={`Output: ${output.toLocaleString()} tokens`}
        />
      )}
    </div>
  )
}

export function TokenDisplay({ usage, showDetails = false, className }: TokenDisplayProps) {
  const [isExpanded, setIsExpanded] = React.useState(showDetails)
  const agentEntries = React.useMemo(
    () => Object.entries(usage.by_agent).sort(([, a], [, b]) => b.total_tokens - a.total_tokens),
    [usage.by_agent]
  )

  if (usage.total.total_tokens === 0) {
    return null
  }

  return (
    <div className={cn('rounded-lg border border-border bg-background', className)}>
      <button
        type="button"
        onClick={() => setIsExpanded((prev) => !prev)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
        aria-expanded={isExpanded}
      >
        <Coins className="h-4 w-4 text-amber-500" />
        <span className="text-sm font-semibold text-foreground">Token Usage</span>
        <div className="flex items-center gap-3">
          <span className="text-sm text-foreground">
            {usage.total.total_tokens.toLocaleString()} tokens
          </span>
          <span className="min-w-[50px] text-right font-mono text-sm font-semibold text-emerald-600">
            ${usage.total.cost_usd.toFixed(4)}
          </span>
        </div>
        {isExpanded ? (
          <ChevronDown className="ml-auto h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="ml-auto h-4 w-4 text-muted-foreground" />
        )}
      </button>

      {isExpanded ? (
        <div className="border-t border-border px-4 py-3 space-y-3">
          {/* Input/Output breakdown */}
          <div className="space-y-2">
            <TokenProgressBar
              input={usage.total.input_tokens}
              output={usage.total.output_tokens}
              total={usage.total.total_tokens}
            />
            <div className="flex items-center justify-between gap-4 text-xs text-muted-foreground">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-blue-500" />
                <span>Input: {usage.total.input_tokens.toLocaleString()}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-emerald-500" />
                <span>Output: {usage.total.output_tokens.toLocaleString()}</span>
              </div>
            </div>
          </div>

          {/* Agent breakdown */}
          {agentEntries.length > 0 ? (
            <div className="space-y-2">
              <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Breakdown by Agent
              </div>
              <div className="space-y-1">
                {agentEntries.map(([agent, agentUsage]) => (
                  <TokenUsageRow
                    key={agent}
                    label={agent}
                    usage={agentUsage}
                    showLabel={false}
                    className="pl-2"
                  />
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
