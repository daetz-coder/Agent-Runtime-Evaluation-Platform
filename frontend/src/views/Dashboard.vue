<template>
  <div class="dashboard">
    <el-alert
      v-if="!hasEvaluationData"
      title="欢迎使用 Agent 评估平台"
      description="在「任务管理」中创建任务、上传轨迹并运行评估，Dashboard 将展示真实统计数据。"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 20px"
    />

    <!-- Stats Cards -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6" v-for="stat in statsCards" :key="stat.title">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon" :style="{ background: stat.bgColor }">
            <el-icon :size="28" :color="stat.color">
              <component :is="stat.icon" />
            </el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stat.value }}</div>
            <div class="stat-title">{{ stat.title }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Cost Summary -->
    <el-row :gutter="20" class="cost-row" v-if="costSummary.evalCount > 0">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <span>成本追踪</span>
            <el-tag size="small" style="margin-left: 8px">预估 · DeepSeek 定价</el-tag>
          </template>
          <el-row :gutter="16">
            <el-col :span="6">
              <el-statistic title="评估总数" :value="costSummary.evalCount" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="预估 Token" :value="costSummary.estTokens.toLocaleString()" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="DeepSeek 费用" :value="'¥' + costSummary.estCostDeepSeek" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="对比 GPT-4o 节省" :value="'¥' + costSummary.savings">
                <template #suffix>
                  <el-tag type="success" size="small">预估</el-tag>
                </template>
              </el-statistic>
            </el-col>
          </el-row>
        </el-card>
      </el-col>
    </el-row>

    <!-- Charts Row -->
    <el-row :gutter="20" class="chart-row">
      <!-- Radar Chart - Overall Performance -->
      <el-col :span="12">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>综合能力雷达图</span>
              <el-tag v-if="hasEvaluationData" type="success" size="small">已评估 {{ summaryData?.total_evaluations || 0 }} 次</el-tag>
            </div>
          </template>
          <div ref="radarChart" class="chart-container"></div>
        </el-card>
      </el-col>

      <!-- Line Chart - Score Trends -->
      <el-col :span="12">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>评分趋势分析</span>
              <el-radio-group v-model="trendPeriod" size="small">
                <el-radio-button label="week">本周</el-radio-button>
                <el-radio-button label="month">本月</el-radio-button>
                <el-radio-button label="all">全部</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div ref="lineChart" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Second Row -->
    <el-row :gutter="20" class="chart-row">
      <!-- Bar Chart - Dimension Comparison -->
      <el-col :span="12">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>维度对比分析</span>
              <el-tooltip content="各维度平均得分对比">
                <el-icon><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
          </template>
          <div ref="barChart" class="chart-container"></div>
        </el-card>
      </el-col>

      <!-- Gauge Charts -->
      <el-col :span="12">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>维度详细得分</span>
            </div>
          </template>
          <div class="gauge-grid">
            <div v-for="dim in dimensions" :key="dim.key" ref="gaugeCharts" class="gauge-item"></div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Third Row - Recent Tasks & Issues -->
    <el-row :gutter="20" class="chart-row">
      <!-- Recent Tasks -->
      <el-col :span="12">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>最近任务</span>
              <el-button type="primary" link @click="router.push('/tasks')">查看全部</el-button>
            </div>
          </template>
          <div class="task-list">
            <div v-for="task in recentTasks" :key="task.id" class="task-item" @click="router.push(`/tasks/${task.id}`)">
              <div class="task-info">
                <div class="task-goal">{{ task.goal }}</div>
                <div class="task-time">{{ formatTime(task.created_at) }}</div>
              </div>
              <el-tag :type="getStatusType(task.status)" size="small">
                {{ getStatusText(task.status) }}
              </el-tag>
            </div>
            <el-empty v-if="!recentTasks.length" description="暂无任务" :image-size="60" />
          </div>
        </el-card>
      </el-col>

      <!-- Top Issues -->
      <el-col :span="12">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>主要问题</span>
              <el-tag type="warning" size="small">{{ topIssues.length }} 个问题</el-tag>
            </div>
          </template>
          <div class="issues-list">
            <div v-for="(issue, index) in topIssues" :key="index" class="issue-item">
              <div class="issue-index">{{ index + 1 }}</div>
              <div class="issue-text">{{ issue }}</div>
            </div>
            <el-empty v-if="!topIssues.length" description="暂无问题" :image-size="60" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { reportApi, taskApi } from '@/api'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'
import {
  REPORT_DIMENSIONS,
  chartEmptyOption,
  filterTrendsByRange,
} from '@/utils/reportCharts'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

const router = useRouter()

// Chart refs
const radarChart = ref<HTMLElement>()
const lineChart = ref<HTMLElement>()
const barChart = ref<HTMLElement>()
const gaugeCharts = ref<HTMLElement[]>([])

// Chart instances
let radarInstance: echarts.ECharts | null = null
let lineInstance: echarts.ECharts | null = null
let barInstance: echarts.ECharts | null = null
let gaugeInstances: echarts.ECharts[] = []

// Data
const trendPeriod = ref('week')
const summaryData = ref<any>(null)
const dashboardData = ref<any>(null)
const recentTasks = ref<any[]>([])
const trendData = ref<any[]>([])
const costSummary = ref({ evalCount: 0, estTokens: 0, estCostDeepSeek: 0, estCostGPT4: 0, savings: 0 })

// Dimensions config
const dimensions = REPORT_DIMENSIONS

const hasEvaluationData = computed(() => (summaryData.value?.total_evaluations || 0) > 0)

const filteredTrends = computed(() => {
  const range = trendPeriod.value === 'week' ? 'week' : trendPeriod.value === 'month' ? 'month' : 'all'
  return filterTrendsByRange(trendData.value, range)
})

// Computed
const statsCards = computed(() => [
  {
    title: '总评估数',
    value: summaryData.value?.total_evaluations || 0,
    icon: 'DataAnalysis',
    color: '#409eff',
    bgColor: 'rgba(64, 158, 255, 0.1)',
  },
  {
    title: '平均得分',
    value: (summaryData.value?.average_scores?.overall || 0).toFixed(1),
    icon: 'TrendCharts',
    color: '#67c23a',
    bgColor: 'rgba(103, 194, 58, 0.1)',
  },
  {
    title: '任务总数',
    value: dashboardData.value?.total_tasks ?? 0,
    icon: 'Document',
    color: '#e6a23c',
    bgColor: 'rgba(230, 162, 60, 0.1)',
  },
  {
    title: '问题数量',
    value: topIssues.value.length,
    icon: 'Warning',
    color: '#f56c6c',
    bgColor: 'rgba(245, 108, 108, 0.1)',
  },
])

const topIssues = computed(() => {
  return summaryData.value?.top_issues || []
})

// Methods
const formatTime = (time: string) => {
  if (!time) return ''
  const d = time.endsWith('Z') || time.includes('+') ? time : time + 'Z'
  return dayjs(d).fromNow()
}

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

// Initialize charts
const initRadarChart = () => {
  if (!radarChart.value) return

  radarInstance = echarts.init(radarChart.value)
  const avgScores = summaryData.value?.average_scores || {}

  if (!hasEvaluationData.value) {
    radarInstance.setOption(chartEmptyOption())
    return
  }

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
      splitLine: {
        lineStyle: {
          color: '#e8e8e8',
        },
      },
      splitArea: {
        show: true,
        areaStyle: {
          color: ['rgba(64, 158, 255, 0.05)', 'rgba(64, 158, 255, 0.1)'],
        },
      },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: dimensions.map(d => avgScores[d.key] || 0),
            name: '平均得分',
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

const initLineChart = () => {
  if (!lineChart.value) return

  lineInstance = echarts.init(lineChart.value)

  const tData = filteredTrends.value
  if (!tData.length) {
    lineInstance.setOption(chartEmptyOption())
    return
  }

  const dates = tData.map((t: any) => dayjs(t.date).format('MM/DD'))

  const seriesData = REPORT_DIMENSIONS.map(d => ({
    name: d.name,
    type: 'line' as const,
    smooth: true,
    data: tData.map((t: any) => t[d.trendKey] || 0),
    itemStyle: { color: d.color },
    lineStyle: { width: 2 },
  }))

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
    },
    legend: {
      data: dimensions.map(d => d.name),
      bottom: 0,
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '5%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates,
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: {
        formatter: '{value}',
      },
    },
    series: seriesData,
  }

  lineInstance.setOption(option)
}

