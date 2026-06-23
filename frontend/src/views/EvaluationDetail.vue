<template>
  <div class="evaluation-detail" v-loading="loading">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <el-button :icon="ArrowLeft" @click="router.back()">返回</el-button>
        <h2>评估详情</h2>
      </div>
      <el-tag :type="getStatusType(evaluation?.status)" size="large">
        {{ getStatusText(evaluation?.status) }}
      </el-tag>
    </div>

    <template v-if="evaluation">
      <!-- In-progress banner -->
      <el-alert
        v-if="evaluation.status === 'in_progress'"
        title="评估正在进行中，页面将自动刷新..."
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 20px"
      >
        <template #default>
          <div style="display: flex; align-items: center; gap: 8px">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>正在运行 5 个评估器，请稍候（约 30-60 秒）</span>
          </div>
        </template>
      </el-alert>

      <!-- Overall Score Card -->
      <el-card class="overall-card" shadow="hover" v-if="evaluation.status === 'completed'">
        <div class="overall-content">
          <div class="score-circle">
            <el-progress
              type="dashboard"
              :percentage="overallScore"
              :color="getScoreColor(overallScore)"
              :width="160"
              :stroke-width="12"
            >
              <template #default>
                <div class="score-text">
                  <span class="score-value">{{ overallScore }}</span>
                  <span class="score-label">综合得分</span>
                </div>
              </template>
            </el-progress>
          </div>

          <div class="score-summary">
            <h3>{{ evaluation.evaluation?.summary || '评估完成' }}</h3>
            <div class="recommendations">
              <h4>改进建议：</h4>
              <ul>
                <li v-for="(rec, index) in evaluation.evaluation?.recommendations" :key="index">
                  {{ rec }}
                </li>
              </ul>
            </div>
          </div>
        </div>
      </el-card>

      <!-- Dimension Scores -->
      <div class="dimension-grid" v-if="evaluation.status === 'completed'">
        <el-card v-for="dim in dimensions" :key="dim.key" class="dimension-card" shadow="hover">
          <div class="dimension-header">
            <div class="dimension-icon" :style="{ background: dim.bgColor }">
              <el-icon :size="24" :color="dim.color">
                <component :is="dim.icon" />
              </el-icon>
            </div>
            <div class="dimension-title">
              <h4>{{ dim.name }}</h4>
              <span class="dimension-score" :style="{ color: dim.color }">
                {{ getDimensionScore(dim.key) }}
              </span>
            </div>
          </div>

          <div class="dimension-detail">
            <div v-for="(metric, key) in dim.metrics" :key="key" class="metric-item">
              <span class="metric-name">{{ metric }}</span>
              <el-progress
                :percentage="getMetricScore(dim.key, key)"
                :color="getScoreColor(getMetricScore(dim.key, key))"
                :stroke-width="8"
                :show-text="false"
              />
              <span class="metric-value">{{ getMetricScore(dim.key, key) }}</span>
            </div>
          </div>

          <div class="dimension-feedback">
            <p>{{ getDimensionFeedback(dim.key) }}</p>
          </div>
        </el-card>
      </div>

      <!-- Detailed Analysis -->
      <el-card class="analysis-card" shadow="hover" v-if="evaluation.status === 'completed'">
        <template #header>
          <div class="card-header">
            <span>详细分析</span>
            <el-radio-group v-model="selectedDimension" size="small">
              <el-radio-button v-for="dim in dimensions" :key="dim.key" :label="dim.key">
                {{ dim.name }}
              </el-radio-button>
            </el-radio-group>
          </div>
        </template>

        <div class="analysis-content">
          <!-- Radar Chart -->
          <div class="chart-section">
            <div ref="radarChart" class="chart-container"></div>
          </div>

          <!-- Feedback Section -->
          <div class="feedback-section">
            <h4>详细反馈</h4>
            <div class="feedback-content">
              {{ currentFeedback }}
            </div>

            <h4 v-if="currentIssues.length">发现的问题</h4>
            <ul v-if="currentIssues.length" class="issues-list">
              <li v-for="(issue, index) in currentIssues" :key="index">
                <el-icon color="#e6a23c"><Warning /></el-icon>
                {{ issue }}
              </li>
            </ul>

            <h4 v-if="currentSuggestions.length">改进建议</h4>
            <ul v-if="currentSuggestions.length" class="suggestions-list">
              <li v-for="(suggestion, index) in currentSuggestions" :key="index">
                <el-icon color="#67c23a"><CircleCheck /></el-icon>
                {{ suggestion }}
              </li>
            </ul>
          </div>
        </div>
      </el-card>

      <!-- Trajectory Analysis -->
      <el-card class="trajectory-card" shadow="hover" v-if="trajectory.length > 0">
        <template #header>
          <div class="card-header">
            <span>执行轨迹分析</span>
            <el-tag type="info">共 {{ trajectory.length }} 步</el-tag>
          </div>
        </template>

        <div class="timeline">
          <el-timeline>
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
        </div>
      </el-card>

      <!-- Multi-model Consensus -->
      <el-card class="consensus-card" shadow="hover" v-if="consensusData">
        <template #header>
          <div class="card-header">
            <span>多模型共识评估</span>
            <el-tag :type="consensusData.result.consensus_type === 'cross_provider' ? 'success' : 'warning'" size="small">
              {{ consensusData.result.consensus_type === 'cross_provider' ? '跨厂商' : '同厂商' }}
            </el-tag>
            <el-tag v-if="consensusData.result.std_score !== undefined" 
              :type="consensusData.result.std_score < 10 ? 'success' : 'warning'" size="small" style="margin-left:4px">
              std={{ consensusData.result.std_score.toFixed(1) }}
            </el-tag>
          </div>
        </template>
        <el-row :gutter="16">
          <el-col :span="12">
            <div ref="consensusChart" class="consensus-chart"></div>
          </el-col>
          <el-col :span="12">
            <div class="consensus-info">
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item label="参与模型">{{ consensusData.result.model_count }} 个</el-descriptions-item>
                <el-descriptions-item label="综合均分">{{ consensusData.result.mean_score }}</el-descriptions-item>
                <el-descriptions-item label="分歧度 (std)">
                  <el-tag :type="consensusData.result.std_score > 15 ? 'danger' : 'success'" size="small">
                    {{ consensusData.result.std_score > 15 ? '高分歧' : '一致' }}
                  </el-tag>
                </el-descriptions-item>
              </el-descriptions>
              <div style="margin-top:12px">
                <div v-for="(score, model) in consensusData.result.individual_scores" :key="model" class="model-score-row">
                  <span class="model-name">{{ model }}</span>
                  <el-progress :percentage="score" :color="getScoreColor(score)" :stroke-width="8" style="flex:1;margin:0 8px" />
                  <span class="model-score">{{ score }}</span>
                </div>
              </div>
            </div>
          </el-col>
        </el-row>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { ArrowLeft, Warning, CircleCheck, DataAnalysis, TrendCharts, Tools, Memory, Refresh, Loading } from '@element-plus/icons-vue'
