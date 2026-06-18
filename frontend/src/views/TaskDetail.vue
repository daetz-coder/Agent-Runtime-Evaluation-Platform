<template>
  <div class="task-detail" v-loading="loading">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <el-button :icon="ArrowLeft" @click="router.back()">返回</el-button>
        <h2>任务详情</h2>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="handleEvaluate" :loading="evaluating">
          <el-icon><VideoPlay /></el-icon>
          运行评估
        </el-button>
        <el-button @click="showTrajectoryDialog = true">
          <el-icon><Plus /></el-icon>
          添加轨迹
        </el-button>
      </div>
    </div>

    <template v-if="task">
      <!-- Task Info Card -->
      <el-card class="info-card" shadow="hover">
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">任务ID</span>
            <span class="info-value monospace">{{ task.id }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">状态</span>
            <el-tag :type="getStatusType(task.status)">{{ getStatusText(task.status) }}</el-tag>
          </div>
          <div class="info-item">
            <span class="info-label">创建时间</span>
            <span class="info-value">{{ formatDateTime(task.created_at) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">开始时间</span>
            <span class="info-value">{{ task.started_at ? formatDateTime(task.started_at) : '-' }}</span>
          </div>
          <div class="info-item full-width">
            <span class="info-label">任务目标</span>
            <div class="info-value goal">{{ task.goal }}</div>
          </div>
          <div v-if="task.context" class="info-item full-width">
            <span class="info-label">上下文</span>
            <div class="info-value">
              <pre class="context-json">{{ JSON.stringify(task.context, null, 2) }}</pre>
            </div>
          </div>
        </div>
      </el-card>

      <!-- Trajectory Section -->
      <el-card class="trajectory-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span>执行轨迹</span>
            <el-tag type="info">{{ trajectory.length }} 步</el-tag>
          </div>
        </template>

        <div v-if="trajectory.length === 0" class="empty-trajectory">
          <el-empty description="暂无执行轨迹">
            <el-button type="primary" @click="showTrajectoryDialog = true">添加轨迹</el-button>
          </el-empty>
        </div>

        <el-timeline v-else>
          <el-timeline-item
            v-for="step in trajectory"
            :key="step.step_number"
            :type="getStepType(step.action_type)"
            :timestamp="formatTime(step.timestamp)"
            placement="top"
          >
            <el-card class="step-card" shadow="never">
              <div class="step-header">
                <el-tag :type="getStepType(step.action_type)" size="small">
                  {{ getStepTypeName(step.action_type) }}
                </el-tag>
                <span class="step-number">步骤 {{ step.step_number }}</span>
              </div>
              <div class="step-content">
                <pre>{{ formatActionDetail(step.action_detail) }}</pre>
              </div>
              <div v-if="step.observation" class="step-observation">
                <strong>观察结果：</strong>
                <pre>{{ step.observation }}</pre>
              </div>
            </el-card>
          </el-timeline-item>
        </el-timeline>
      </el-card>

      <!-- Evaluations History -->
      <el-card class="evaluations-card" shadow="hover">
        <template #header>
          <span>评估历史</span>
        </template>

        <div v-if="evaluations.length === 0" class="empty-evaluations">
          <el-empty description="暂无评估记录" />
        </div>

        <el-table v-else :data="evaluations" style="width: 100%">
          <el-table-column prop="id" label="评估ID" width="280">
            <template #default="{ row }">
              <el-button type="primary" link @click="router.push(`/evaluations/${row.id}`)">
                {{ row.id.substring(0, 8) }}...
              </el-button>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="getEvalStatusType(row.status)">{{ getEvalStatusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="overall_score" label="综合得分" width="120">
            <template #default="{ row }">
              <span :style="{ color: getScoreColor(row.overall_score), fontWeight: 600 }">
                {{ row.overall_score || '-' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" />
        </el-table>
      </el-card>
    </template>

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
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, VideoPlay, Plus } from '@element-plus/icons-vue'
import { taskApi, evaluationApi, reportApi, withSilent } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()

// State
const loading = ref(false)
const evaluating = ref(false)
const submitting = ref(false)
const task = ref<any>(null)
const trajectory = ref<any[]>([])
const evaluations = ref<any[]>([])
const showTrajectoryDialog = ref(false)
const trajectorySteps = ref<{
  action_type: string
  action_detail: string
  observation: string
}[]>([])

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

const getEvalStatusType = (status: string) => {
  const map: Record<string, string> = {
    completed: 'success',
    in_progress: 'primary',
    pending: 'info',
    failed: 'danger',
  }
  return map[status] || 'info'
}

const getEvalStatusText = (status: string) => {
  const map: Record<string, string> = {
    completed: '已完成',
    in_progress: '进行中',
    pending: '待处理',
    failed: '失败',
  }
  return map[status] || status
}

const getStepType = (type: string) => {
  const map: Record<string, string> = {
    plan: 'primary',
    tool_call: 'success',
    think: 'warning',
    replan: 'danger',
  }
  return map[type] || 'info'
}

const getStepTypeName = (type: string) => {
  const map: Record<string, string> = {
    plan: '计划',
    tool_call: '工具调用',
    think: '思考',
    replan: '重规划',
  }
  return map[type] || type
}

const getScoreColor = (score: number) => {
  if (score >= 80) return '#67c23a'
  if (score >= 60) return '#e6a23c'
  return '#f56c6c'
}

const formatDateTime = (date: string) => {
  return dayjs(date).format('YYYY-MM-DD HH:mm:ss')
}

const formatTime = (time: string) => {
  return dayjs(time).format('HH:mm:ss')
}

const formatActionDetail = (detail: any) => {
  if (typeof detail === 'string') return detail
  return JSON.stringify(detail, null, 2)
}

const fetchData = async () => {
  const taskId = route.params.id as string
  if (!taskId) return

  loading.value = true
  try {
    const [taskData, history, trajData] = await Promise.all([
      taskApi.getById(taskId),
      reportApi.getTaskHistory(taskId, withSilent()).catch(() => ({ evaluations: [] })),
      taskApi.getTrajectory(taskId, withSilent()).catch(() => ({ steps: [] })),
    ])
    task.value = taskData
    evaluations.value = history.evaluations || []
    trajectory.value = trajData.steps || []
  } catch (error) {
    console.error('Failed to fetch task:', error)
    if ((error as any)?.response?.status === 404) {
      ElMessage.warning('任务不存在或已被删除')
      router.push('/tasks')
    }
  } finally {
    loading.value = false
  }
}

const handleEvaluate = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要运行评估吗？',
      '确认评估',
      { type: 'info' }
    )

    evaluating.value = true
    // 发起异步评估，立即返回 evaluation ID（status=in_progress）
    const result = await evaluationApi.run({ task_id: task.value.id })
    ElMessage.info('评估已启动，正在等待结果...')

    // 轮询直到评估完成
    const evalId = result.id
    const maxAttempts = 60 // 最多等 60 次（约 120 秒）
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise(resolve => setTimeout(resolve, 2000)) // 每 2 秒查一次
      try {
        const detail = await evaluationApi.getById(evalId, { silent: true } as any)
        if (detail.status === 'completed') {
          ElMessage.success('评估完成')
          router.push(`/evaluations/${evalId}`)
          return
        }
        if (detail.status === 'failed') {
          ElMessage.error('评估失败')
          return
        }
      } catch {
        // 忽略轮询中的临时错误
      }
    }
    ElMessage.warning('评估超时，请稍后在评估列表中查看结果')
    router.push(`/evaluations/${evalId}`)
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to run evaluation:', error)
    }
  } finally {
    evaluating.value = false
  }
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

    await taskApi.addTrajectory(task.value.id, steps)
    ElMessage.success('轨迹添加成功')
    showTrajectoryDialog.value = false
    fetchData()
  } catch (error) {
    console.error('Failed to add trajectory:', error)
  } finally {
    submitting.value = false
  }
}

