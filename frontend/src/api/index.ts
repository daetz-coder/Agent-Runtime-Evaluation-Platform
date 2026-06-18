import axios, { type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

export interface ApiRequestConfig extends AxiosRequestConfig {
  /** Suppress global error toast (e.g. optional resource lookups) */
  silent?: boolean
}

// Create axios instance
const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
api.interceptors.request.use(
  (config) => config,
  (error) => Promise.reject(error)
)

// Response interceptor
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const silent = (error.config as ApiRequestConfig | undefined)?.silent
    if (!silent) {
      const message = error.response?.data?.detail || error.message || '请求失败'
      ElMessage.error(message)
    }
    return Promise.reject(error)
  }
)

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

  run(data: { task_id: string; include_details?: boolean }) {
    return api.post('/evaluations/', data)
  },

  getById(id: string, config?: ApiRequestConfig) {
    return api.get(`/evaluations/${id}`, config)
  },

  delete(id: string) {
    return api.delete(`/evaluations/${id}`)
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
}

export { withSilent }
export default api