import { evaluationApi, taskApi, withSilent } from '@/api'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()

// State
const loading = ref(false)
const evaluation = ref<any>(null)
const trajectory = ref<any[]>([])
const selectedDimension = ref('planning')
const radarChart = ref<HTMLElement>()
let radarInstance: echarts.ECharts | null = null
let consensusInstance: echarts.ECharts | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null
const consensusData = ref<any>(null)
const consensusChart = ref<HTMLElement>()

// Dimensions config
const dimensions = [
  {
    key: 'planning',
    name: '规划质量',
    icon: 'DataAnalysis',
    color: '#409eff',
    bgColor: 'rgba(64, 158, 255, 0.1)',
    metrics: {
      coverage: '覆盖率',
      ordering: '顺序性',
      granularity: '粒度',
      completeness: '完整性',
    },
  },
  {
    key: 'tactical',
    name: '战术决策',
    icon: 'TrendCharts',
    color: '#67c23a',
    bgColor: 'rgba(103, 194, 58, 0.1)',
    metrics: {
      relevance: '相关性',
      efficiency: '效率',
      correctness: '正确性',
    },
  },
  {
    key: 'tool_use',
    name: '工具使用',
    icon: 'Tools',
    color: '#e6a23c',
    bgColor: 'rgba(230, 162, 60, 0.1)',
    metrics: {
      selection_quality: '选择质量',
      parameter_accuracy: '参数准确性',
      result_utilization: '结果利用',
    },
  },
  {
    key: 'memory',
    name: '记忆保持',
    icon: 'Memory',
    color: '#f56c6c',
    bgColor: 'rgba(245, 108, 108, 0.1)',
    metrics: {
      retention: '保持力',
      relevance: '相关性',
      consistency: '一致性',
    },
  },
  {
    key: 'replan',
    name: '重规划',
    icon: 'Refresh',
    color: '#909399',
    bgColor: 'rgba(144, 147, 153, 0.1)',
    metrics: {
      trigger_appropriateness: '触发适当性',
      adaptation_quality: '适应质量',
      learning_from_failure: '学习能力',
    },
  },
  {
    key: 'retrieval',
    name: '检索质量',
    icon: 'Search',
    color: '#9b59b6',
    bgColor: 'rgba(155, 89, 182, 0.1)',
    metrics: {
      relevance: '相关性',
      evidence_accuracy: '证据准确性',
      coverage: '覆盖度',
    },
  },
]