// Lifecycle
onMounted(() => {
  trajectorySteps.value = [
    { action_type: 'plan', action_detail: '', observation: '' },
  ]
  fetchData()
})
</script>

<style scoped lang="scss">
.task-detail {
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;

    .header-left {
      display: flex;
      align-items: center;
      gap: 16px;

      h2 {
        margin: 0;
      }
    }

    .header-right {
      display: flex;
      gap: 12px;
    }
  }

  .info-card {
    margin-bottom: 20px;

    .info-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 20px;

      .info-item {
        &.full-width {
          grid-column: 1 / -1;
        }

        .info-label {
          display: block;
          font-size: 12px;
          color: var(--text-color-secondary);
          margin-bottom: 8px;
        }

        .info-value {
          font-size: 14px;

          &.monospace {
            font-family: monospace;
          }

          &.goal {
            font-size: 16px;
            font-weight: 500;
          }
        }

        .context-json {
          background: var(--bg-color);
          padding: 12px;
          border-radius: 4px;
          font-size: 12px;
          overflow-x: auto;
        }
      }
    }
  }

  .trajectory-card {
    margin-bottom: 20px;

    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .step-card {
      :deep(.el-card__body) {
        padding: 12px;
      }

      .step-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;

        .step-number {
          font-size: 12px;
          color: var(--text-color-secondary);
        }
      }

      .step-content {
        pre {
          margin: 0;
          padding: 8px;
          background: var(--bg-color);
          border-radius: 4px;
          font-size: 12px;
          overflow-x: auto;
        }
      }

      .step-observation {
        margin-top: 8px;
        font-size: 13px;

        strong {
          color: var(--text-color-secondary);
        }

        pre {
          margin: 4px 0 0 0;
          padding: 8px;
          background: #f0f9ff;
          border-radius: 4px;
          font-size: 12px;
        }
      }
    }
  }

  .evaluations-card {
    .empty-evaluations {
      padding: 40px 0;
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
