import axios, { type AxiosRequestConfig, type AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'

export interface ApiRequestConfig extends AxiosRequestConfig {
  /** Suppress global error toast (e.g. optional resource lookups) */
  silent?: boolean
}

/** Axios instance whose response interceptor unwraps `response.data`. */
interface ApiClient {
  get<T = any>(url: string, config?: ApiRequestConfig): Promise<T>
  post<T = any>(url: string, data?: unknown, config?: ApiRequestConfig): Promise<T>
  delete<T = any>(url: string, config?: ApiRequestConfig): Promise<T>
}

const axiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

axiosInstance.interceptors.request.use(
  (config) => config,
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

  list(params?: { skip?: number; limit?: number }) {
    return api.get('/tasks/', { params })
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
  list(params?: { skip?: number; limit?: number; status?: string }) {
    return api.get('/evaluations/', { params })
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

// Benchmark API
export const benchmarkApi = {
  getMonotonicity() {
    return api.get('/benchmark/monotonicity')
  },
}

export { withSilent }
export default api
