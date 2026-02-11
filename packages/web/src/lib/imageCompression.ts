const MAX_IMAGE_DIMENSION = 2048
const MAX_FILE_SIZE = 10 * 1024 * 1024

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
  quality?: number,
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

export const compressImageFile = async (file: File): Promise<File | null> => {
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