const initBarChart = () => {
  if (!barChart.value) return

  barInstance = echarts.init(barChart.value)
  const avgScores = summaryData.value?.average_scores || {}

  if (!hasEvaluationData.value) {
    barInstance.setOption(chartEmptyOption())
    return
  }

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow',
      },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '8%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: dimensions.map(d => d.name),
      axisLabel: {
        color: '#666',
      },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: {
        formatter: '{value}',
      },
    },
    series: [
      {
        type: 'bar',
        barWidth: '40%',
        data: dimensions.map(d => ({
          value: avgScores[d.key] || 0,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: d.color },
              { offset: 1, color: d.color + '80' },
            ]),
            borderRadius: [4, 4, 0, 0],
          },
        })),
        label: {
          show: true,
          position: 'top',
          formatter: '{c}',
          color: '#666',
        },
      },
    ],
  }

  barInstance.setOption(option)
}

const initGaugeCharts = () => {
  gaugeInstances.forEach(instance => instance.dispose())
  gaugeInstances = []

  const avgScores = summaryData.value?.average_scores || {}

  gaugeCharts.value.forEach((el, index) => {
    if (!el) return

    const dim = dimensions[index]
    const score = avgScores[dim.key] || 0

    const instance = echarts.init(el)
    gaugeInstances.push(instance)

    const option: echarts.EChartsOption = {
      series: [
        {
          type: 'gauge',
          startAngle: 200,
          endAngle: -20,
          min: 0,
          max: 100,
          splitNumber: 10,
          axisLine: {
            lineStyle: {
              width: 12,
              color: [
                [0.3, '#f56c6c'],
                [0.7, '#e6a23c'],
                [1, '#67c23a'],
              ],
            },
          },
          pointer: {
            itemStyle: {
              color: 'auto',
            },
          },
          axisTick: {
            distance: -12,
            length: 4,
            lineStyle: {
              color: '#fff',
              width: 1,
            },
          },
          splitLine: {
            distance: -14,
            length: 8,
            lineStyle: {
              color: '#fff',
              width: 2,
            },
          },
          axisLabel: {
            color: 'inherit',
            distance: 20,
            fontSize: 10,
          },
          detail: {
            valueAnimation: true,
            formatter: '{value}',
            color: 'inherit',
            fontSize: 16,
            offsetCenter: [0, '70%'],
          },
          title: {
            offsetCenter: [0, '90%'],
            fontSize: 12,
            color: '#666',
          },
          data: [
            {
              value: score,
              name: dim.name,
            },
          ],
        },
      ],
    }

    instance.setOption(option)
  })
}

