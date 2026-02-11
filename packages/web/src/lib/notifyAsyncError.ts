import { classifyError, type RequestError, userFriendlyMessage } from '@/api/client'
import { toast } from '@/hooks/use-toast'

interface NotifyAsyncErrorOptions {
  title?: string
  fallback?: string
  loggerPrefix?: string
  silentStatuses?: number[]
}

const DEFAULT_ERROR_TITLE = 'Request failed'

export function notifyAsyncError(
  error: unknown,
  {
    title = DEFAULT_ERROR_TITLE,
    fallback,
    loggerPrefix,
    silentStatuses = [],
  }: NotifyAsyncErrorOptions = {}
): RequestError {
  const classified = classifyError(error)
  const message = fallback ?? userFriendlyMessage(classified)

  if (!silentStatuses.includes(classified.status ?? -1)) {
    toast({ title, description: message })
  }

  if (loggerPrefix) {
    console.error(loggerPrefix, classified)
  }

  return classified
}
