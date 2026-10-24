// Thin API client. Every backend response is an envelope:
//   { success: true, data, meta }  |  { success: false, error: { code, message, details } }
import { compressImage } from './utils'

const BASE = import.meta.env.VITE_API_BASE || ''
const TIMEOUT_MS = 150_000

export class ApiError extends Error {
  constructor(message, code = 'error', details = null, status = 0) {
    super(message)
    this.code = code
    this.details = details
    this.status = status
  }
}

async function request(path, options = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  let res
  try {
    res = await fetch(BASE + path, { ...options, signal: controller.signal })
  } catch (e) {
    if (e.name === 'AbortError') throw new ApiError('The request timed out. Please try again.', 'timeout')
    throw new ApiError('Cannot reach the backend. Is the FastAPI server running on port 8000?', 'network')
  } finally {
    clearTimeout(timer)
  }

  let body
  try {
    body = await res.json()
  } catch {
    throw new ApiError(`Unexpected response from server (HTTP ${res.status}).`, 'bad_response', null, res.status)
  }
  if (!res.ok || !body || body.success !== true) {
    const err = body?.error || {}
    throw new ApiError(err.message || `Request failed (HTTP ${res.status}).`, err.code, err.details, res.status)
  }
  if (body.data === undefined || body.data === null) {
    throw new ApiError('Server returned an empty result.', 'bad_response')
  }
  return body
}

async function form(fields = {}, image = null) {
  const fd = new FormData()
  for (const [k, v] of Object.entries(fields)) {
    if (v !== undefined && v !== null && v !== '') fd.append(k, typeof v === 'object' ? JSON.stringify(v) : String(v))
  }
  if (image) fd.append('image', await compressImage(image))
  return fd
}

const postJson = (path, data) =>
  request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })

export const api = {
  health: () => request('/api/health'),
  history: (module) => request('/api/history' + (module ? `?module=${encodeURIComponent(module)}` : '')),
  historyItem: (id) => request(`/api/history/${id}`),
  imageUrl: (name) => `${BASE}/api/uploads/${name}`,

  safety: async (image, context, siteType) =>
    request('/api/safety/analyze', { method: 'POST', body: await form({ context, site_type: siteType }, image) }),
  crack: async (image, fields) => request('/api/cracks/analyze', { method: 'POST', body: await form(fields, image) }),
  valuation: async (payload, image) =>
    request('/api/valuation/estimate', { method: 'POST', body: await form({ payload }, image) }),
  planning: (payload) => postJson('/api/planning/estimate', payload),
  daily: (payload) => postJson('/api/assistant/daily', payload),
  chat: async (messages, image) =>
    request('/api/assistant/chat', { method: 'POST', body: await form({ payload: { messages } }, image) }),
  legal: async (payload, image) =>
    request('/api/legal/ask', { method: 'POST', body: await form({ payload }, image) }),
  legalKb: () => request('/api/legal/kb'),
  legalArticle: (id) => request(`/api/legal/kb/${encodeURIComponent(id)}`),
}
