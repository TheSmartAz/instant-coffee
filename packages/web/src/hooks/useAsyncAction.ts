import * as React from 'react'
import { classifyError, type RequestError, userFriendlyMessage } from '@/api/client'
import { toast } from '@/hooks/use-toast'

type ToastPayload = {
  title: string
  description?: string
}

type ToastFactory<T> = ToastPayload | ((value: T) => ToastPayload | null | undefined)
type ErrorToastFactory =
  | ToastPayload
  | ((error: RequestError) => ToastPayload | null | undefined)

interface RunAsyncActionOptions<T> {
  onStart?: () => void
  onSuccess?: (value: T) => void | Promise<void>
  onError?: (error: RequestError) => void | Promise<void>
  onFinally?: () => void
  successToast?: ToastFactory<T>
  errorToast?: ErrorToastFactory
  fallbackErrorMessage?: string
  rethrow?: boolean
}

const resolveToast = <T,>(factory: ToastFactory<T>, value: T) =>
  typeof factory === 'function' ? factory(value) : factory

const resolveErrorToast = (factory: ErrorToastFactory, error: RequestError) =>
  typeof factory === 'function' ? factory(error) : factory

export function useAsyncAction() {
  const [pendingCount, setPendingCount] = React.useState(0)

  const runAction = React.useCallback(
    async <T>(
      action: () => Promise<T>,
      options: RunAsyncActionOptions<T> = {}
    ): Promise<T | undefined> => {
      setPendingCount((count) => count + 1)
      options.onStart?.()

      try {
        const result = await action()
        await options.onSuccess?.(result)

        if (options.successToast) {
          const payload = resolveToast(options.successToast, result)
          if (payload) {
            toast(payload)
          }
        }

        return result
      } catch (error) {
        const classified = classifyError(error)
        await options.onError?.(classified)

        if (options.errorToast) {
          const payload = resolveErrorToast(options.errorToast, classified)
          if (payload) {
            toast({
              ...payload,
              description:
                payload.description ??
                options.fallbackErrorMessage ??
                userFriendlyMessage(classified),
            })
          }
        }

        if (options.rethrow) {
          throw classified
        }

        return undefined
      } finally {
        options.onFinally?.()
        setPendingCount((count) => Math.max(0, count - 1))
      }
    },
    []
  )

  return {
    runAction,
    isRunning: pendingCount > 0,
  }
}

