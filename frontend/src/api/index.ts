import axios from 'axios'
import { ElMessage } from 'element-plus'

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
  (config) => {
    // You can add auth token here
    // const token = localStorage.getItem('token')
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`
    // }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    const message = error.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

// Task API
export const taskApi = {
  // Create task
  create(data: { goal: string; context?: Record<string, any> }) {
    return api.post('/tasks/', data)
  },

  // Get task by ID
  getById(id: string) {
    return api.get(`/tasks/${id}`)
  },

  // List tasks
  list(params?: { skip?: number; limit?: number }) {
    return api.get('/tasks/', { params })
  },

  // Add trajectory
  addTrajectory(taskId: string, steps: any[]) {
    return api.post(`/tasks/${taskId}/trajectory`, steps)
  },
}

// Evaluation API
export const evaluationApi = {
  // Run evaluation
  run(data: { task_id: string; include_details?: boolean }) {
    return api.post('/evaluations/', data)
  },

  // Get evaluation by ID
  getById(id: string) {
    return api.get(`/evaluations/${id}`)
  },
}

// Report API
export const reportApi = {
  // Get summary
  getSummary() {
    return api.get('/reports/summary')
  },

  // Get task history
  getTaskHistory(taskId: string) {
    return api.get(`/reports/tasks/${taskId}/history`)
  },

  // Get dimension statistics
  getDimensionStats(dimension: string) {
    return api.get(`/reports/dimensions/${dimension}`)
  },
}

export default api
