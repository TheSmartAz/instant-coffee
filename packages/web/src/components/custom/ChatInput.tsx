import * as React from 'react'
import { Loader2, Mic, MicOff, Send, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import type { AssetType, ChatAttachment, ChatStyleReference, ImageIntent, Page } from '@/types'
import { toast } from '@/hooks/use-toast'
import { useSettings } from '@/hooks/useSettings'
import { useMentionState } from '@/hooks/useMentionState'
import { compressImageFile } from '@/lib/imageCompression'
import logoDeepSeek from '@/assets/model-logos/deepseek.png'
import logoGemini from '@/assets/model-logos/gemini.png'
import logoGrok from '@/assets/model-logos/grok.png'
import logoHunyuan from '@/assets/model-logos/hunyuan.png'
import logoKimi from '@/assets/model-logos/kimi.png'
import logoMiniMax from '@/assets/model-logos/minimax.png'
import logoOpenAI from '@/assets/model-logos/openai.png'
import logoQwen from '@/assets/model-logos/qwen.png'
import logoZai from '@/assets/model-logos/zai.png'
import { AssetTypeSelector } from './AssetTypeSelector'
import { ImageThumbnail } from './ImageThumbnail'
import { PageMentionPopover } from './PageMentionPopover'
import { parsePageMentions } from '@/utils/chat'

export interface ChatInputProps {
  onSend: (
    message: string,
    options?: {
      triggerInterview?: boolean
      attachments?: ChatAttachment[]
      imageIntent?: ImageIntent
      targetPages?: string[]
      mentionedFiles?: string[]
      styleReference?: ChatStyleReference
    }
  ) => void
  onAssetUpload?: (
    file: File,
    type: AssetType,
    options?: { onProgress?: (progress: number) => void }
  ) => Promise<void>
  disabled?: boolean
  placeholder?: string
  pages?: Page[]
}

const MAX_ATTACHMENTS = 3
const MAX_FILE_SIZE = 10 * 1024 * 1024
const MAX_ASSET_FILE_SIZE = 10 * 1024 * 1024
const ASSET_ACCEPT_TYPES = 'image/png,image/jpeg,image/webp,image/svg+xml'

const ASSET_TYPE_LABELS: Record<AssetType, string> = {
  logo: 'Logo',
  style_ref: 'Style reference',
  background: 'Background',
  product_image: 'Product image',
}

type SpeechRecognitionLike = {
  continuous: boolean
  interimResults: boolean
  lang: string
  onresult: ((event: SpeechRecognitionEventLike) => void) | null
  onstart: (() => void) | null
  onend: (() => void) | null
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null
  start: () => void
  stop: () => void
}

type SpeechRecognitionResultLike = {
  isFinal: boolean
  0?: { transcript?: string }
}

type SpeechRecognitionEventLike = {
  resultIndex: number
  results: ArrayLike<SpeechRecognitionResultLike>
}

type SpeechRecognitionErrorEventLike = {
  error?: string
}

const getSpeechRecognitionCtor = (): (new () => SpeechRecognitionLike) | null => {
  if (typeof window === 'undefined') return null
  const w = window as typeof window & {
    SpeechRecognition?: new () => SpeechRecognitionLike
    webkitSpeechRecognition?: new () => SpeechRecognitionLike
  }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

const resolveModelLogo = (modelId?: string, label?: string) => {
  const key = `${modelId ?? ''} ${label ?? ''}`.toLowerCase()
  if (key.includes('deepseek')) return logoDeepSeek
  if (key.includes('qwen')) return logoQwen
  if (key.includes('minimax')) return logoMiniMax
  if (key.includes('hunyuan')) return logoHunyuan
  if (key.includes('kimi') || key.includes('moonshot')) return logoKimi
  if (key.includes('z.ai') || key.includes('zai') || key.includes('zhipu')) return logoZai
  if (key.includes('glm')) return logoZai
  if (key.includes('gemini')) return logoGemini
  if (key.includes('grok')) return logoGrok
  if (key.includes('gpt') || key.includes('openai')) return logoOpenAI
  return null
}

const readImageFile = async (file: File): Promise<ChatAttachment | null> =>
  new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = typeof reader.result === 'string' ? reader.result : ''
      if (!result) {
        resolve(null)
        return
      }
      const [header, data] = result.split(',')
      const mimeType =
        file.type || header?.match(/data:(.*?);base64/)?.[1] || undefined
      const base = {
        type: 'image' as const,
        data: data ?? '',
        name: file.name,
        size: file.size,
        mimeType,
        previewUrl: result,
      }
      const img = new Image()
      img.onload = () => {
        resolve({ ...base, width: img.naturalWidth, height: img.naturalHeight })
      }
      img.onerror = () => resolve(base)
      img.src = result
    }
    reader.onerror = () => resolve(null)
    reader.readAsDataURL(file)
  })

