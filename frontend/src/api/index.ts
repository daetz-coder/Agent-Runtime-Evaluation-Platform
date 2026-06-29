import axios, { type AxiosRequestConfig, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

export interface ApiRequestConfig extends AxiosRequestConfig {
  /** Suppress global error toast (e.g. optional resource lookups) */
  silent?: boolean
}

/** Axios instance whose response interceptor unwraps `response.data`. */
interface ApiClient {
  get<T = any>(url: string, config?: ApiRequestConfig): Promise<T>
  post<T = any>(url: string, data?: unknown, config?: ApiRequestConfig): Promise<T>
  put<T = any>(url: string, data?: unknown, config?: ApiRequestConfig): Promise<T>
  delete<T = any>(url: string, config?: ApiRequestConfig): Promise<T>
}

const apiKey = import.meta.env.VITE_API_KEY as string | undefined

function attachAuthHeader(config: InternalAxiosRequestConfig): InternalAxiosRequestConfig {
  if (apiKey) {
    config.headers = {
      ...config.headers,
      Authorization: `Bearer ${apiKey}`,
    } as InternalAxiosRequestConfig['headers']
  }
  return config
}

export function streamAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (apiKey) {
    headers.Authorization = `Bearer ${apiKey}`
  }
  return headers
}

const axiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

/** Raw client for endpoints that return pagination headers. */
const paginatedAxios = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

export interface PaginatedResult<T> {
  items: T[]
  total: number
}

async function fetchPaginated<T>(url: string, config?: ApiRequestConfig): Promise<PaginatedResult<T>> {
  const response = await paginatedAxios.get<T[]>(url, config)
  const headerTotal = response.headers['x-total-count']
  const total = headerTotal ? Number(headerTotal) : response.data.length
  return { items: response.data, total }
}

paginatedAxios.interceptors.request.use(
  (config) => attachAuthHeader(config),
  (error) => Promise.reject(error)
)

paginatedAxios.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error) => {
    const silent = (error.config as ApiRequestConfig | undefined)?.silent
    if (!silent) {
      const message = error.response?.data?.detail || error.message || '请求失败'
      ElMessage.error(message)
    }
    return Promise.reject(error)
  }
)

axiosInstance.interceptors.request.use(
  (config) => attachAuthHeader(config),
  (error) => Promise.reject(error)
)

axiosInstance.interceptors.response.use(
  (response: AxiosResponse) => response.data,
  (error) => {
    const silent = (error.config as ApiRequestConfig | undefined)?.silent
    if (!silent) {
      const message = error.response?.data?.detail || error.message || '请求失败'
      ElMessage.error(message)
    }
    return Promise.reject(error)
  }
)

const api = axiosInstance as ApiClient

function withSilent(config?: ApiRequestConfig): ApiRequestConfig {
  return { ...config, silent: true }
}

// Task API
export const taskApi = {
  create(data: { goal: string; context?: Record<string, any> }) {
    return api.post('/tasks/', data)
  },

  getById(id: string, config?: ApiRequestConfig) {
    return api.get(`/tasks/${id}`, config)
  },

  list(params?: { skip?: number; limit?: number; status?: string; search?: string }) {
    return fetchPaginated('/tasks/', { params })
  },

  getDashboard() {
    return api.get('/tasks/dashboard')
  },

  getTrajectory(taskId: string, config?: ApiRequestConfig) {
    return api.get(`/tasks/${taskId}/trajectory`, config)
  },

  addTrajectory(taskId: string, steps: any[]) {
    return api.post(`/tasks/${taskId}/trajectory`, steps)
  },

  delete(id: string) {
    return api.delete(`/tasks/${id}`)
  },
}

