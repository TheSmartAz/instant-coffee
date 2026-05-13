import chalk from 'chalk'
import Table from 'cli-table3'
import {
  calculateAverage,
  formatAgentLabel,
  formatAgentName,
  formatCost,
  formatDateTime,
  formatNumber,
  formatTime,
  padString,
  separator,
} from '../../utils/stats-formatter.js'
import type { SessionStats, TokenBucket } from './types.js'

export function displaySessionStats(stats: SessionStats): void {
  const {
    session_id,
    title,
    created_at,
    total_tokens,
    cost_usd,
    calls,
    by_agent,
    timeline,
  } = stats
  const callCount = calls || 0

  console.log()
  console.log(chalk.cyan.bold(`Session ${session_id} token usage`))
  console.log(chalk.gray(separator('-', 60)))
  console.log()

  console.log(chalk.yellow('Session:'))
  if (title) console.log(chalk.gray('  Title:'), chalk.white(title))
  if (created_at) console.log(chalk.gray('  Created:'), chalk.white(formatDateTime(created_at)))
  console.log(
    chalk.gray('  Total:'),
    chalk.white(`${formatNumber(total_tokens)} tokens`),
    chalk.gray(`(${formatCost(cost_usd)})`)
  )
  console.log(chalk.gray('  Calls:'), chalk.white(`${callCount}`))
  console.log(chalk.gray('  Average:'), chalk.white(`${formatNumber(calculateAverage(total_tokens, callCount))} tokens`))
  console.log()

  if (by_agent && Object.keys(by_agent).length > 0) {
    console.log(chalk.cyan('By agent:'))
    console.log(chalk.gray(separator('-', 60)))
    const agentTable = new Table({
      head: [chalk.cyan('Agent'), chalk.cyan('Tokens'), chalk.cyan('Calls'), chalk.cyan('Average')],
      colWidths: [15, 15, 15, 15],
      style: {
        head: [],
        border: ['gray'],
      },
    })
    Object.entries(by_agent).forEach(([agent, data]: [string, TokenBucket]) => {
      agentTable.push([
        formatAgentLabel(agent),
        formatNumber(data.tokens),
        formatNumber(data.calls || 0),
        formatNumber(calculateAverage(data.tokens, data.calls || 0)),
      ])
    })
    console.log(agentTable.toString())
    console.log()
  }

  if (timeline && timeline.length > 0) {
    console.log(chalk.cyan('Timeline:'))
    console.log(chalk.gray(separator('-', 60)))
    timeline.forEach((entry) => {
      const agentLabel = padString(formatAgentName(entry.agent_type), 12)
      const tokensStr = padString(`${formatNumber(entry.tokens)} tokens`, 12)
      console.log(
        chalk.gray(formatTime(entry.timestamp)),
        chalk.white(agentLabel),
        chalk.gray('|'),
        chalk.white(tokensStr),
        chalk.gray('|'),
        chalk.green(formatCost(entry.cost_usd, 5))
      )
    })
    console.log()
  }
}

export { displaySessionNotFound } from '../history/list.js'
