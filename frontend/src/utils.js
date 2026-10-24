// Defensive helpers so the UI never crashes on unexpected/missing values.
export const arr = (v) => (Array.isArray(v) ? v : [])
export const num = (v, d = 0) => (typeof v === 'number' && Number.isFinite(v) ? v : d)
export const str = (v, d = '') => (typeof v === 'string' ? v : v == null ? d : String(v))
const LABELS = { rcc_frame: 'RCC Frame', no_go: 'No-go', mep: 'MEP' }
export const label = (v) => LABELS[str(v)] || str(v).replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

export function money(value, currency = 'INR') {
  const v = num(value)
  if (currency === 'INR') {
    if (v >= 1e7) return `₹${(v / 1e7).toFixed(2)} Cr`
    if (v >= 1e5) return `₹${(v / 1e5).toFixed(2)} L`
    return `₹${Math.round(v).toLocaleString('en-IN')}`
  }
  if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`
  return `$${Math.round(v).toLocaleString('en-US')}`
}

export const pct = (v) => `${Math.round(num(v) * 100)}%`

export const MAX_IMAGE_MB = 8
const ALLOWED = ['image/jpeg', 'image/png', 'image/webp', 'image/bmp', 'image/gif']

export function checkImage(file) {
  if (!file) return 'Please choose an image.'
  if (file.type && !ALLOWED.includes(file.type)) return 'Unsupported file type. Use JPG, PNG or WEBP.'
  if (file.size === 0) return 'The selected file is empty.'
  if (file.size > MAX_IMAGE_MB * 1024 * 1024) return `Image is larger than ${MAX_IMAGE_MB} MB.`
  return null
}

/**
 * Downscale large photos in the browser before upload (keeps requests well under
 * serverless body limits such as Vercel's 4.5 MB and speeds up uploads).
 * Falls back to the original file if the browser cannot decode it.
 */
export async function compressImage(file, maxSide = 1600, quality = 0.85) {
  if (!file || !file.type?.startsWith('image/') || file.type === 'image/gif') return file
  try {
    const bitmap = await createImageBitmap(file)
    const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height))
    if (scale === 1 && file.size < 1.5 * 1024 * 1024) return file
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(bitmap.width * scale)
    canvas.height = Math.round(bitmap.height * scale)
    canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality))
    if (!blob || blob.size >= file.size) return file
    return new File([blob], file.name.replace(/\.\w+$/, '') + '.jpg', { type: 'image/jpeg' })
  } catch {
    return file // let the server report corrupted/unsupported images
  }
}

const TONE = {
  low: 'ok', none: 'ok', minor: 'ok', compliant: 'ok', proceed: 'ok', go: 'ok', positive: 'ok', monitor: 'info',
  medium: 'warn', moderate: 'warn', partial: 'warn', proceed_with_caution: 'warn', caution: 'warn', short_term: 'warn',
  neutral: 'info', not_visible: 'info',
  high: 'bad', severe: 'bad', non_compliant: 'bad', postpone: 'bad', no_go: 'bad', negative: 'bad', immediate: 'bad',
  critical: 'crit',
}
export const tone = (v) => TONE[str(v).toLowerCase()] || 'info'
