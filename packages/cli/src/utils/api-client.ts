import axios, { type AxiosInstance, type AxiosRequestConfig } from 'axios'
import config from '../config.js'
import Logger from './logger.js'

export interface StreamMessage<T = unknown> {
  type: 'data' | 'error' | 'done'
  data: T
}

export class ApiClient {
  private client: AxiosInstance
  private logger: Logger

  constructor(baseURL?: string, logger?: Logger) {
    this.logger = logger || new Logger()
    this.client = axios.create({
      baseURL: baseURL || config.backendUrl,
      timeout: 300000,
      headers: {
        'Content-Type': 'application/json',
      },
    })
    this.setupInterceptors()
  }

  private setupInterceptors(): void {
    this.client.interceptors.request.use(
      (requestConfig) => {
        this.logger.debug(`API Request: ${requestConfig.method?.toUpperCase()} ${requestConfig.url}`)
        return requestConfig
      },
      (error: unknown) => {
        this.logger.error('Request setup error')
        return Promise.reject(error)
      }
    )

    this.client.interceptors.response.use(
      (response) => {
        this.logger.debug(`API Response: ${response.status} ${response.config.url}`)
        return response
      },
      async (error: unknown) => {
        if (axios.isAxiosError(error) && error.response) {
          this.logger.debug(`API Error: ${error.response.status} ${error.response.config.url}`)
        } else if (axios.isAxiosError(error) && error.request) {
          this.logger.debug('API Error: No response received')
        } else if (error instanceof Error) {
          this.logger.debug(`API Error: ${error.message}`)
        }
        return Promise.reject(error)
      }
    )
  }

  async get<T>(url: string, requestConfig?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.get<T>(url, requestConfig)
    return response.data
  }

  async post<T>(url: string, data?: unknown, requestConfig?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.post<T>(url, data, requestConfig)
    return response.data
  }

  async put<T>(url: string, data?: unknown, requestConfig?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.put<T>(url, data, requestConfig)
    return response.data
  }

  async delete<T>(url: string, requestConfig?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.delete<T>(url, requestConfig)
    return response.data
  }

  async withRetry<T>(fn: () => Promise<T>, maxRetries = 3, baseDelay = 1000): Promise<T> {
    for (let attempt = 1; attempt <= maxRetries; attempt += 1) {
      try {
        return await fn()
      } catch (error) {
        const isLastAttempt = attempt === maxRetries
        if (axios.isAxiosError(error) && error.response?.status === 429) {
          const delay = baseDelay * 2 ** (attempt - 1)
          this.logger.warning(`Rate limited. Retrying in ${delay}ms... (attempt ${attempt}/${maxRetries})`)
          if (!isLastAttempt) {
            await this.sleep(delay)
            continue
          }
        }
        if (isLastAttempt) {
          throw error
        }
        this.logger.debug(`Request failed. Retrying... (attempt ${attempt}/${maxRetries})`)
        await this.sleep(baseDelay * attempt)
      }
    }
    throw new Error('Max retries exceeded')
  }

  async *stream<T = unknown>(url: string, data?: unknown): AsyncGenerator<StreamMessage<T>> {
    yield* this.streamRequest<T>(() =>
      this.client.post(url, data, {
        responseType: 'stream',
        headers: { Accept: 'text/event-stream' },
        timeout: 0,
      })
    )
  }

  async *streamGet<T = unknown>(url: string, params?: unknown): AsyncGenerator<StreamMessage<T>> {
    yield* this.streamRequest<T>(() =>
      this.client.get(url, {
        params,
        responseType: 'stream',
        headers: { Accept: 'text/event-stream' },
        timeout: 0,
      })
    )
  }

  private async *streamRequest<T>(
    request: () => Promise<{ data: AsyncIterable<Buffer | string> }>
  ): AsyncGenerator<StreamMessage<T>> {
    try {
      const response = await request()
      let buffer = ''
      for await (const chunk of response.data) {
        buffer += chunk.toString()
        const parts = buffer.split('\n')
        buffer = parts.pop() || ''
        for (const line of parts) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data:')) continue
          const payload = trimmed.replace(/^data:\s*/, '')
          if (payload === '[DONE]') {
            yield { type: 'done', data: '' as T }
            return
          }
          try {
            const parsed = JSON.parse(payload) as T | { error?: unknown }
            if (parsed && typeof parsed === 'object' && 'error' in parsed) {
              yield { type: 'error', data: parsed.error as T }
              continue
            }
            yield { type: 'data', data: parsed as T }
          } catch {
            yield { type: 'data', data: payload as T }
          }
        }
      }
    } catch (error) {
      yield {
        type: 'error',
        data: (error instanceof Error ? error.message : String(error)) as T,
      }
    }
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms))
  }

  async healthCheck(): Promise<boolean> {
    try {
      await this.get('/health')
      return true
    } catch {
      return false
    }
  }
}

export default ApiClient
