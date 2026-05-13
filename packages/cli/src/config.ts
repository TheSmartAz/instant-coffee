import dotenv from 'dotenv'
import path from 'node:path'

dotenv.config()

export interface Config {
  backendUrl: string
  verbose: boolean
  outputDir: string
}

function getEnvVar(key: string, defaultValue: string): string {
  return process.env[key] || defaultValue
}

function getOutputDir(): string {
  const outputDir = getEnvVar('OUTPUT_DIR', '~/instant-coffee-output')
  if (outputDir.startsWith('~')) {
    return path.join(process.env.HOME || '', outputDir.slice(1))
  }
  return outputDir
}

export const config: Config = {
  backendUrl: getEnvVar('BACKEND_URL', 'http://localhost:8000'),
  verbose: getEnvVar('VERBOSE', 'false').toLowerCase() === 'true',
  outputDir: getOutputDir(),
}

export default config
