<template>
  <div class="tasks-page">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <h2>任务管理</h2>
        <span class="task-count">共 {{ tasks.length }} 个任务</span>
      </div>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon>
        创建任务
      </el-button>
    </div>

    <!-- Filters -->
    <el-card class="filter-card" shadow="never">
      <el-row :gutter="16">
        <el-col :span="8">
          <el-input
            v-model="searchQuery"
            placeholder="搜索任务目标..."
            clearable
            :prefix-icon="Search"
          />
        </el-col>
        <el-col :span="6">
          <el-select v-model="statusFilter" placeholder="状态筛选" clearable>
            <el-option label="全部" value="" />
            <el-option label="待处理" value="pending" />
            <el-option label="运行中" value="running" />
            <el-option label="已完成" value="completed" />
            <el-option label="失败" value="failed" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
          />
        </el-col>
        <el-col :span="4">
          <el-button @click="fetchTasks">刷新</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- Task List -->
    <el-card class="task-list-card" shadow="never">
      <el-table
        :data="filteredTasks"
        style="width: 100%"
        @row-click="handleRowClick"
        v-loading="loading"
      >
        <el-table-column prop="id" label="ID" width="280">
          <template #default="{ row }">
            <span class="task-id">{{ row.id.substring(0, 8) }}...</span>
          </template>
        </el-table-column>

        <el-table-column prop="goal" label="任务目标" min-width="300">
          <template #default="{ row }">
            <div class="goal-cell">
              <span class="goal-text">{{ row.goal }}</span>
              <el-tag v-if="row.context" size="small" type="info">
                {{ Object.keys(row.context).length }} 个上下文
              </el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" effect="light">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            <span>{{ formatDateTime(row.created_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click.stop="handleEvaluate(row)">
              评估
            </el-button>
            <el-button type="success" link @click.stop="handleAddTrajectory(row)">
              添加轨迹
            </el-button>
            <el-button type="info" link @click.stop="router.push(`/tasks/${row.id}`)">
              详情
            </el-button>
            <el-popconfirm
              title="确定删除该任务及其所有轨迹和评估记录？"
              confirm-button-text="删除"
              cancel-button-text="取消"
              @confirm="handleDeleteTask(row)"
            >
              <template #reference>
                <el-button type="danger" link @click.stop>
                  删除
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="totalTasks"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchTasks"
          @current-change="fetchTasks"
        />
      </div>
    </el-card>

    <!-- Create Task Dialog -->
    <el-dialog
      v-model="showCreateDialog"
      title="创建新任务"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-width="100px"
      >
        <el-form-item label="任务目标" prop="goal">
          <el-input
            v-model="createForm.goal"
            type="textarea"
            :rows="3"
            placeholder="请输入Agent需要完成的目标..."
          />
        </el-form-item>

        <el-form-item label="上下文">
          <div class="context-editor">
            <div v-for="(item, index) in contextItems" :key="index" class="context-item">
              <el-input v-model="item.key" placeholder="键" style="width: 40%" />
              <el-input v-model="item.value" placeholder="值" style="width: 40%" />
              <el-button type="danger" :icon="Delete" circle @click="removeContext(index)" />
            </div>
            <el-button type="primary" link @click="addContext">
              <el-icon><Plus /></el-icon>
              添加上下文
            </el-button>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="creating">
          创建
        </el-button>
      </template>
    </el-dialog>

    <!-- Add Trajectory Dialog -->
    <el-dialog
      v-model="showTrajectoryDialog"
      title="添加执行轨迹"
      width="800px"
      :close-on-click-modal="false"
    >
      <div class="trajectory-editor">
        <div v-for="(step, index) in trajectorySteps" :key="index" class="step-item">
          <div class="step-header">
            <span class="step-number">步骤 {{ index + 1 }}</span>
            <el-button type="danger" link @click="removeStep(index)">删除</el-button>
          </div>

          <el-row :gutter="12">
            <el-col :span="8">
              <el-select v-model="step.action_type" placeholder="动作类型">
                <el-option label="计划" value="plan" />
                <el-option label="工具调用" value="tool_call" />
                <el-option label="思考" value="think" />
                <el-option label="重规划" value="replan" />
              </el-select>
            </el-col>
            <el-col :span="16">
              <el-input
                v-model="step.action_detail"
                type="textarea"
                :rows="2"
                placeholder="动作详情 (JSON格式)"
              />
            </el-col>
          </el-row>

          <el-input
            v-model="step.observation"
            type="textarea"
            :rows="2"
            placeholder="观察结果 (可选)"
            style="margin-top: 8px"
          />
        </div>

        <el-button type="primary" @click="addStep" style="margin-top: 12px">
          <el-icon><Plus /></el-icon>
          添加步骤
        </el-button>
      </div>

      <template #footer>
        <el-button @click="showTrajectoryDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitTrajectory" :loading="submitting">
          提交
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Delete, Search } from '@element-plus/icons-vue'
import { taskApi, evaluationApi } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import dayjs from 'dayjs'

const router = useRouter()

// State
const loading = ref(false)
const creating = ref(false)
const submitting = ref(false)
const tasks = ref<any[]>([])
const searchQuery = ref('')
const statusFilter = ref('')
const dateRange = ref<[Date, Date] | null>(null)
const currentPage = ref(1)
const pageSize = ref(20)
const totalTasks = ref(0)

// Dialogs
const showCreateDialog = ref(false)
const showTrajectoryDialog = ref(false)
const currentTaskId = ref('')

// Form
const createFormRef = ref<FormInstance>()
const createForm = reactive({
  goal: '',
})