export function ChatInput({
  onSend,
  onAssetUpload,
  disabled = false,
  placeholder = 'Describe what you want to build...',
  pages = [],
}: ChatInputProps) {
  const [message, setMessage] = React.useState('')
  const [attachments, setAttachments] = React.useState<ChatAttachment[]>([])
  const [imageIntent, setImageIntent] = React.useState<ImageIntent>('asset')
  const [isProcessing, setIsProcessing] = React.useState(false)
  const [assetPickerOpen, setAssetPickerOpen] = React.useState(false)
  const [selectedAssetType, setSelectedAssetType] = React.useState<AssetType | null>(
    null
  )
  const [isUploadingAsset, setIsUploadingAsset] = React.useState(false)
  const [assetUploadProgress, setAssetUploadProgress] = React.useState(0)
  const [isListening, setIsListening] = React.useState(false)
  const [speechSupported, setSpeechSupported] = React.useState(false)
  const [isSavingModel, setIsSavingModel] = React.useState(false)
  const [dragActive, setDragActive] = React.useState(false)
  const [liveVoiceStatus, setLiveVoiceStatus] = React.useState('')
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)
  const assetInputRef = React.useRef<HTMLInputElement>(null)
  const popoverRef = React.useRef<HTMLDivElement>(null)
  const recognitionRef = React.useRef<SpeechRecognitionLike | null>(null)

  const {
    mentionOpen,
    mentionQuery,
    mentionType,
    mentionIndex,
    mentionRange,
    mentionPosition,
    filteredPages,
    setMentionIndex,
    updateMentionState,
    closeMention,
  } = useMentionState(pages, textareaRef)

  const { settings, modelOptions, isLoading: isSettingsLoading, updateSettings } =
    useSettings()

  const availableModels = React.useMemo(() => {
    if (modelOptions.length > 0) return modelOptions
    if (settings.model) return [{ id: settings.model, label: settings.model }]
    return []
  }, [modelOptions, settings.model])

  const modelItems = React.useMemo(
    () =>
      availableModels.map((option) => ({
        ...option,
        logo: resolveModelLogo(option.id, option.label),
      })),
    [availableModels]
  )

  React.useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`
    }
  }, [message])


  React.useEffect(() => {
    const SpeechRecognitionCtor = getSpeechRecognitionCtor()
    if (!SpeechRecognitionCtor) return
    setSpeechSupported(true)
    const recognition = new SpeechRecognitionCtor()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = navigator.language || 'en-US'
    recognition.onstart = () => setIsListening(true)
    recognition.onend = () => setIsListening(false)
    recognition.onerror = () => setIsListening(false)
    recognition.onresult = (event: SpeechRecognitionEventLike) => {
      let finalTranscript = ''
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i]
        if (result.isFinal && result[0]?.transcript) {
          finalTranscript += result[0].transcript
        }
      }
      if (!finalTranscript) return
      const normalized = finalTranscript.trim()
      if (!normalized) return
      setMessage((prev) => {
        const next = prev ? `${prev.trimEnd()} ${normalized}` : normalized
        return next
      })
      requestAnimationFrame(() => {
        const textarea = textareaRef.current
        if (!textarea) return
        const cursor = textarea.value.length
        textarea.setSelectionRange(cursor, cursor)
        updateMentionState(textarea.value, cursor)
      })
    }
    recognitionRef.current = recognition
    return () => {
      recognition.onstart = null
      recognition.onend = null
      recognition.onerror = null
      recognition.onresult = null
      recognition.stop()
      recognitionRef.current = null
    }
  }, [updateMentionState])


  const handleSend = React.useCallback(() => {
    if (!message.trim() || disabled || isProcessing) return
    const trimmed = message.trim()
    const targetPages = parsePageMentions(trimmed, pages)
    // Extract @file: mentions from the message
    const fileMentions = Array.from(trimmed.matchAll(/@file:([A-Za-z0-9_./\-]+)/g))
      .map((m) => m[1])
      .filter(Boolean)
    onSend(trimmed, {
      attachments,
      imageIntent: attachments.length > 0 ? imageIntent : undefined,
      targetPages: targetPages.length > 0 ? targetPages : undefined,
      mentionedFiles: fileMentions.length > 0 ? fileMentions : undefined,
    })
    setMessage('')
    setAttachments([])
    setImageIntent('asset')
    closeMention()
    if (isListening) {
      recognitionRef.current?.stop()
    }
  }, [
    attachments,
    imageIntent,
    closeMention,
    disabled,
    message,
    onSend,
    pages,
    isProcessing,
    isListening,
  ])

  const handleModelChange = async (value: string) => {
    if (value === settings.model) return
    setIsSavingModel(true)
    try {
      await updateSettings({ ...settings, model: value })
    } finally {
      setIsSavingModel(false)
    }
  }

  const handleToggleListening = () => {
    if (disabled || isProcessing) return
    if (!speechSupported) {
      toast({
        title: 'Voice input unavailable',
        description: 'Your browser does not support speech recognition.',
      })
      return
    }
    const recognition = recognitionRef.current
    if (!recognition) {
      toast({
        title: 'Voice input unavailable',
        description: 'Speech recognition failed to initialize.',
      })
      return
    }
    if (isListening) {
      recognition.stop()
      return
    }
    try {
      recognition.start()
    } catch {
      recognition.stop()
      setIsListening(false)
    }
  }

  React.useEffect(() => {
    if (!isListening) return
    if (disabled || isProcessing) {
      recognitionRef.current?.stop()
    }
  }, [disabled, isListening, isProcessing])

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (mentionOpen) {
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        if (filteredPages.length === 0) return
        setMentionIndex((index) => (index + 1) % filteredPages.length)
        return
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault()
        if (filteredPages.length === 0) return
        setMentionIndex(
          (index) => (index - 1 + filteredPages.length) % filteredPages.length
        )
        return
      }
      if (event.key === 'Enter') {
        const selection = filteredPages[mentionIndex]
        if (selection) {
          event.preventDefault()
          const textarea = textareaRef.current
          const range = mentionRange
          if (!textarea || !range) return
          const before = message.slice(0, range.start)
          const after = message.slice(range.end)
          const mention = `@${selection.slug}`
          const shouldAddSpace =
            after.length === 0 ? true : !/^[\\s,.;:!?)]/.test(after)
          const insertion = shouldAddSpace ? `${mention} ` : mention
          const nextValue = `${before}${insertion}${after}`
          setMessage(nextValue)
          closeMention()
          requestAnimationFrame(() => {
            const cursor = before.length + insertion.length
            textarea.setSelectionRange(cursor, cursor)
            textarea.focus()
          })
          return
        }
      }
      if (event.key === 'Escape') {
        event.preventDefault()
        closeMention()
        return
      }
    }
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSend()
    }
  }

  const handleChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = event.target.value
    setMessage(value)
    updateMentionState(value, event.target.selectionStart ?? value.length)
  }

  const handleSelectionChange = () => {
    const textarea = textareaRef.current
    if (!textarea) return
    updateMentionState(textarea.value, textarea.selectionStart ?? textarea.value.length)
  }

  const isSupportedAssetFile = (file: File) => {
    const type = file.type.toLowerCase()
    if (type) {
      return [
        'image/png',
        'image/jpeg',
        'image/jpg',
        'image/webp',
        'image/svg+xml',
      ].includes(type)
    }
    const name = file.name.toLowerCase()
    return (
      name.endsWith('.png') ||
      name.endsWith('.jpg') ||
      name.endsWith('.jpeg') ||
      name.endsWith('.webp') ||
      name.endsWith('.svg')
    )
  }

  const handleAssetTypeSelect = (type: AssetType) => {
    setSelectedAssetType(type)
    setAssetPickerOpen(false)
    requestAnimationFrame(() => {
      assetInputRef.current?.click()
    })
  }

  const handleAssetUpload = async (file: File) => {
    if (disabled) return
    if (!onAssetUpload) {
      toast({
        title: 'Upload unavailable',
        description: 'Asset upload is not configured yet.',
      })
      return
    }
    if (!selectedAssetType) {
      toast({
        title: 'Select an asset type',
        description: 'Choose how this image should be used before uploading.',
      })
      return
    }
    if (!isSupportedAssetFile(file)) {
      toast({
        title: 'Unsupported file type',
        description: 'Supported formats: PNG, JPEG, WebP, SVG.',
      })
      return
    }
    if (file.size > MAX_ASSET_FILE_SIZE) {
      toast({
        title: 'File too large',
        description: 'Asset uploads are limited to 10MB.',
      })
      return
    }

    setIsUploadingAsset(true)
    setAssetUploadProgress(0)
    try {
      await onAssetUpload(file, selectedAssetType, {
        onProgress: (progress) => setAssetUploadProgress(progress),
      })
      toast({
        title: 'Asset uploaded',
        description: `${ASSET_TYPE_LABELS[selectedAssetType]} added to this session.`,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Upload failed'
      toast({ title: 'Upload failed', description: message })
    } finally {
      setIsUploadingAsset(false)
      setAssetUploadProgress(0)
    }
  }

  const handleAssetInputChange = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    await handleAssetUpload(file)
  }

  React.useEffect(() => {
    if (!mentionOpen) return
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null
      const textarea = textareaRef.current
      if (textarea && target && textarea.contains(target)) return
      const popover = popoverRef.current
      if (popover && target && popover.contains(target)) return
      closeMention()
    }
    document.addEventListener('pointerdown', handlePointerDown)
    return () => document.removeEventListener('pointerdown', handlePointerDown)
  }, [mentionOpen, closeMention])

  const handleFiles = React.useCallback(
    async (files: FileList | File[]) => {
      if (disabled) return
      const list = Array.from(files)
      if (list.length === 0) return

      const remaining = MAX_ATTACHMENTS - attachments.length
      if (remaining <= 0) {
        toast({
          title: 'Image limit reached',
          description: `You can upload up to ${MAX_ATTACHMENTS} images.`,
        })
        return
      }

      const candidates: File[] = []
      for (const file of list) {
        if (!file.type.startsWith('image/')) {
          toast({
            title: 'Invalid file type',
            description: `${file.name} is not an image.`,
          })
          continue
        }
        candidates.push(file)
      }

      if (candidates.length === 0) return

      if (candidates.length > remaining) {
        toast({
          title: 'Image limit reached',
          description: `Only ${remaining} more image${remaining === 1 ? '' : 's'} allowed.`,
        })
      }

      const selected = candidates.slice(0, remaining)
      setIsProcessing(true)
      const processed = await Promise.all(
        selected.map(async (file) => {
          if (file.size <= MAX_FILE_SIZE) return file
          const compressed = await compressImageFile(file)
          if (!compressed || compressed.size > MAX_FILE_SIZE) {
            toast({
              title: 'File too large',
              description: `${file.name} exceeds 10MB.`,
            })
            return null
          }
          return compressed
        })
      )
      const usable = processed.filter((file): file is File => Boolean(file))
      const results = await Promise.all(usable.map(readImageFile))
      const next = results.filter((item): item is ChatAttachment => Boolean(item))
      setAttachments((prev) => [...prev, ...next])
      setIsProcessing(false)
    },
    [attachments.length, disabled]
  )

  const handleDrop = (event: React.DragEvent<HTMLTextAreaElement>) => {
    event.preventDefault()
    event.stopPropagation()
    setDragActive(false)
    if (disabled) return
    if (event.dataTransfer?.files?.length) {
      void handleFiles(event.dataTransfer.files)
    }
  }

  const handleDragOver = (event: React.DragEvent<HTMLTextAreaElement>) => {
    event.preventDefault()
    setDragActive(true)
  }

  const handleDragLeave = (event: React.DragEvent<HTMLTextAreaElement>) => {
    if (event.currentTarget.contains(event.relatedTarget as Node)) return
    setDragActive(false)
  }

  const handlePaste = (event: React.ClipboardEvent<HTMLTextAreaElement>) => {
    if (disabled) return
    const clipboard = event.clipboardData
    if (!clipboard) return

    const files: File[] = []
    if (clipboard.files && clipboard.files.length > 0) {
      files.push(...Array.from(clipboard.files))
    } else if (clipboard.items && clipboard.items.length > 0) {
      for (const item of Array.from(clipboard.items)) {
        if (item.kind === 'file' && item.type.startsWith('image/')) {
          const file = item.getAsFile()
          if (file) files.push(file)
        }
      }
    }

    if (files.length > 0) {
      void handleFiles(files)
    }
  }

  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index))
  }

  return (
    <div
      className="flex w-full flex-col gap-2 rounded-2xl border border-border bg-background p-3 shadow-sm"
      data-testid="chat-input"
    >
      {attachments.length > 0 ? (
        <div className="flex flex-col gap-1.5">
          <div className="flex gap-2 overflow-x-auto pb-1">
            {attachments.map((attachment, index) => (
              <ImageThumbnail
                key={`${attachment.name}-${index}`}
                attachment={attachment}
                onRemove={() => removeAttachment(index)}
              />
            ))}
          </div>
          <Select
            value={imageIntent}
            onValueChange={(v) => setImageIntent(v as ImageIntent)}
          >
            <SelectTrigger
              className="h-7 w-[170px] rounded-md text-xs"
              data-testid="image-intent-select"
            >
              <SelectValue placeholder="Image intent" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="asset">Asset (use in page)</SelectItem>
              <SelectItem value="style_reference">Style Reference</SelectItem>
              <SelectItem value="layout_reference">Layout Reference</SelectItem>
              <SelectItem value="screenshot">Screenshot</SelectItem>
            </SelectContent>
          </Select>
        </div>
      ) : null}
      {isUploadingAsset ? (
        <div
          className="flex items-center gap-3 rounded-lg border border-border/60 bg-muted/40 px-3 py-2 text-xs text-muted-foreground"
          data-testid="asset-upload-progress"
        >
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          <span>
            Uploading{' '}
            {selectedAssetType
              ? ASSET_TYPE_LABELS[selectedAssetType]
              : 'asset'}
            {assetUploadProgress > 0 ? ` (${assetUploadProgress}%)` : ''}
          </span>
          <div className="h-1 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${assetUploadProgress}%` }}
            />
          </div>
        </div>
      ) : null}
      <div className="relative">
        <Textarea
          ref={textareaRef}
          value={message}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onClick={handleSelectionChange}
          onKeyUp={handleSelectionChange}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onPaste={handlePaste}
          placeholder={placeholder}
          disabled={disabled}
          aria-label="Message input"
          data-testid="chat-textarea"
          rows={1}
          className={`min-h-[92px] w-full resize-none border-0 bg-transparent p-0 pb-2 text-sm shadow-none focus-visible:ring-0 ${
            dragActive ? 'ring-2 ring-primary/40' : ''
          }`}
        />
      </div>
      <div className="flex w-full items-center justify-between gap-2 text-xs text-muted-foreground">
        <Select
          value={settings.model ?? modelItems[0]?.id ?? ''}
          onValueChange={handleModelChange}
          disabled={disabled || isSettingsLoading || isSavingModel}
        >
          <SelectTrigger className="h-8 w-[180px] rounded-full text-xs">
            <SelectValue placeholder="Select model" />
          </SelectTrigger>
          <SelectContent>
            {modelItems.length > 0 ? (
              modelItems.map((option) => (
                <SelectItem
                  key={option.id}
                  value={option.id}
                  textValue={option.label ?? option.id}
                >
                  <div className="flex items-center gap-2">
                    {option.logo ? (
                      <img
                        src={option.logo}
                        alt={`${option.label ?? option.id} logo`}
                        className="h-4 w-4 shrink-0 rounded-sm object-contain"
                      />
                    ) : null}
                    <span className="text-xs">{option.label ?? option.id}</span>
                  </div>
                </SelectItem>
              ))
            ) : (
              <SelectItem value="default" disabled>
                No models configured
              </SelectItem>
            )}
          </SelectContent>
        </Select>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => {
              if (disabled || isUploadingAsset) return
              if (!onAssetUpload) {
                toast({
                  title: 'Upload unavailable',
                  description: 'Asset upload is not configured yet.',
                })
                return
              }
              setAssetPickerOpen(true)
            }}
            disabled={disabled || isUploadingAsset || !onAssetUpload}
            aria-label="Upload asset"
            className="h-9 w-9"
            title="Upload asset"
            data-testid="asset-upload-button"
          >
            <Upload className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={async () => {
              await handleToggleListening()
              setLiveVoiceStatus(
                isListening
                  ? 'Voice input stopped'
                  : 'Voice input started'
              )
            }}
            disabled={disabled || isProcessing || !speechSupported}
            aria-label={isListening ? 'Stop voice input' : 'Start voice input'}
            className="h-9 w-9"
            title={
              speechSupported
                ? isListening
                  ? 'Stop voice input'
                  : 'Start voice input'
                : 'Voice input not supported'
            }
          >
            {isListening ? (
              <MicOff className="h-4 w-4" />
            ) : (
              <Mic className="h-4 w-4" />
            )}
          </Button>
          <span className="sr-only" role="status" aria-live="polite">
            {liveVoiceStatus}
          </span>
          <Button
            type="button"
            onClick={handleSend}
            disabled={disabled || !message.trim() || isProcessing}
            size="icon"
            className="h-9 w-9"
            aria-label="Send message"
          >
            {isProcessing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>
      {mentionOpen && mentionPosition ? (
        <PageMentionPopover
          ref={popoverRef}
          pages={pages}
          query={mentionQuery}
          position={mentionPosition}
          placement={mentionPosition.placement}
          arrowOffset={mentionPosition.arrowOffset}
          selectedIndex={mentionIndex}
          onHoverIndex={setMentionIndex}
          onSelect={(page) => {
            const textarea = textareaRef.current
            const range = mentionRange
            if (!textarea || !range) return
            const before = message.slice(0, range.start)
            const after = message.slice(range.end)
            const mention = `@${page.slug}`
            const shouldAddSpace =
              after.length === 0 ? true : !/^[\\s,.;:!?)]/.test(after)
            const insertion = shouldAddSpace ? `${mention} ` : mention
            const nextValue = `${before}${insertion}${after}`
            setMessage(nextValue)
            closeMention()
            requestAnimationFrame(() => {
              const cursor = before.length + insertion.length
              textarea.setSelectionRange(cursor, cursor)
              textarea.focus()
            })
          }}
        />
      ) : null}
      <Dialog open={assetPickerOpen} onOpenChange={setAssetPickerOpen}>
        <DialogContent data-testid="asset-type-dialog">
          <DialogHeader>
            <DialogTitle>Upload an asset</DialogTitle>
            <DialogDescription>
              Choose how this image should be used in the session.
            </DialogDescription>
          </DialogHeader>
          <AssetTypeSelector
            selected={selectedAssetType}
            onSelect={handleAssetTypeSelect}
            onCancel={() => setAssetPickerOpen(false)}
          />
        </DialogContent>
      </Dialog>
      <input
        ref={assetInputRef}
        type="file"
        accept={ASSET_ACCEPT_TYPES}
        className="hidden"
        onChange={handleAssetInputChange}
        data-testid="asset-file-input"
      />
    </div>
  )
}
