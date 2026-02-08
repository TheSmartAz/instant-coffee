import { buildUrl } from '@/api/client'
import type { AssetRef, AssetType } from '@/types'

export type UploadAssetOptions = {
  onProgress?: (progress: number) => void
  signal?: AbortSignal
}

const buildAssetUrl = (sessionId: string, assetType: AssetType) => {
  const params = new URLSearchParams({ asset_type: assetType })
  return buildUrl(`/api/sessions/${sessionId}/assets?${params.toString()}`)
}

const parseJsonResponse = (xhr: XMLHttpRequest) => {
  if (xhr.responseType === 'json' && xhr.response) return xhr.response
  if (!xhr.responseText) return null
  try {
    return JSON.parse(xhr.responseText)
  } catch {
    return null
  }
}

export async function uploadAsset(
  sessionId: string,
  file: File,
  assetType: AssetType,
  options?: UploadAssetOptions
): Promise<AssetRef> {
  const formData = new FormData()
  formData.append('file', file)

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const url = buildAssetUrl(sessionId, assetType)

    xhr.open('POST', url)
    xhr.responseType = 'json'

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) return
      const progress = Math.round((event.loaded / event.total) * 100)
      options?.onProgress?.(progress)
    }

    xhr.onload = () => {
      const data = parseJsonResponse(xhr)
      if (xhr.status >= 200 && xhr.status < 300 && data) {
        resolve(data as AssetRef)
        return
      }
      const message =
        (data && (data.message || data.detail)) ||
        xhr.statusText ||
        'Asset upload failed'
      const error = new Error(message)
      ;(error as Error & { status?: number; data?: unknown }).status = xhr.status
      ;(error as Error & { status?: number; data?: unknown }).data = data
      reject(error)
    }

    xhr.onerror = () => {
      reject(new Error('Asset upload failed'))
    }

    if (options?.signal) {
      const abortHandler = () => {
        xhr.abort()
        reject(new Error('Asset upload cancelled'))
      }
      if (options.signal.aborted) {
        abortHandler()
        return
      }
      options.signal.addEventListener('abort', abortHandler, { once: true })
    }

    xhr.send(formData)
  })
}

export const resolveAssetUrl = (url: string) => buildUrl(url)
