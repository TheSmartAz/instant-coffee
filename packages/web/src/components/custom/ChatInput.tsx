import * as React from 'react'
import { Loader2, Mic, MicOff, Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import type { ChatAttachment, ChatStyleReference, Page } from '@/types'
import { toast } from '@/hooks/use-toast'
import { useSettings } from '@/hooks/useSettings'
import logoDeepSeek from '@/assets/model-logos/deepseek.png'
import logoGemini from '@/assets/model-logos/gemini.png'
import logoGrok from '@/assets/model-logos/grok.png'
import logoHunyuan from '@/assets/model-logos/hunyuan.png'
import logoKimi from '@/assets/model-logos/kimi.png'
import logoMiniMax from '@/assets/model-logos/minimax.png'
import logoOpenAI from '@/assets/model-logos/openai.png'
import logoQwen from '@/assets/model-logos/qwen.png'
import logoZai from '@/assets/model-logos/zai.png'
import { ImageThumbnail } from './ImageThumbnail'
import { PageMentionPopover } from './PageMentionPopover'
import { filterPages, parsePageMentions } from '@/utils/chat'

export interface ChatInputProps {
  onSend: (
    message: string,
    options?: {
      triggerInterview?: boolean
      attachments?: ChatAttachment[]
      targetPages?: string[]
      styleReference?: ChatStyleReference
    }
  ) => void
  disabled?: boolean
  placeholder?: string
  initialInterviewOn?: boolean
  showInterviewToggle?: boolean
  pages?: Page[]
}

const MAX_ATTACHMENTS = 3
const MAX_FILE_SIZE = 5 * 1024 * 1024
const MAX_IMAGE_DIMENSION = 2048
const MENTION_POPOVER_WIDTH = 288
const MENTION_POPOVER_HEIGHT = 224

type SpeechRecognitionLike = {
  continuous: boolean
  interimResults: boolean
  lang: string
  onresult: ((event: any) => void) | null
  onstart: (() => void) | null
  onend: (() => void) | null
  onerror: ((event: any) => void) | null
  start: () => void
  stop: () => void
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

const isValidMentionBoundary = (value?: string) =>
  !value || !/[A-Za-z0-9_]/.test(value)

const findMentionAtCursor = (value: string, cursor: number) => {
  const uptoCursor = value.slice(0, cursor)
  const atIndex = uptoCursor.lastIndexOf('@')
  if (atIndex === -1) return null
  const prevChar = atIndex > 0 ? value[atIndex - 1] : undefined
  if (!isValidMentionBoundary(prevChar)) return null

  const fragment = uptoCursor.slice(atIndex + 1)
  if (!/^[A-Za-z0-9_-]*$/.test(fragment)) return null

  return { start: atIndex, end: cursor, query: fragment }
}

const getCaretCoords = (textarea: HTMLTextAreaElement, position: number) => {
  const style = window.getComputedStyle(textarea)
  const div = document.createElement('div')
  const properties = [
    'boxSizing',
    'width',
    'height',
    'overflowX',
    'overflowY',
    'borderTopWidth',
    'borderRightWidth',
    'borderBottomWidth',
    'borderLeftWidth',
    'paddingTop',
    'paddingRight',
    'paddingBottom',
    'paddingLeft',
    'fontStyle',
    'fontVariant',
    'fontWeight',
    'fontStretch',
    'fontSize',
    'fontSizeAdjust',
    'lineHeight',
    'fontFamily',
    'textAlign',
    'textTransform',
    'textIndent',
    'textDecoration',
    'letterSpacing',
    'wordSpacing',
    'tabSize',
  ] as const

  properties.forEach((prop) => {
    div.style[prop] = style[prop]
  })

  div.style.position = 'absolute'
  div.style.visibility = 'hidden'
  div.style.whiteSpace = 'pre-wrap'
  div.style.wordWrap = 'break-word'
  div.style.left = '-9999px'
  div.textContent = textarea.value.substring(0, position)

  const span = document.createElement('span')
  span.textContent = textarea.value.substring(position) || '.'
  div.appendChild(span)
  document.body.appendChild(div)

  const top = span.offsetTop
  const left = span.offsetLeft
  const lineHeight = parseFloat(style.lineHeight) || parseFloat(style.fontSize) || 16

  document.body.removeChild(div)

  return { top, left, lineHeight }
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

const loadImageFromFile = (file: File): Promise<HTMLImageElement> =>
  new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.decoding = 'async'
    img.onload = () => {
      URL.revokeObjectURL(url)
      resolve(img)
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('Failed to load image'))
    }
    img.src = url
  })

const canvasToBlob = (
  canvas: HTMLCanvasElement,
  type: string,
  quality?: number
): Promise<Blob | null> =>
  new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), type, quality)
  })

const extensionForType = (type: string) => {
  switch (type) {
    case 'image/png':
      return 'png'
    case 'image/webp':
      return 'webp'
    case 'image/jpeg':
    case 'image/jpg':
      return 'jpg'
    default:
      return 'jpg'
  }
}

