import api, { streamAuthHeaders } from './index'

export interface WorkspaceItem {
  id: string
  name: string
  description: string | null
  api_key: string
  created_at: string
  is_active: boolean
}

export interface MemberCreate {
  user_id: string
  role: 'admin' | 'evaluator' | 'viewer'
}

export interface AuditLogItem {
  id: number
  workspace_id: string
  user_id: string
  action: string
  resource_type: string
  resource_id: string
  details: Record<string, any> | null
  created_at: string
}

export interface WorkspaceCreate {
  name: string
  description?: string
}

export const workspaceApi = {
  list() {
    return api.get<WorkspaceItem[]>('/workspaces/')
  },

  getById(id: string) {
    return api.get<WorkspaceItem>(`/workspaces/${id}`)
  },

  create(data: WorkspaceCreate) {
    return api.post<WorkspaceItem>('/workspaces/', data)
  },

  getMembers(workspaceId: string) {
    return api.get<{ user_id: string; role: string; joined_at: string }[]>(`/workspaces/${workspaceId}/members`)
  },

  addMember(workspaceId: string, data: MemberCreate) {
    return api.post(`/workspaces/${workspaceId}/members`, data)
  },

  removeMember(workspaceId: string, userId: string) {
    return api.delete(`/workspaces/${workspaceId}/members/${userId}`)
  },

  rotateKey(workspaceId: string) {
    return api.post<{ workspace_id: string; api_key: string }>(`/workspaces/${workspaceId}/rotate-key`)
  },

  delete(workspaceId: string) {
    return api.delete<{ message: string }>(`/workspaces/${workspaceId}`)
  },

  getAuditLogs(workspaceId: string, limit = 50, action?: string) {
    const params: Record<string, any> = { limit }
    if (action) params.action = action
    return api.get<AuditLogItem[]>(`/workspaces/${workspaceId}/audit`, { params })
  },
}

/** Fetch helpers for non-axios native fetch calls (e.g. streaming). */
export { streamAuthHeaders }