// Fetch data
const fetchData = async () => {
  try {
    const [summary, dashboard, trends] = await Promise.all([
      reportApi.getSummary(),
      taskApi.getDashboard(),
      reportApi.getTrends(),
    ])
    summaryData.value = summary
    dashboardData.value = dashboard
    recentTasks.value = dashboard.recent_tasks || []
    trendData.value = trends || []

    // 成本估算（DeepSeek 定价: ¥1/百万tokens input, ¥2/百万tokens output）
    const evalCount = summary?.total_evaluations || 0
    const avgTokensPerEval = 11750 / 6  // 约 2000 tokens/评估维度
    const estTokens = evalCount * avgTokensPerEval * 6  // 6维度
    const estCostDeepSeek = (estTokens / 1_000_000 * 1.0).toFixed(4)
    const estCostGPT4 = (estTokens / 1_000_000 * 30.0).toFixed(2)
    costSummary.value = {
      evalCount,
      estTokens,
      estCostDeepSeek: parseFloat(estCostDeepSeek),
      estCostGPT4: parseFloat(estCostGPT4),
      savings: parseFloat((parseFloat(estCostGPT4) - parseFloat(estCostDeepSeek)).toFixed(2)),
    }

    requestAnimationFrame(() => {
      initRadarChart()
      initLineChart()
      initBarChart()
      initGaugeCharts()
    })
  } catch (error) {
    console.error('Failed to fetch data:', error)
  }
}

// Handle resize
const handleResize = () => {
  radarInstance?.resize()
  lineInstance?.resize()
  barInstance?.resize()
  gaugeInstances.forEach(instance => instance.resize())
}

// Lifecycle
onMounted(() => {
  fetchData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  radarInstance?.dispose()
  lineInstance?.dispose()
  barInstance?.dispose()
  gaugeInstances.forEach(instance => instance.dispose())
})

// Watch for period change
watch(trendPeriod, () => {
  initLineChart()
})
</script>

<style scoped lang="scss">
.dashboard {
  .stats-row {
    margin-bottom: 20px;
  }

  .stat-card {
    :deep(.el-card__body) {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 20px;
    }

    .stat-icon {
      width: 56px;
      height: 56px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .stat-content {
      .stat-value {
        font-size: 28px;
        font-weight: 600;
        color: var(--text-color);
        line-height: 1.2;
      }

      .stat-title {
        font-size: 14px;
        color: var(--text-color-secondary);
        margin-top: 4px;
      }
    }
  }

  .chart-row {
    margin-bottom: 20px;
  }

  .chart-card {
    height: 100%;

    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
  }

  .chart-container {
    height: 300px;
  }

  .gauge-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    height: 300px;

    .gauge-item {
      height: 100%;
    }
  }

  .task-list {
    max-height: 300px;
    overflow-y: auto;

    .task-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 0;
      border-bottom: 1px solid var(--border-color);
      cursor: pointer;
      transition: background 0.2s;

      &:hover {
        background: rgba(64, 158, 255, 0.05);
      }

      &:last-child {
        border-bottom: none;
      }

      .task-info {
        flex: 1;
        min-width: 0;

        .task-goal {
          font-size: 14px;
          color: var(--text-color);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .task-time {
          font-size: 12px;
          color: var(--text-color-secondary);
          margin-top: 4px;
        }
      }
    }
  }

  .issues-list {
    max-height: 300px;
    overflow-y: auto;

    .issue-item {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 12px 0;
      border-bottom: 1px solid var(--border-color);

      &:last-child {
        border-bottom: none;
      }

      .issue-index {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        background: var(--warning-color);
        color: #fff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 12px;
        font-weight: 600;
        flex-shrink: 0;
      }

      .issue-text {
        font-size: 14px;
        color: var(--text-color);
        line-height: 1.5;
      }
    }
  }
}
</style>
