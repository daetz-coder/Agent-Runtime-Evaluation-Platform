<template>
  <div class="evaluations-page">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <h2>评估记录</h2>
        <span class="eval-count">共 {{ evaluations.length }} 条记录</span>
      </div>
      <el-button type="primary" @click="fetchEvaluations">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <!-- Stats Summary -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon" style="background: rgba(103, 194, 58, 0.1)">
            <el-icon :size="24" color="#67c23a"><CircleCheck /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ completedCount }}</div>
            <div class="stat-title">已完成</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon" style="background: rgba(64, 158, 255, 0.1)">
            <el-icon :size="24" color="#409eff"><Loading /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ inProgressCount }}</div>
            <div class="stat-title">进行中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon" style="background: rgba(230, 162, 60, 0.1)">
            <el-icon :size="24" color="#e6a23c"><TrendCharts /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ averageScore }}</div>
            <div class="stat-title">平均得分</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon" style="background: rgba(245, 108, 108, 0.1)">
            <el-icon :size="24" color="#f56c6c"><Warning /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ failedCount }}</div>
            <div class="stat-title">失败</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Filters -->
    <el-card class="filter-card" shadow="never">
      <el-row :gutter="16">
        <el-col :span="8">
          <el-select v-model="statusFilter" placeholder="状态筛选" clearable>
            <el-option label="全部" value="" />
            <el-option label="已完成" value="completed" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="待处理" value="pending" />
            <el-option label="失败" value="failed" />
          </el-select>
        </el-col>
        <el-col :span="8">
          <el-slider
            v-model="scoreRange"
            range
            :min="0"
            :max="100"
            :marks="{ 0: '0', 50: '50', 100: '100' }"
          />
        </el-col>
        <el-col :span="8">
          <el-button type="primary" @click="fetchEvaluations">筛选</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- Evaluation List -->
    <el-card class="eval-list-card" shadow="never">
      <el-table :data="filteredEvaluations" style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="280">
          <template #default="{ row }">
            <span class="eval-id">{{ row.id.substring(0, 8) }}...</span>
          </template>
        </el-table-column>

        <el-table-column prop="task_goal" label="关联任务" min-width="200">
          <template #default="{ row }">
            <el-button type="primary" link @click="router.push(`/tasks/${row.task_id}`)">
              {{ row.task_goal || row.task_id.substring(0, 8) + '...' }}
            </el-button>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" effect="light">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="综合" width="80">
          <template #default="{ row }">
            <span :style="{ color: getScoreColor(row.overall_score), fontWeight: 600 }">
              {{ row.overall_score ?? '-' }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="六维得分" min-width="360">
          <template #default="{ row }">
            <div class="score-bars compact">
              <div v-for="dim in dimensions" :key="dim.key" class="score-bar-item">
                <span class="dim-name">{{ dim.name }}</span>
                <el-progress
                  :percentage="getScore(row, dim.key)"
                  :color="dim.color"
                  :stroke-width="6"
                  :show-text="false"
                />
                <span class="dim-score">{{ getScore(row, dim.key) }}</span>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            <span>{{ formatDateTime(row.created_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="router.push(`/evaluations/${row.id}`)">
              查看详情
            </el-button>
            <el-popconfirm
              title="确定删除该评估记录？"
              confirm-button-text="删除"
              cancel-button-text="取消"
              @confirm="handleDeleteEvaluation(row)"
            >
              <template #reference>
                <el-button type="danger" link>
                  删除
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 空状态 -->
      <el-empty v-if="!loading && filteredEvaluations.length === 0" description="暂无评估记录" />

      <!-- Pagination -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="totalEvaluations"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchEvaluations"
          @current-change="fetchEvaluations"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh, CircleCheck, Loading, TrendCharts, Warning } from '@element-plus/icons-vue'
import { reportApi, evaluationApi } from '@/api'
import dayjs from 'dayjs'

const router = useRouter()

// State
const loading = ref(false)
const evaluations = ref<any[]>([])
const statusFilter = ref('')
const scoreRange = ref<[number, number]>([0, 100])
const currentPage = ref(1)
const pageSize = ref(20)
const totalEvaluations = ref(0)

// Dimensions config
const dimensions = [
  { key: 'planning', name: '规划', color: '#409eff' },
  { key: 'tactical', name: '战术', color: '#67c23a' },
  { key: 'tool_use', name: '工具', color: '#e6a23c' },
  { key: 'memory', name: '记忆', color: '#f56c6c' },
  { key: 'replan', name: '重规划', color: '#909399' },
  { key: 'retrieval', name: '检索', color: '#9b59b6' },
]

// Computed
const filteredEvaluations = computed(() => {
  let result = evaluations.value

  if (statusFilter.value) {
    result = result.filter(e => e.status === statusFilter.value)
  }

  // Score filter
  const [minScore, maxScore] = scoreRange.value
  result = result.filter(e => {
    const score = e.overall_score || 0
    return score >= minScore && score <= maxScore
  })

  return result
})

const completedCount = computed(() => {
  return evaluations.value.filter(e => e.status === 'completed').length
})

const inProgressCount = computed(() => {
  return evaluations.value.filter(e => e.status === 'in_progress').length
})

const failedCount = computed(() => {
  return evaluations.value.filter(e => e.status === 'failed').length
})

const averageScore = computed(() => {
  const completed = evaluations.value.filter(e => e.overall_score)
  if (completed.length === 0) return 0
  const sum = completed.reduce((acc, e) => acc + (e.overall_score || 0), 0)
  return Math.round(sum / completed.length)
})

// Methods
const getStatusType = (status: string) => {
  const map: Record<string, string> = {
    completed: 'success',
    in_progress: 'primary',
    pending: 'info',
    failed: 'danger',
  }
  return map[status] || 'info'
}

const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    completed: '已完成',
    in_progress: '进行中',
    pending: '待处理',
    failed: '失败',
  }
  return map[status] || status
}

const getScore = (evaluation: any, dimKey: string) => {
  const scoreField = `${dimKey}_score`
  return Math.round(evaluation[scoreField] || 0)
}

const getScoreColor = (score: number) => {
  if (score >= 80) return '#67c23a'
  if (score >= 60) return '#e6a23c'
  return '#f56c6c'
}

const formatDateTime = (date: string) => {
  if (!date) return '-'
  const d = date.endsWith('Z') || date.includes('+') ? date : date + 'Z'
  return dayjs(d).format('YYYY-MM-DD HH:mm:ss')
}

const fetchEvaluations = async () => {
  loading.value = true
  try {
    const skip = (currentPage.value - 1) * pageSize.value
    const [summary, items] = await Promise.all([
      reportApi.getSummary(),
      evaluationApi.list({ skip, limit: pageSize.value }),
    ])
    evaluations.value = items as any[]
    totalEvaluations.value = summary.total_evaluations || evaluations.value.length
  } catch (error) {
    console.error('Failed to fetch evaluations:', error)
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  statusFilter.value = ''
  scoreRange.value = [0, 100]
}

const handleDeleteEvaluation = async (evaluation: any) => {
  try {
    await evaluationApi.delete(evaluation.id)
    ElMessage.success('评估记录已删除')
    fetchEvaluations()
  } catch (error) {
    console.error('Failed to delete evaluation:', error)
  }
}

// Lifecycle
onMounted(() => {
  fetchEvaluations()
})
</script>

<style scoped lang="scss">
.evaluations-page {
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
      }

      .eval-count {
        color: var(--text-color-secondary);
      }
    }
  }

  .stats-row {
    margin-bottom: 20px;
  }

  .stat-card {
    :deep(.el-card__body) {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .stat-icon {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .stat-content {
      .stat-value {
        font-size: 24px;
        font-weight: 600;
      }

      .stat-title {
        font-size: 14px;
        color: var(--text-color-secondary);
      }
    }
  }

  .filter-card {
    margin-bottom: 20px;
  }

  .eval-list-card {
    .eval-id {
      font-family: monospace;
      font-size: 12px;
      color: var(--text-color-secondary);
    }

    .score-bars {
      display: flex;
      flex-direction: column;
      gap: 4px;

      &.compact {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 4px 12px;
      }

      .score-bar-item {
        display: flex;
        align-items: center;
        gap: 8px;

        .dim-name {
          width: 40px;
          font-size: 12px;
          color: var(--text-color-secondary);
        }

        .el-progress {
          flex: 1;
        }

        .dim-score {
          width: 30px;
          text-align: right;
          font-size: 12px;
          font-weight: 600;
        }
      }
    }

    .pagination-wrapper {
      display: flex;
      justify-content: flex-end;
      margin-top: 20px;
    }
  }
}
</style>
