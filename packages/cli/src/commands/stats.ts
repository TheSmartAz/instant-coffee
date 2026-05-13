import chalk from 'chalk'
import Table from 'cli-table3'
import Logger from '../utils/logger.js'
import { ApiClient } from '../utils/api-client.js'
import {
  formatAgentLabel,
  formatCost,
  formatNumber,
  formatPercentage,
  separator,
} from '../utils/stats-formatter.js'
import { displaySessionNotFound, displaySessionStats } from './stats/session.js'
import type { OverallStats, SessionStats, TokenBucket } from './stats/types.js'
import type { Command } from 'commander'

interface SessionSummary {
  id: string
  title?: string
  created_at?: string
}

function displayOverallStats(stats: OverallStats): void {
  console.log()
  console.log(chalk.cyan.bold('Token usage statistics'))
  console.log(chalk.gray(separator('-', 60)))
  console.log()

  console.log(chalk.yellow('Today:'))
  console.log(chalk.gray('  Tokens:'), chalk.white(formatNumber(stats.today.tokens)))
  console.log(chalk.gray('  Cost:'), chalk.white(formatCost(stats.today.cost_usd)))
  console.log(chalk.gray('  API calls:'), chalk.white(`${stats.today.calls}`))
  console.log()

  console.log(chalk.yellow('This week:'))
  console.log(chalk.gray('  Tokens:'), chalk.white(formatNumber(stats.week.tokens)))
  console.log(chalk.gray('  Cost:'), chalk.white(formatCost(stats.week.cost_usd)))
  console.log(chalk.gray('  API calls:'), chalk.white(`${stats.week.calls}`))
  console.log()

  console.log(chalk.yellow('Total:'))
  console.log(chalk.gray('  Tokens:'), chalk.white(formatNumber(stats.total.tokens)))
  console.log(chalk.gray('  Cost:'), chalk.white(formatCost(stats.total.cost_usd)))
  console.log(chalk.gray('  API calls:'), chalk.white(`${stats.total.calls}`))
  console.log(chalk.gray('  Sessions:'), chalk.white(`${stats.total.sessions}`))
  if (stats.total.pages !== undefined) {
    console.log(chalk.gray('  Pages:'), chalk.white(`${stats.total.pages}`))
  }
  console.log()

  if (stats.by_agent && Object.keys(stats.by_agent).length > 0) {
    console.log(chalk.cyan('By agent:'))
    console.log(chalk.gray(separator('-', 60)))
    const agentTable = new Table({
      head: [chalk.cyan('Agent'), chalk.cyan('Tokens'), chalk.cyan('Cost'), chalk.cyan('Share')],
      colWidths: [15, 15, 15, 15],
      style: {
        head: [],
        border: ['gray'],
      },
    })
    Object.entries(stats.by_agent).forEach(([agent, data]: [string, TokenBucket]) => {
      agentTable.push([
        formatAgentLabel(agent),
        formatNumber(data.tokens),
        formatCost(data.cost_usd || 0),
        formatPercentage(data.tokens, stats.total.tokens),
      ])
    })
    console.log(agentTable.toString())
    console.log()
  }
}

function displayEmptyStats(): void {
  console.log()
  console.log(chalk.cyan.bold('Token usage statistics'))
  console.log(chalk.gray(separator('-', 60)))
  console.log()
  console.log(chalk.gray('No usage data yet'))
  console.log()
  console.log(chalk.gray('Start with:'))
  console.log(chalk.cyan('   instant-coffee chat'))
  console.log()
}

export async function statsCommand(options: { session?: string }): Promise<void> {
  const logger = new Logger()
  const apiClient = new ApiClient()

  try {
    if (options.session) {
      try {
        const session = await apiClient.get<SessionSummary>(`/api/sessions/${options.session}`)
        const sessionStats = await apiClient.get<SessionStats>(`/api/stats/session/${options.session}`)
        if (!sessionStats || !sessionStats.session_id) {
          displaySessionNotFound(options.session)
          return
        }
        displaySessionStats({
          ...sessionStats,
          title: session?.title,
          created_at: session?.created_at,
        })
      } catch (error) {
        if (isHttpStatus(error, 404)) {
          displaySessionNotFound(options.session)
        } else {
          logger.error(`Failed to load session statistics: ${errorMessage(error)}`)
        }
      }
      return
    }

    const stats = await apiClient.get<OverallStats>('/api/stats')
    const hasData = stats.total.tokens > 0 || stats.total.calls > 0
    if (!hasData) {
      displayEmptyStats()
      return
    }
    displayOverallStats(stats)
  } catch (error) {
    logger.error(`Failed to load statistics: ${errorMessage(error)}`)
    logger.debug('Make sure the backend service is running')
  }
}

export function registerStatsCommand(program: Command): void {
  program
    .command('stats [sessionId]')
    .description('View usage statistics and token consumption')
    .option('-j, --json', 'Output statistics as JSON')
    .action(async (sessionId: string | undefined) => {
      try {
        await statsCommand({ session: sessionId })
      } catch (error) {
        console.error(chalk.red('Stats command failed:'), errorMessage(error))
        process.exit(1)
      }
    })
}

function isHttpStatus(error: unknown, status: number): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof (error as { response?: { status?: unknown } }).response?.status === 'number' &&
    (error as { response: { status: number } }).response.status === status
  )
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