// Computed
const overallScore = computed(() => {
  return Math.round(evaluation.value?.evaluation?.overall_score || 0)
})

const currentDimensionData = computed(() => {
  return evaluation.value?.evaluation?.[selectedDimension.value] || {}
})

const currentFeedback = computed(() => {
  return currentDimensionData.value.feedback || '暂无反馈'
})

const currentIssues = computed(() => {
  const data = currentDimensionData.value
  return data.missing_milestones || data.problematic_actions || data.inefficient_calls || data.forgotten_facts || data.missed_replan_opportunities || []
})

const currentSuggestions = computed(() => {
  return currentDimensionData.value.suggestions || []
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

const getScoreColor = (score: number) => {
  if (score >= 80) return '#67c23a'
  if (score >= 60) return '#e6a23c'
  return '#f56c6c'
}

const getDimensionScore = (dimKey: string) => {
  return Math.round(evaluation.value?.evaluation?.[dimKey]?.overall || 0)
}

const getMetricScore = (dimKey: string, metricKey: string) => {
  return Math.round(evaluation.value?.evaluation?.[dimKey]?.[metricKey] || 0)
}

const getDimensionFeedback = (dimKey: string) => {
  return evaluation.value?.evaluation?.[dimKey]?.feedback || ''
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

const formatTime = (time: string) => {
  if (!time) return ''
  const d = time.endsWith('Z') || time.includes('+') ? time : time + 'Z'
  return dayjs(d).format('HH:mm:ss')
}

const formatActionDetail = (detail: any) => {
  if (typeof detail === 'string') return detail
  return JSON.stringify(detail, null, 2)
}

// Initialize radar chart
const initRadarChart = () => {
  if (!radarChart.value) return

  radarInstance = echarts.init(radarChart.value)

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'item',
    },
    radar: {
      indicator: dimensions.map(d => ({
        name: d.name,
        max: 100,
      })),
      shape: 'circle',
      splitNumber: 5,
      axisName: {
        color: '#666',
        fontSize: 12,
      },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: dimensions.map(d => getDimensionScore(d.key)),
            name: '得分',
            areaStyle: {
              color: 'rgba(64, 158, 255, 0.3)',
            },
            lineStyle: {
              color: '#409eff',
              width: 2,
            },
            itemStyle: {
              color: '#409eff',
            },
          },
        ],
      },
    ],
  }

  radarInstance.setOption(option)
}

// Consensus chart — horizontal bar comparing model scores
const initConsensusChart = () => {
  if (!consensusChart.value || !consensusData.value?.result?.individual_scores) return
  if (consensusInstance) consensusInstance.dispose()

  consensusInstance = echarts.init(consensusChart.value)
  const scores = consensusData.value.result.individual_scores
  const models = Object.keys(scores)
  const values = Object.values(scores) as number[]
  const colors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399']

  consensusInstance.setOption({
    title: { text: '模型评分对比', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    grid: { left: '20%', right: '10%', top: '15%', bottom: '5%' },
    xAxis: { type: 'value', min: 0, max: 100 },
    yAxis: { type: 'category', data: models },
    series: [{
      type: 'bar',
      data: values.map((v, i) => ({ value: v, itemStyle: { color: colors[i % colors.length] } })),
      label: { show: true, position: 'right', formatter: '{c}' },
      barMaxWidth: 30,
    }],
  })
}

// Fetch data
const fetchData = async () => {
  const evalId = route.params.id as string
  if (!evalId) return

  loading.value = true
  try {
    const data = await evaluationApi.getById(evalId)
    evaluation.value = data

    // Fetch trajectory (optional — task may have been deleted)
    if (data.task_id) {
      try {
        const trajData = await taskApi.getTrajectory(data.task_id, withSilent())
        trajectory.value = trajData.steps || []
      } catch {
        trajectory.value = []
      }
    }

    setTimeout(initRadarChart, 100)

    // Fetch consensus data for completed evaluations
    if (data.status === 'completed' && data.task_id) {
      try {
        const consensus = await evaluationApi.getConsensus(data.task_id)
        consensusData.value = consensus
        setTimeout(initConsensusChart, 200)
      } catch {
        consensusData.value = null
      }
    }

    // 如果评估还在进行中，启动轮询
    if (data.status === 'in_progress') {
      startPolling(evalId)
    }
  } catch (error) {
    console.error('Failed to fetch evaluation:', error)
  } finally {
    loading.value = false
  }
}

/** 启动轮询：每 5 秒检查评估状态，完成后刷新数据 */
const startPolling = (evalId: string) => {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const data = await evaluationApi.getById(evalId, withSilent() as any)
      if (data.status === 'completed' || data.status === 'failed') {
        // 评估结束，停止轮询并刷新完整数据
        stopPolling()
        evaluation.value = data
        if (data.task_id) {
          try {
            const trajData = await taskApi.getTrajectory(data.task_id, withSilent())
            trajectory.value = trajData.steps || []
          } catch {
            trajectory.value = []
          }
        }
        setTimeout(initRadarChart, 100)
      }
    } catch {
      // 忽略轮询中的临时错误
    }
  }, 5000)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// Handle resize