const buildOutputName = (name: string, type: string) => {
  const ext = extensionForType(type)
  const base = name && name.includes('.') ? name.replace(/\.[^/.]+$/, '') : name || 'image'
  return `${base}.${ext}`
}

const buildTypeCandidates = (originalType: string) => {
  const normalized =
    originalType.toLowerCase() === 'image/jpg' ? 'image/jpeg' : originalType.toLowerCase()
  const candidates: string[] = []
  if (normalized.startsWith('image/')) {
    candidates.push(normalized)
  }
  if (normalized === 'image/png') {
    candidates.push('image/webp', 'image/jpeg')
  } else if (normalized === 'image/webp') {
    candidates.push('image/jpeg')
  } else if (normalized !== 'image/jpeg') {
    candidates.push('image/webp', 'image/jpeg')
  }
  return Array.from(new Set(candidates))
}

const compressImageFile = async (file: File): Promise<File | null> => {
  try {
    const img = await loadImageFromFile(file)
    const width = img.naturalWidth || img.width
    const height = img.naturalHeight || img.height
    if (!width || !height) return null

    const baseScale =
      Math.max(width, height) > MAX_IMAGE_DIMENSION
        ? MAX_IMAGE_DIMENSION / Math.max(width, height)
        : 1
    const scaleSteps = [1, 0.85, 0.72, 0.6]
    const qualitySteps = [0.92, 0.85, 0.78, 0.7, 0.6]
    const typeCandidates = buildTypeCandidates(file.type)

    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    if (!ctx) return null
    ctx.imageSmoothingEnabled = true
    ctx.imageSmoothingQuality = 'high'

    for (const scaleStep of scaleSteps) {
      const scale = baseScale * scaleStep
      const targetWidth = Math.max(1, Math.round(width * scale))
      const targetHeight = Math.max(1, Math.round(height * scale))
      canvas.width = targetWidth
      canvas.height = targetHeight
      ctx.clearRect(0, 0, targetWidth, targetHeight)
      ctx.drawImage(img, 0, 0, targetWidth, targetHeight)

      for (const type of typeCandidates) {
        if (type === 'image/png') {
          const blob = await canvasToBlob(canvas, type)
          if (blob && blob.size <= MAX_FILE_SIZE) {
            return new File([blob], buildOutputName(file.name, type), { type })
          }
          continue
        }
        for (const quality of qualitySteps) {
          const blob = await canvasToBlob(canvas, type, quality)
          if (blob && blob.size <= MAX_FILE_SIZE) {
            return new File([blob], buildOutputName(file.name, type), { type })
          }
        }
      }
    }
    return null
  } catch {
    return null
  }
}