// Evaluation API
export const evaluationApi = {
  list(params?: { skip?: number; limit?: number; status?: string; min_score?: number; max_score?: number }) {
    return fetchPaginated('/evaluations/', { params })
  },

  getDashboard() {
    return api.get('/evaluations/dashboard')
  },

  run(data: { task_id: string; include_details?: boolean; use_stream?: boolean }) {
    return api.post('/evaluations/', data)
  },

  getById(id: string, config?: ApiRequestConfig) {
    return api.get(`/evaluations/${id}`, config)
  },

  delete(id: string) {
    return api.delete(`/evaluations/${id}`)
  },

  getConsensus(taskId: string, includeAll?: boolean) {
    return api.post('/evaluations/consensus', { task_id: taskId, include_all: includeAll || false })
  },

  // ── Replay Debugger ──
  getReplay(evalId: string, config?: ApiRequestConfig) {
    return api.get(`/evaluations/${evalId}/replay`, config)
  },

  // ── Judge Transparency ──
  getJudgeRaw(evalId: string, dimension?: string, config?: ApiRequestConfig) {
    const path = dimension
      ? `/evaluations/${evalId}/judge-raw/${dimension}`
      : `/evaluations/${evalId}/judge-raw`
    return api.get(path, config)
  },

  // ── Trajectory Diff ──
  getDiff(baseEvalId: string, headEvalId: string, config?: ApiRequestConfig) {
    return api.get('/evaluations/diff', {
      params: { base_evaluation_id: baseEvalId, head_evaluation_id: headEvalId },
      ...config,
    })
  },

  // ── Incremental Evaluation ──
  runIncremental(data: { base_evaluation_id: string; head_task_id: string; force_dimensions?: string[] }) {
    return api.post('/evaluations/incremental', data)
  },

  // ── One-Click Legacy Evaluation ──
  runLegacy(data: { goal: string; steps: any[]; context?: Record<string, any> }) {
    return api.post('/evaluations/run-legacy', data)
  },
}

// Report API
export const reportApi = {
  getSummary() {
    return api.get('/reports/summary')
  },

  getTaskHistory(taskId: string, config?: ApiRequestConfig) {
    return api.get(`/reports/tasks/${taskId}/history`, config)
  },

  getDimensionStats(dimension: string) {
    return api.get(`/reports/dimensions/${dimension}`)
  },

  getTrends() {
    return api.get('/reports/trends')
  },

  getCompare(taskId: string, limit = 10, config?: ApiRequestConfig) {
    return api.get(`/reports/compare/${taskId}`, { params: { limit }, ...config })
  },

  getExportUrl(taskId: string) {
    return `/api/v1/reports/export/${taskId}`
  },
}

// System API
export const systemApi = {
  getHealth() {
    return api.get('/system/health')
  },

  // Prompt templates
  listPrompts() {
    return api.get('/settings/prompts')
  },

  getPrompt(version: string) {
    return api.get(`/settings/prompts/${version}`)
  },

  updatePrompt(version: string, content: string, description?: string) {
    return api.put(`/settings/prompts/${version}`, { content, description: description || '' })
  },
}

// Benchmark API
export const benchmarkApi = {
  getMonotonicity() {
    return api.get('/benchmark/monotonicity')
  },
}

// Debug / System Inspector API (served at /api/debug, not /api/v1)
const debugAxios = axios.create({ baseURL: '/api/debug', timeout: 15000 })
debugAxios.interceptors.request.use(
  (config) => attachAuthHeader(config),
  (error) => Promise.reject(error)
)
debugAxios.interceptors.response.use(
  (response: AxiosResponse) => response.data,
  (error) => {
    const silent = (error.config as ApiRequestConfig | undefined)?.silent
    if (!silent) {
      const message = error.response?.data?.detail || error.message || '请求失败'
      ElMessage.error(message)
    }
    return Promise.reject(error)
  }
)
const debugClient = debugAxios as ApiClient

export const debugApi = {
  getOverview() {
    return debugClient.get('/overview')
  },
  getSessions() {
    return debugClient.get('/sessions')
  },
  getSessionDetail(id: string) {
    return debugClient.get(`/sessions/${id}`)
  },
  getCheckpoints() {
    return debugClient.get('/checkpoints')
  },
  getCheckpointDetail(threadId: string) {
    return debugClient.get(`/checkpoints/${threadId}`)
  },
  getBm25Stats() {
    return debugClient.get('/bm25')
  },
}

export { withSilent }
export default api