const handleResize = () => {
  radarInstance?.resize()
}

// Lifecycle
onMounted(() => {
  fetchData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  radarInstance?.dispose()
  stopPolling()
})

watch(selectedDimension, () => {
  // Update radar chart highlight if needed
})
</script>

<style scoped lang="scss">
.evaluation-detail {
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
  }

  .overall-card {
    margin-bottom: 20px;

    .overall-content {
      display: flex;
      align-items: center;
      gap: 40px;

      .score-circle {
        flex-shrink: 0;

        .score-text {
          display: flex;
          flex-direction: column;
          align-items: center;

          .score-value {
            font-size: 36px;
            font-weight: 600;
            color: var(--text-color);
          }

          .score-label {
            font-size: 14px;
            color: var(--text-color-secondary);
          }
        }
      }

      .score-summary {
        flex: 1;

        h3 {
          margin: 0 0 16px 0;
          font-size: 16px;
          color: var(--text-color);
        }

        .recommendations {
          h4 {
            margin: 0 0 8px 0;
            font-size: 14px;
            color: var(--text-color-secondary);
          }

          ul {
            margin: 0;
            padding-left: 20px;

            li {
              margin-bottom: 8px;
              color: var(--text-color);
            }
          }
        }
      }
    }
  }

  .dimension-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
    margin-bottom: 20px;
  }

  .dimension-card {
    height: 100%;

    .dimension-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;

      .dimension-icon {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .dimension-title {
        flex: 1;

        h4 {
          margin: 0;
          font-size: 16px;
        }

        .dimension-score {
          font-size: 24px;
          font-weight: 600;
        }
      }
    }

    .dimension-detail {
      margin-bottom: 16px;

      .metric-item {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;

        .metric-name {
          width: 80px;
          font-size: 12px;
          color: var(--text-color-secondary);
        }

        .el-progress {
          flex: 1;
        }

        .metric-value {
          width: 30px;
          text-align: right;
          font-size: 12px;
          font-weight: 600;
        }
      }
    }

    .dimension-feedback {
      p {
        margin: 0;
        font-size: 13px;
        color: var(--text-color-secondary);
        line-height: 1.6;
      }
    }
  }

  .analysis-card {
    margin-bottom: 20px;

    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .analysis-content {
      display: flex;
      gap: 24px;

      .chart-section {
        flex: 1;

        .chart-container {
          height: 300px;
        }
      }

      .feedback-section {
        flex: 1;

        h4 {
          margin: 0 0 12px 0;
          font-size: 14px;
          color: var(--text-color);
        }

        .feedback-content {
          background: var(--bg-color);
          padding: 16px;
          border-radius: 8px;
          margin-bottom: 16px;
          font-size: 14px;
          line-height: 1.6;
        }

        .issues-list,
        .suggestions-list {
          margin: 0 0 16px 0;
          padding: 0;
          list-style: none;

          li {
            display: flex;
            align-items: flex-start;
            gap: 8px;
            margin-bottom: 8px;
            font-size: 14px;
          }
        }
      }
    }
  }

  .trajectory-card {
    .timeline {
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
  }
}

.consensus-card {
  margin-top: 20px;
  .consensus-chart {
    width: 100%;
    height: 200px;
  }
  .consensus-info {
    .model-score-row {
      display: flex;
      align-items: center;
      margin-bottom: 8px;
      .model-name {
        width: 100px;
        font-size: 13px;
        color: #606266;
      }
      .model-score {
        width: 40px;
        text-align: right;
        font-weight: 600;
        font-size: 14px;
      }
    }
  }
}
</style>