const createRules: FormRules = {
  goal: [
    { required: true, message: '请输入任务目标', trigger: 'blur' },
    { min: 10, message: '任务目标至少10个字符', trigger: 'blur' },
  ],
}

// Context items
const contextItems = ref<{ key: string; value: string }[]>([])

// Trajectory steps
const trajectorySteps = ref<{
  action_type: string
  action_detail: string
  observation: string
}[]>([])

// Computed
const filteredTasks = computed(() => {
  let result = tasks.value

  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(t => t.goal.toLowerCase().includes(query))
  }

  if (statusFilter.value) {
    result = result.filter(t => t.status === statusFilter.value)
  }

  return result
})

// Methods
const getStatusType = (status: string) => {
  const map: Record<string, string> = {
    completed: 'success',
    running: 'primary',
    pending: 'info',
    failed: 'danger',
  }
  return map[status] || 'info'
}

const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    completed: '已完成',
    running: '运行中',
    pending: '待处理',
    failed: '失败',
  }
  return map[status] || status
}

const formatDateTime = (date: string) => {
  if (!date) return '-'
  // 后端存储 UTC 时间，SQLite 不保留时区信息，需追加 Z 让 dayjs 按 UTC 解析后转本地时间
  const d = date.endsWith('Z') || date.includes('+') ? date : date + 'Z'
  return dayjs(d).format('YYYY-MM-DD HH:mm:ss')
}

const fetchTasks = async () => {
  loading.value = true
  try {
    const { items, total } = await taskApi.list({
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value,
    })
    tasks.value = items
    totalTasks.value = total
  } catch (error) {
    console.error('Failed to fetch tasks:', error)
  } finally {
    loading.value = false
  }
}

const handleRowClick = (row: any) => {
  router.push(`/tasks/${row.id}`)
}

const handleCreate = async () => {
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return

  creating.value = true
  try {
    const context: Record<string, string> = {}
    contextItems.value.forEach(item => {
      if (item.key && item.value) {
        context[item.key] = item.value
      }
    })

    await taskApi.create({
      goal: createForm.goal,
      context: Object.keys(context).length > 0 ? context : undefined,
    })

    ElMessage.success('任务创建成功')
    showCreateDialog.value = false
    createForm.goal = ''
    contextItems.value = []
    fetchTasks()
  } catch (error) {
    console.error('Failed to create task:', error)
  } finally {
    creating.value = false
  }
}

const addContext = () => {
  contextItems.value.push({ key: '', value: '' })
}

const removeContext = (index: number) => {
  contextItems.value.splice(index, 1)
}

const handleAddTrajectory = (task: any) => {
  currentTaskId.value = task.id
  trajectorySteps.value = [
    { action_type: 'plan', action_detail: '', observation: '' },
  ]
  showTrajectoryDialog.value = true
}

const addStep = () => {
  trajectorySteps.value.push({
    action_type: 'tool_call',
    action_detail: '',
    observation: '',
  })
}

const removeStep = (index: number) => {
  trajectorySteps.value.splice(index, 1)
}

const handleSubmitTrajectory = async () => {
  submitting.value = true
  try {
    const steps = trajectorySteps.value.map((step, index) => {
      let actionDetail: any
      try {
        actionDetail = JSON.parse(step.action_detail)
      } catch {
        actionDetail = { raw: step.action_detail }
      }

      return {
        step_number: index + 1,
        action_type: step.action_type,
        action_detail: actionDetail,
        observation: step.observation || undefined,
      }
    })

    await taskApi.addTrajectory(currentTaskId.value, steps)
    ElMessage.success('轨迹添加成功')
    showTrajectoryDialog.value = false
    fetchTasks()
  } catch (error) {
    console.error('Failed to add trajectory:', error)
  } finally {
    submitting.value = false
  }
}

const handleEvaluate = async (task: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要评估任务 "${task.goal.substring(0, 50)}..." 吗？`,
      '确认评估',
      { type: 'info' }
    )

    // 发起异步评估，后端立即返回 evaluation ID（status=in_progress）
    const result = await evaluationApi.run({ task_id: task.id, use_stream: true })

    ElMessage.success('评估已启动，正在实时推送进度…')
    router.push(`/evaluations/${result.id}?stream=1`)
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to run evaluation:', error)
    }
  }
}

const handleDeleteTask = async (task: any) => {
  try {
    await taskApi.delete(task.id)
    ElMessage.success('任务已删除')
    fetchTasks()
  } catch (error) {
    console.error('Failed to delete task:', error)
  }
}

// Lifecycle
onMounted(() => {
  fetchTasks()
})
</script>

<style scoped lang="scss">
.tasks-page {
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;

    .header-left {
      display: flex;
      align-items: baseline;
      gap: 12px;

      h2 {
        margin: 0;
        font-size: 20px;
      }

      .task-count {
        color: var(--text-color-secondary);
        font-size: 14px;
      }
    }
  }

  .filter-card {
    margin-bottom: 20px;
  }

  .task-list-card {
    .task-id {
      font-family: monospace;
      font-size: 12px;
      color: var(--text-color-secondary);
    }

    .goal-cell {
      display: flex;
      align-items: center;
      gap: 8px;

      .goal-text {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }

    .pagination-wrapper {
      display: flex;
      justify-content: flex-end;
      margin-top: 20px;
    }
  }

  .context-editor {
    width: 100%;

    .context-item {
      display: flex;
      gap: 8px;
      margin-bottom: 8px;
    }
  }

  .trajectory-editor {
    .step-item {
      background: var(--bg-color);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 12px;

      .step-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;

        .step-number {
          font-weight: 600;
          color: var(--primary-color);
        }
      }
    }
  }
}
</style>
