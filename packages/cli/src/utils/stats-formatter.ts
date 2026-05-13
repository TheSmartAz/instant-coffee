import chalk, { type ChalkInstance } from 'chalk'

export function formatNumber(n: number): string {
  return n.toLocaleString('en-US')
}

export function formatCost(cost: number, decimals = 5): string {
  return `$${cost.toFixed(decimals)}`
}

export function formatPercentage(value: number, total: number): string {
  if (total === 0) return '0.0%'
  return `${((value / total) * 100).toFixed(1)}%`
}

export function formatDateTime(isoString: string): string {
  const date = new Date(isoString)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}`
}

export function formatTime(isoString: string): string {
  const date = new Date(isoString)
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `[${hours}:${minutes}:${seconds}]`
}

export function separator(char = '-', length = 60): string {
  return char.repeat(length)
}

export function formatAgentName(agent: string): string {
  const agentNames: Record<string, string> = {
    interview: 'Interview',
    generation: 'Generation',
    refinement: 'Refinement',
  }
  return agentNames[agent] || agent
}

export function calculateAverage(totalTokens: number, callCount: number): number {
  if (callCount === 0) return 0
  return Math.round(totalTokens / callCount)
}

export function getAgentColor(agent: string): ChalkInstance {
  const colors: Record<string, ChalkInstance> = {
    interview: chalk.cyan,
    generation: chalk.green,
    refinement: chalk.yellow,
  }
  return colors[agent] || chalk.white
}

export function formatAgentLabel(agent: string): string {
  return getAgentColor(agent)(formatAgentName(agent))
}

export function padString(
  str: string,
  width: number,
  align: 'left' | 'right' | 'center' = 'left'
): string {
  if (str.length >= width) return str.substring(0, width)
  const padding = width - str.length
  switch (align) {
    case 'right':
      return ' '.repeat(padding) + str
    case 'center': {
      const leftPad = Math.floor(padding / 2)
      const rightPad = padding - leftPad
      return ' '.repeat(leftPad) + str + ' '.repeat(rightPad)
    }
    default:
      return str + ' '.repeat(padding)
  }
}
