import chalk from 'chalk'
import path from 'node:path'
import Logger from '../utils/logger.js'
import { ApiClient } from '../utils/api-client.js'
import { displaySessionNotFound } from './history/list.js'
import type { Command } from 'commander'

interface ExportOptions {
  output?: string
  version?: string
  format?: string
}

interface SessionSummary {
  id: string
  title: string
  current_version: number
}

interface SessionListResponse {
  sessions?: SessionSummary[]
}

interface ExportResponse {
  file_path: string
  assets_file?: string
}

export async function exportCommand(
  sessionId: string | undefined,
  options: ExportOptions
): Promise<void> {
  const logger = new Logger()
  const apiClient = new ApiClient()
  let resolvedSessionId = sessionId

  try {
    if (!resolvedSessionId) {
      const latest = await apiClient.get<SessionListResponse>('/api/sessions?limit=1&offset=0')
      if (!latest.sessions || latest.sessions.length === 0) {
        console.log()
        console.log(chalk.gray('No sessions are available to export'))
        console.log(chalk.gray('Run instant-coffee chat first'))
        console.log()
        return
      }
      resolvedSessionId = latest.sessions[0].id
      console.log(chalk.gray(`Using latest session: ${resolvedSessionId}`))
    }

    const session = await apiClient.get<SessionSummary>(`/api/sessions/${resolvedSessionId}`)
    const targetVersion = parseVersion(options.version, session.current_version)
    if (targetVersion === null) {
      console.log(chalk.red('Invalid version'))
      console.log(chalk.gray('Use --version <number> or --version latest'))
      return
    }

    const exportRequest: {
      session_id: string
      version: number
      output_dir?: string
    } = {
      session_id: resolvedSessionId,
      version: targetVersion,
    }
    if (options.output) {
      exportRequest.output_dir = path.resolve(process.cwd(), options.output)
    }

    console.log()
    console.log(chalk.cyan('Exporting...'))
    const response = await apiClient.post<ExportResponse>('/api/export', exportRequest)

    console.log()
    console.log(chalk.green('Export succeeded'))
    console.log()
    console.log(chalk.gray('Session:'), chalk.white(`${resolvedSessionId} (${session.title})`))
    console.log(
      chalk.gray('Version:'),
      chalk.white(`v${targetVersion}` + (targetVersion === session.current_version ? ' (current)' : ''))
    )
    console.log()
    console.log(chalk.gray('File:'), chalk.white(response.file_path))
    if (response.assets_file) {
      console.log(chalk.gray('Manifest:'), chalk.white(response.assets_file))
    }
    console.log()

    const absolutePath = path.isAbsolute(response.file_path)
      ? response.file_path
      : path.resolve(process.cwd(), response.file_path)
    console.log(chalk.gray('Open with:'))
    console.log(chalk.cyan(`   open ${absolutePath}`))
    console.log()
  } catch (error) {
    if (isHttpStatus(error, 404)) {
      if (resolvedSessionId) {
        displaySessionNotFound(resolvedSessionId)
      } else {
        console.log()
        console.log(chalk.red.bold('No exportable session was found'))
        console.log()
      }
    } else if (isHttpStatus(error, 400)) {
      console.log()
      console.log(chalk.red('Export failed:'), chalk.white(httpDetail(error) || 'Invalid request'))
      console.log()
    } else {
      logger.error(`Export failed: ${errorMessage(error)}`)
    }
  }
}

export function registerExportCommand(program: Command): void {
  program
    .command('export [sessionId]')
    .description('Export sessions or generated pages')
    .option('-o, --output <path>', 'Output directory')
    .option('-v, --version <number>', 'Specific version to export (default: latest)')
    .option('-f, --format <format>', 'Export format (html, json, zip)', 'html')
    .action(async (sessionId: string | undefined, options: ExportOptions) => {
      try {
        await exportCommand(sessionId, options)
      } catch (error) {
        console.error(chalk.red('Export command failed:'), errorMessage(error))
        process.exit(1)
      }
    })
}

function parseVersion(input: string | undefined, currentVersion: number): number | null {
  const versionInput = input?.trim()
  if (!versionInput || versionInput === 'latest') {
    return currentVersion
  }
  const normalized = versionInput.toLowerCase().startsWith('v')
    ? versionInput.slice(1)
    : versionInput
  const parsed = Number.parseInt(normalized, 10)
  return Number.isNaN(parsed) ? null : parsed
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

function httpDetail(error: unknown): string | undefined {
  if (typeof error !== 'object' || error === null || !('response' in error)) return undefined
  const response = (error as { response?: { data?: { detail?: unknown } } }).response
  return typeof response?.data?.detail === 'string' ? response.data.detail : undefined
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
