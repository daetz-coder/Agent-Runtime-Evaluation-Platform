<template>
  <div class="dashboard">
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

    <!-- Charts Row -->
    <el-row :gutter="20" class="chart-row">
      <!-- Radar Chart - Overall Performance -->
      <el-col :span="12">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>综合能力雷达图</span>
              <el-tag type="success" size="small">实时数据</el-tag>
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
import { DataAnalysis, Document, TrendCharts, Warning } from '@element-plus/icons-vue'
import { reportApi, taskApi } from '@/api'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'

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
const recentTasks = ref<any[]>([])

// Dimensions config
const dimensions = [
  { key: 'planning', name: '规划质量', color: '#409eff' },
  { key: 'tactical', name: '战术决策', color: '#67c23a' },
  { key: 'tool_use', name: '工具使用', color: '#e6a23c' },
  { key: 'memory', name: '记忆保持', color: '#f56c6c' },
  { key: 'replan', name: '重规划', color: '#909399' },
]

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
    value: recentTasks.value.length,
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
  return dayjs(time).fromNow()
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

  // Mock data for trends
  const dates = Array.from({ length: 7 }, (_, i) =>
    dayjs().subtract(6 - i, 'day').format('MM/DD')
  )

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
    series: dimensions.map(d => ({
      name: d.name,
      type: 'line',
      smooth: true,
      data: dates.map(() => Math.floor(Math.random() * 40) + 60),
      itemStyle: {
        color: d.color,
      },
      lineStyle: {
        width: 2,
      },
    })),
  }

  lineInstance.setOption(option)
}

const initBarChart = () => {
  if (!barChart.value) return

  barInstance = echarts.init(barChart.value)
  const avgScores = summaryData.value?.average_scores || {}

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
    // Fetch summary
    const summary = await reportApi.getSummary()
    summaryData.value = summary

    // Fetch recent tasks
    const tasks = await taskApi.list({ limit: 5 })
    recentTasks.value = tasks

    // Initialize charts after data loaded
    setTimeout(() => {
      initRadarChart()
      initLineChart()
      initBarChart()
      initGaugeCharts()
    }, 100)
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
