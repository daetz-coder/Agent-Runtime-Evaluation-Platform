/**
 * 认证工具 — 独立版，不依赖评估平台
 */

const apiKey = import.meta.env.VITE_API_KEY as string | undefined

export function streamAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (apiKey) {
    headers.Authorization = `Bearer ${apiKey}`
  }
  return headers
}