export function ChatInput({
  onSend,
  disabled = false,
  placeholder = 'Describe what you want to build...',
  initialInterviewOn = false,
  showInterviewToggle = true,
  pages = [],
}: ChatInputProps) {
  const [message, setMessage] = React.useState('')
  const [triggerInterview, setTriggerInterview] = React.useState(initialInterviewOn)
  const [attachments, setAttachments] = React.useState<ChatAttachment[]>([])
  const [isProcessing, setIsProcessing] = React.useState(false)
  const [isListening, setIsListening] = React.useState(false)
  const [speechSupported, setSpeechSupported] = React.useState(false)
  const [isSavingModel, setIsSavingModel] = React.useState(false)
  const [dragActive, setDragActive] = React.useState(false)
  const [mentionOpen, setMentionOpen] = React.useState(false)
  const [mentionQuery, setMentionQuery] = React.useState('')
  const [mentionIndex, setMentionIndex] = React.useState(0)
  const [mentionRange, setMentionRange] = React.useState<{ start: number; end: number } | null>(
    null
  )
  const [mentionPosition, setMentionPosition] = React.useState<{
    x: number
    y: number
    placement: 'top' | 'bottom'
    arrowOffset: number
  } | null>(null)
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)
  const popoverRef = React.useRef<HTMLDivElement>(null)
  const prevInitialRef = React.useRef(initialInterviewOn)
  const recognitionRef = React.useRef<SpeechRecognitionLike | null>(null)
  const { settings, modelOptions, isLoading: isSettingsLoading, updateSettings } =
    useSettings()

  React.useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`
    }
  }, [message])

  React.useEffect(() => {
    if (!prevInitialRef.current && initialInterviewOn) {
      setTriggerInterview(true)
    }
    prevInitialRef.current = initialInterviewOn
  }, [initialInterviewOn])


  const filteredPages = React.useMemo(
    () => filterPages(pages, mentionQuery),
    [pages, mentionQuery]
  )

  React.useEffect(() => {
    if (!mentionOpen) return
    setMentionIndex((current) =>
      Math.min(current, Math.max(filteredPages.length - 1, 0))
    )
  }, [filteredPages.length, mentionOpen])

  const updateMentionState = React.useCallback(
    (value: string, cursor: number) => {
      const mention = findMentionAtCursor(value, cursor)
      if (!mention) {
        setMentionOpen(false)
        setMentionQuery('')
        setMentionRange(null)
        return
      }

      const textarea = textareaRef.current
      if (textarea) {
        const coords = getCaretCoords(textarea, mention.end)
        const rect = textarea.getBoundingClientRect()
        const baseX = rect.left + coords.left - textarea.scrollLeft
        const baseY = rect.top + coords.top - textarea.scrollTop + coords.lineHeight + 8

        let nextX = baseX
        let nextY = baseY
        let placement: 'top' | 'bottom' = 'bottom'
        const margin = 8
        const maxX = window.innerWidth - MENTION_POPOVER_WIDTH - margin
        const maxY = window.innerHeight - MENTION_POPOVER_HEIGHT - margin

        if (nextX > maxX) nextX = Math.max(margin, maxX)
        if (nextY > maxY) {
          const above = rect.top + coords.top - MENTION_POPOVER_HEIGHT - margin
          if (above > margin) {
            nextY = above
            placement = 'top'
          } else {
            nextY = Math.max(margin, maxY)
          }
        }

        const unclampedArrow = baseX - nextX
        const arrowOffset = Math.min(
          Math.max(unclampedArrow, 12),
          MENTION_POPOVER_WIDTH - 12
        )

        setMentionPosition({ x: nextX, y: nextY, placement, arrowOffset })
      }

      const isSameMention =
        mentionRange?.start === mention.start && mentionQuery === mention.query
      setMentionRange({ start: mention.start, end: mention.end })
      setMentionQuery(mention.query)
      setMentionIndex((current) => (isSameMention ? current : 0))
      setMentionOpen(true)
    },
    [mentionQuery, mentionRange]
  )

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
    recognition.onresult = (event: any) => {
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


  const handleSend = React.useCallback(() => {
    if (!message.trim() || disabled || isProcessing) return
    const shouldTriggerInterview = triggerInterview
    const trimmed = message.trim()
    const targetPages = parsePageMentions(trimmed, pages)
    onSend(trimmed, {
      ...(shouldTriggerInterview ? { triggerInterview: true } : {}),
      attachments,
      targetPages: targetPages.length > 0 ? targetPages : undefined,
    })
    setMessage('')
    setTriggerInterview(false)
    setAttachments([])
    setMentionOpen(false)
    setMentionQuery('')
    setMentionRange(null)
    if (isListening) {
      recognitionRef.current?.stop()
    }
  }, [
    attachments,
    disabled,
    message,
    onSend,
    pages,
    triggerInterview,
    isProcessing,
    isListening,
  ])

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
      setIsListening(false)
    }
  }

  const handleModelChange = async (value: string) => {
    if (value === settings.model) return
    setIsSavingModel(true)
    try {
      await updateSettings({ ...settings, model: value })
    } finally {
      setIsSavingModel(false)
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
          setMentionOpen(false)
          setMentionQuery('')
          setMentionRange(null)
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
        setMentionOpen(false)
        setMentionQuery('')
        setMentionRange(null)
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

  React.useEffect(() => {
    if (!mentionOpen) return
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null
      const textarea = textareaRef.current
      if (textarea && target && textarea.contains(target)) return
      const popover = popoverRef.current
      if (popover && target && popover.contains(target)) return
      setMentionOpen(false)
      setMentionQuery('')
      setMentionRange(null)
    }
    document.addEventListener('pointerdown', handlePointerDown)
    return () => document.removeEventListener('pointerdown', handlePointerDown)
  }, [mentionOpen])

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
              description: `${file.name} exceeds 5MB.`,
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
    <div className="flex w-full flex-col gap-2 rounded-2xl border border-border bg-background p-3 shadow-sm">
      {attachments.length > 0 ? (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {attachments.map((attachment, index) => (
            <ImageThumbnail
              key={`${attachment.name}-${index}`}
              attachment={attachment}
              onRemove={() => removeAttachment(index)}
            />
          ))}
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
          rows={1}
          className={`min-h-[44px] w-full resize-none border-0 bg-transparent p-0 pr-20 pb-10 text-sm shadow-none focus-visible:ring-0 ${
            dragActive ? 'ring-2 ring-primary/40' : ''
          }`}
        />
        <div className="absolute bottom-1 right-1 flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={handleToggleListening}
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
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        {showInterviewToggle ? (
          <Button
            type="button"
            variant={triggerInterview ? 'default' : 'outline'}
            size="sm"
            onClick={() => setTriggerInterview((prev) => !prev)}
            disabled={disabled}
            aria-pressed={triggerInterview}
            className="h-8 w-[72px] rounded-full"
          >
            {triggerInterview ? 'Interview' : 'Chat'}
          </Button>
        ) : null}
        <div className="flex items-center gap-2">
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
            setMentionOpen(false)
            setMentionQuery('')
            setMentionRange(null)
            requestAnimationFrame(() => {
              const cursor = before.length + insertion.length
              textarea.setSelectionRange(cursor, cursor)
              textarea.focus()
            })
          }}
        />
      ) : null}
    </div>
  )
}
