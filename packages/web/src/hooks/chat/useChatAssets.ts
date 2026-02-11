import * as React from 'react'
import { uploadAsset as uploadAssetApi } from '@/api/assets'
import { loadChatAssets, saveChatAssets } from '@/lib/assetStorage'
import { createId } from '@/hooks/useChatUtils'
import type { AssetType, ChatAsset, Message } from '@/types'

const ASSET_TYPE_LABELS: Record<AssetType, string> = {
  logo: 'Logo',
  style_ref: 'Style reference',
  background: 'Background',
  product_image: 'Product image',
}

interface UseChatAssetsOptions {
  sessionId?: string
  sessionIdRef: React.MutableRefObject<string | undefined>
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
}

export function useChatAssets({
  sessionId,
  sessionIdRef,
  setMessages,
}: UseChatAssetsOptions) {
  const [assets, setAssets] = React.useState<ChatAsset[]>(() =>
    loadChatAssets(sessionId)
  )
  const assetsRef = React.useRef<ChatAsset[]>(assets)

  React.useEffect(() => {
    if (!sessionId) {
      setAssets([])
      return
    }
    setAssets(loadChatAssets(sessionId))
  }, [sessionId])

  React.useEffect(() => {
    assetsRef.current = assets
    const activeSessionId = sessionIdRef.current
    if (!activeSessionId) return
    saveChatAssets(activeSessionId, assets)
  }, [assets, sessionIdRef])

  const requireSessionId = React.useCallback(() => {
    const currentSessionId = sessionIdRef.current
    if (!currentSessionId) {
      throw new Error(
        'Start a chat to create a session before uploading assets.'
      )
    }
    return currentSessionId
  }, [sessionIdRef])

  const addAsset = React.useCallback((asset: ChatAsset) => {
    setAssets((prev) => {
      const index = prev.findIndex((item) => item.id === asset.id)
      if (index >= 0) {
        const next = [...prev]
        next[index] = { ...next[index], ...asset }
        return next
      }
      return [...prev, asset]
    })
  }, [])

  const removeAsset = React.useCallback((assetId: string) => {
    setAssets((prev) => prev.filter((asset) => asset.id !== assetId))
  }, [])

  const getAssetById = React.useCallback((assetId: string) => {
    return assetsRef.current.find((asset) => asset.id === assetId) ?? null
  }, [])

  const appendAssetMessage = React.useCallback(
    (asset: ChatAsset) => {
      setMessages((prev) => {
        const alreadyAdded = prev.some(
          (message) =>
            message.assets?.some((item) => item.id === asset.id) ||
            message.content.includes(asset.id)
        )
        if (alreadyAdded) return prev
        const label = ASSET_TYPE_LABELS[asset.assetType] ?? asset.assetType
        return [
          ...prev,
          {
            id: createId(),
            role: 'user',
            content: `Uploaded ${label}`,
            timestamp: new Date(),
            assets: [asset],
          },
        ]
      })
    },
    [setMessages]
  )

  const uploadAsset = React.useCallback(
    async (
      file: File,
      assetType: AssetType,
      options?: { onProgress?: (progress: number) => void }
    ) => {
      const activeSessionId = requireSessionId()
      const assetRef = await uploadAssetApi(activeSessionId, file, assetType, {
        onProgress: options?.onProgress,
      })
      const chatAsset: ChatAsset = {
        ...assetRef,
        assetType,
        name: file.name,
        size: file.size,
        createdAt: new Date().toISOString(),
      }
      addAsset(chatAsset)
      appendAssetMessage(chatAsset)
    },
    [addAsset, appendAssetMessage, requireSessionId]
  )

  return {
    assets,
    addAsset,
    removeAsset,
    getAssetById,
    uploadAsset,
  }
}
