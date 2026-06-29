<template>
  <div class="workspaces-page">
    <div class="page-header">
      <h2>多租户工作区</h2>
      <el-button type="primary" :icon="Plus" @click="showCreateDialog = true">
        创建工作区
      </el-button>
    </div>

    <!-- Workspace List -->
    <el-table :data="workspaces" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
      <el-table-column label="API Key" min-width="260">
        <template #default="{ row }">
          <el-input
            :model-value="row.api_key"
            readonly
            size="small"
            style="width: 220px"
          >
            <template #append>
              <el-button @click="copyKey(row.api_key)" :icon="CopyDocument" />
            </template>
          </el-input>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170">
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="viewWorkspace(row)">管理</el-button>
          <el-button size="small" @click="handleRotateKey(row)" :icon="RefreshRight">换 Key</el-button>
          <el-popconfirm title="确定删除该工作区？" @confirm="handleDelete(row)">
            <template #reference>
              <el-button size="small" type="danger" :icon="Delete">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- Create Dialog -->
    <el-dialog v-model="showCreateDialog" title="创建工作区" width="480px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="createForm.name" placeholder="例如：研发团队" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="createForm.description"
            type="textarea"
            :rows="3"
            placeholder="可选描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="creating">创建</el-button>
      </template>
    </el-dialog>

    <!-- Workspace Detail Drawer -->
    <el-drawer
      v-model="drawerVisible"
      :title="activeWorkspace?.name || '工作区详情'"
      size="600px"
    >
      <template v-if="activeWorkspace">
        <el-tabs v-model="detailTab">
          <!-- Overview -->
          <el-tab-pane label="概览" name="overview">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="ID">{{ activeWorkspace.id }}</el-descriptions-item>
              <el-descriptions-item label="名称">{{ activeWorkspace.name }}</el-descriptions-item>
              <el-descriptions-item label="描述">{{ activeWorkspace.description || '-' }}</el-descriptions-item>
              <el-descriptions-item label="API Key">
                <el-input
                  :model-value="activeWorkspace.api_key"
                  readonly
                  size="small"
                  style="width: 320px"
                >
                  <template #append>
                    <el-button @click="copyKey(activeWorkspace.api_key)" :icon="CopyDocument" />
                  </template>
                </el-input>
              </el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="activeWorkspace.is_active ? 'success' : 'danger'">
                  {{ activeWorkspace.is_active ? '启用' : '禁用' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="创建时间">{{ formatTime(activeWorkspace.created_at) }}</el-descriptions-item>
            </el-descriptions>
          </el-tab-pane>

          <!-- Members -->
          <el-tab-pane label="成员管理" name="members">
            <div style="margin-bottom: 12px; display: flex; gap: 8px;">
              <el-input v-model="newMemberUserId" placeholder="用户 ID" style="width: 200px" />
              <el-select v-model="newMemberRole" style="width: 130px">
                <el-option label="管理员" value="admin" />
                <el-option label="评估员" value="evaluator" />
                <el-option label="观察者" value="viewer" />
              </el-select>
              <el-button type="primary" @click="handleAddMember" :loading="addingMember">添加</el-button>
            </div>
            <el-table :data="members" stripe v-loading="membersLoading">
              <el-table-column prop="user_id" label="用户 ID" min-width="180" />
              <el-table-column prop="role" label="角色" width="120">
                <template #default="{ row }">
                  <el-tag :type="roleTag(row.role)" size="small">{{ roleLabel(row.role) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="100">
                <template #default="{ row }">
                  <el-popconfirm title="移除该成员？" @confirm="handleRemoveMember(row.user_id)">
                    <template #reference>
                      <el-button size="small" type="danger" :icon="Remove">移除</el-button>
                    </template>
                  </el-popconfirm>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- Audit Log -->
          <el-tab-pane label="审计日志" name="audit">
            <div style="margin-bottom: 12px;">
              <el-select v-model="auditFilter" placeholder="过滤操作类型" clearable style="width: 200px">
                <el-option label="全部" value="" />
                <el-option label="创建" value="created" />
                <el-option label="更新" value="updated" />
                <el-option label="删除" value="deleted" />
                <el-option label="添加成员" value="member_added" />
                <el-option label="移除成员" value="member_removed" />
                <el-option label="Key 轮换" value="api_key_rotated" />
              </el-select>
            </div>
            <el-table :data="auditLogs" stripe v-loading="auditLoading">
              <el-table-column prop="created_at" label="时间" width="170">
                <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
              </el-table-column>
              <el-table-column prop="user_id" label="操作用户" width="160" />
              <el-table-column prop="action" label="操作类型" width="130">
                <template #default="{ row }">
                  <el-tag size="small">{{ auditActionLabel(row.action) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="resource_type" label="资源类型" width="100" />
              <el-table-column prop="resource_id" label="资源 ID" min-width="160" show-overflow-tooltip />
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, RefreshRight, Delete, CopyDocument, Remove } from '@element-plus/icons-vue'
import { workspaceApi, type WorkspaceItem, type AuditLogItem } from '@/api/workspace'

const loading = ref(false)
const workspaces = ref<WorkspaceItem[]>([])

// Create dialog
const showCreateDialog = ref(false)
const creating = ref(false)
const createForm = ref({ name: '', description: '' })

// Detail drawer
const drawerVisible = ref(false)
const activeWorkspace = ref<WorkspaceItem | null>(null)
const detailTab = ref('overview')

// Members
const members = ref<{ user_id: string; role: string }[]>([])
const membersLoading = ref(false)
const newMemberUserId = ref('')
const newMemberRole = ref<'admin' | 'evaluator' | 'viewer'>('evaluator')
const addingMember = ref(false)

// Audit
const auditLogs = ref<AuditLogItem[]>([])
const auditLoading = ref(false)
const auditFilter = ref('')

async function loadWorkspaces() {
  loading.value = true
  try {
    workspaces.value = await workspaceApi.list()
  } catch (e: any) {
    ElMessage.error(e?.detail || e?.message || '加载工作区列表失败')
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请输入工作区名称')
    return
  }
  creating.value = true
  try {
    await workspaceApi.create({
      name: createForm.value.name.trim(),
      description: createForm.value.description.trim() || undefined,
    })
    ElMessage.success('工作区创建成功')
    showCreateDialog.value = false
    createForm.value = { name: '', description: '' }
    await loadWorkspaces()
  } catch (e: any) {
    ElMessage.error(e?.detail || e?.message || '创建失败')
  } finally {
    creating.value = false
  }
}

async function handleDelete(ws: WorkspaceItem) {
  try {
    await workspaceApi.delete(ws.id)
    ElMessage.success('工作区已删除')
    await loadWorkspaces()
    if (activeWorkspace.value?.id === ws.id) {
      drawerVisible.value = false
    }
  } catch (e: any) {
    ElMessage.error(e?.detail || e?.message || '删除失败')
  }
}

async function handleRotateKey(ws: WorkspaceItem) {
  try {
    await ElMessageBox.confirm(`确定轮换「${ws.name}」的 API Key？旧 Key 将立即失效。`, '确认轮换', {
      confirmButtonText: '确认轮换',
      cancelButtonText: '取消',
      type: 'warning',
    })
    const result = await workspaceApi.rotateKey(ws.id)
    ws.api_key = result.api_key
    ElMessage.success('API Key 已轮换')
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.detail || e?.message || '轮换失败')
    }
  }
}

function copyKey(key: string) {
  navigator.clipboard.writeText(key).then(() => {
    ElMessage.success('已复制 API Key')
  })
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

// ── Workspace Detail ──

async function viewWorkspace(ws: WorkspaceItem) {
  activeWorkspace.value = ws
  drawerVisible.value = true
  detailTab.value = 'overview'
  await loadMembers(ws.id)
  await loadAuditLogs(ws.id)
}

// ── Members ──

async function loadMembers(wsId: string) {
  membersLoading.value = true
  try {
    members.value = await workspaceApi.getMembers(wsId)
  } catch {
    members.value = []
  } finally {
    membersLoading.value = false
  }
}

async function handleAddMember() {
  if (!newMemberUserId.value.trim()) {
    ElMessage.warning('请输入用户 ID')
    return
  }
  if (!activeWorkspace.value) return
  addingMember.value = true
  try {
    await workspaceApi.addMember(activeWorkspace.value.id, {
      user_id: newMemberUserId.value.trim(),
      role: newMemberRole.value,
    })
    ElMessage.success('成员已添加')
    newMemberUserId.value = ''
    await loadMembers(activeWorkspace.value.id)
  } catch (e: any) {
    ElMessage.error(e?.detail || e?.message || '添加失败')
  } finally {
    addingMember.value = false
  }
}

async function handleRemoveMember(userId: string) {
  if (!activeWorkspace.value) return
  try {
    await workspaceApi.removeMember(activeWorkspace.value.id, userId)
    ElMessage.success('成员已移除')
    await loadMembers(activeWorkspace.value.id)
  } catch (e: any) {
    ElMessage.error(e?.detail || e?.message || '移除失败')
  }
}

// ── Audit Logs ──

async function loadAuditLogs(wsId: string) {
  auditLoading.value = true
  try {
    auditLogs.value = await workspaceApi.getAuditLogs(wsId, 50, auditFilter.value || undefined)
  } catch {
    auditLogs.value = []
  } finally {
    auditLoading.value = false
  }
}

// ── Helpers ──

function roleLabel(role: string) {
  const map: Record<string, string> = { admin: '管理员', evaluator: '评估员', viewer: '观察者' }
  return map[role] || role
}

function roleTag(role: string) {
  const map: Record<string, string> = { admin: 'danger', evaluator: 'primary', viewer: 'info' }
  return map[role] || 'info'
}

function auditActionLabel(action: string) {
  const map: Record<string, string> = {
    created: '创建', updated: '更新', deleted: '删除',
    member_added: '添加成员', member_removed: '移除成员',
    api_key_rotated: 'Key 轮换',
  }
  return map[action] || action
}

onMounted(loadWorkspaces)
</script>

<style scoped lang="scss">
.workspaces-page {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  h2 {
    margin: 0;
    font-size: 22px;
  }
}

.form-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
</style>
