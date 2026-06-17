<template>
  <div class="analytics-page">
    <!-- Header -->
    <div class="page-header">
      <h2>数据分析</h2>
      <el-radio-group v-model="timeRange" size="default">
        <el-radio-button label="week">本周</el-radio-button>
        <el-radio-button label="month">本月</el-radio-button>
        <el-radio-button label="quarter">本季度</el-radio-button>
        <el-radio-button label="all">全部</el-radio-button>
      </el-radio-group>
    </div>

    <!-- Summary Stats -->
    <el-row :gutter="20" class="summary-row">
      <el-col :span="6">
        <el-card class="summary-card" shadow="hover">
          <div class="summary-icon" style="background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%)">
            <el-icon :size="32" color="#fff"><DataAnalysis /></el-icon>
          </div>
          <div class="summary-content">
            <div class="summary-value">{{ summaryData.total_evaluations || 0 }}</div>
            <div class="summary-label">总评估数</div>
            <div class="summary-trend" :class="trendClass">
              <el-icon><Top v-if="trend > 0" /><Bottom v-else /></el-icon>
              {{ Math.abs(trend) }}%
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="summary-card" shadow="hover">
          <div class="summary-icon" style="background: linear-gradient(135deg, #67c23a 0%, #85ce61 100%)">
            <el-icon :size="32" color="#fff"><TrendCharts /></el-icon>
          </div>
          <div class="summary-content">
            <div class="summary-value">{{ averageScore }}</div>
            <div class="summary-label">平均得分</div>
            <div class="summary-trend positive">
              <el-icon><Top /></el-icon>
              5.2%
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="summary-card" shadow="hover">
          <div class="summary-icon" style="background: linear-gradient(135deg, #e6a23c 0%, #ebb563 100%)">
            <el-icon :size="32" color="#fff"><Trophy /></el-icon>
          </div>
          <div class="summary-content">
            <div class="summary-value">{{ bestDimension }}</div>
            <div class="summary-label">最强维度</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="summary-card" shadow="hover">
          <div class="summary-icon" style="background: linear-gradient(135deg, #f56c6c 0%, #f89898 100%)">
            <el-icon :size="32" color="#fff"><Warning /></el-icon>
          </div>
          <div class="summary-content">
            <div class="summary-value">{{ worstDimension }}</div>
            <div class="summary-label">待改进维度</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Charts Row 1 -->
    <el-row :gutter="20" class="chart-row">
      <!-- Score Distribution -->
      <el-col :span="12">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>得分分布</span>
              <el-tooltip content="各分数段的评估数量分布">
                <el-icon><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
          </template>
          <div ref="distributionChart" class="chart-container"></div>
        </el-card>
      </el-col>

      <!-- Dimension Comparison -->
      <el-col :span="12">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>维度对比趋势</span>
              <el-select v-model="selectedDimensions" multiple collapse-tags placeholder="选择维度" size="small" style="width: 200px">
                <el-option v-for="dim in allDimensions" :key="dim.key" :label="dim.name" :value="dim.key" />
              </el-select>
            </div>
          </template>
          <div ref="dimensionTrendChart" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Charts Row 2 -->
    <el-row :gutter="20" class="chart-row">
      <!-- Correlation Matrix -->
      <el-col :span="12">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>维度相关性分析</span>
              <el-tooltip content="各维度得分之间的相关性">
                <el-icon><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
          </template>
          <div ref="correlationChart" class="chart-container"></div>
        </el-card>
      </el-col>

      <!-- Performance Heatmap -->
      <el-col :span="12">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>性能热力图</span>
              <el-radio-group v-model="heatmapMetric" size="small">
                <el-radio-button label="score">得分</el-radio-button>
                <el-radio-button label="count">数量</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div ref="heatmapChart" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Insights Section -->
    <el-card class="insights-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>智能洞察</span>
          <el-tag type="success">AI 分析</el-tag>
        </div>
      </template>

      <el-row :gutter="20">
        <el-col :span="8" v-for="insight in insights" :key="insight.title">
          <div class="insight-item" :style="{ borderLeft: `4px solid ${insight.color}` }">
            <div class="insight-icon" :style="{ background: insight.bgColor }">
              <el-icon :size="20" :color="insight.color">
                <component :is="insight.icon" />
              </el-icon>
            </div>
            <div class="insight-content">
              <h4>{{ insight.title }}</h4>
              <p>{{ insight.description }}</p>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- Recommendations -->
    <el-card class="recommendations-card" shadow="hover">
      <template #header>
        <span>改进建议</span>
      </template>

      <div class="recommendations-list">
        <div v-for="(rec, index) in recommendations" :key="index" class="recommendation-item">
          <div class="rec-number">{{ index + 1 }}</div>
          <div class="rec-content">
            <h4>{{ rec.title }}</h4>
            <p>{{ rec.description }}</p>
            <div class="rec-tags">
              <el-tag v-for="tag in rec.tags" :key="tag" size="small" type="info">{{ tag }}</el-tag>
            </div>
          </div>
          <div class="rec-impact">
            <span class="impact-label">预期提升</span>
            <span class="impact-value" :style="{ color: rec.impactColor }">+{{ rec.impact }}%</span>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import { DataAnalysis, TrendCharts, Trophy, Warning, Top, Bottom, InfoFilled, CircleCheck, Star, Aim } from '@element-plus/icons-vue'
import { reportApi } from '@/api'

// State
const timeRange = ref('month')
const selectedDimensions = ref(['planning', 'tactical', 'tool_use', 'memory', 'replan'])
const heatmapMetric = ref('score')
const summaryData = ref<any>({})

// Chart refs
const distributionChart = ref<HTMLElement>()
const dimensionTrendChart = ref<HTMLElement>()
const correlationChart = ref<HTMLElement>()
const heatmapChart = ref<HTMLElement>()

// Chart instances
let distributionInstance: echarts.ECharts | null = null
let dimensionTrendInstance: echarts.ECharts | null = null
let correlationInstance: echarts.ECharts | null = null
let heatmapInstance: echarts.ECharts | null = null

// Dimensions config
const allDimensions = [
  { key: 'planning', name: '规划质量', color: '#409eff' },
  { key: 'tactical', name: '战术决策', color: '#67c23a' },
  { key: 'tool_use', name: '工具使用', color: '#e6a23c' },
  { key: 'memory', name: '记忆保持', color: '#f56c6c' },
  { key: 'replan', name: '重规划', color: '#909399' },
]

// Computed
const trend = computed(() => 12.5) // Mock trend
const trendClass = computed(() => trend.value > 0 ? 'positive' : 'negative')

const averageScore = computed(() => {
  const scores = summaryData.value?.average_scores || {}
  const values = Object.values(scores).filter(v => typeof v === 'number') as number[]
  return values.length ? Math.round(values.reduce((a, b) => a + b, 0) / values.length) : 0
})

const bestDimension = computed(() => {
  const scores = summaryData.value?.average_scores || {}
  let best = { key: '', score: 0 }
  for (const [key, score] of Object.entries(scores)) {
    if (typeof score === 'number' && score > best.score) {
      best = { key, score }
    }
  }
  const dim = allDimensions.find(d => d.key === best.key)
  return dim?.name || '-'
})

const worstDimension = computed(() => {
  const scores = summaryData.value?.average_scores || {}
  let worst = { key: '', score: 100 }
  for (const [key, score] of Object.entries(scores)) {
    if (typeof score === 'number' && score < worst.score) {
      worst = { key, score }
    }
  }
  const dim = allDimensions.find(d => d.key === worst.key)
  return dim?.name || '-'
})

// Insights
const insights = ref([
  {
    title: '规划能力提升',
    description: '最近一周规划质量得分提升了15%，建议继续保持',
    icon: 'TrendCharts',
    color: '#67c23a',
    bgColor: 'rgba(103, 194, 58, 0.1)',
  },
  {
    title: '记忆保持问题',
    description: '记忆保持维度得分较低，建议优化Agent的记忆管理策略',
    icon: 'Warning',
    color: '#e6a23c',
    bgColor: 'rgba(230, 162, 60, 0.1)',
  },
  {
    title: '工具使用优化',
    description: '工具选择准确率提高了8%，参数准确性仍需改进',
    icon: 'Aim',
    color: '#409eff',
    bgColor: 'rgba(64, 158, 255, 0.1)',
  },
])

// Recommendations
const recommendations = ref([
  {
    title: '增强记忆管理',
    description: '建议实现显式的事实跟踪机制，在关键步骤后验证Agent是否记住了重要信息',
    tags: ['记忆', '核心改进'],
    impact: 15,
    impactColor: '#67c23a',
  },
  {
    title: '优化重规划触发',
    description: '当前重规划触发过于保守，建议在连续3次失败后主动触发重规划',
    tags: ['重规划', '策略优化'],
    impact: 10,
    impactColor: '#409eff',
  },
  {
    title: '改进工具参数验证',
    description: '添加工具调用前的参数验证步骤，减少因参数错误导致的失败',
    tags: ['工具使用', '错误预防'],
    impact: 8,
    impactColor: '#e6a23c',
  },
])

// Initialize charts
const initDistributionChart = () => {
  if (!distributionChart.value) return

  distributionInstance = echarts.init(distributionChart.value)

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
      data: ['0-20', '20-40', '40-60', '60-80', '80-100'],
    },
    yAxis: {
      type: 'value',
      name: '评估数量',
    },
    series: [
      {
        type: 'bar',
        barWidth: '60%',
        data: [
          { value: 5, itemStyle: { color: '#f56c6c' } },
          { value: 12, itemStyle: { color: '#e6a23c' } },
          { value: 28, itemStyle: { color: '#409eff' } },
          { value: 45, itemStyle: { color: '#67c23a' } },
          { value: 30, itemStyle: { color: '#67c23a' } },
        ],
        label: {
          show: true,
          position: 'top',
        },
      },
    ],
  }

  distributionInstance.setOption(option)
}

const initDimensionTrendChart = () => {
  if (!dimensionTrendChart.value) return

  dimensionTrendInstance = echarts.init(dimensionTrendChart.value)

  const dates = Array.from({ length: 7 }, (_, i) =>
    new Date(Date.now() - (6 - i) * 24 * 60 * 60 * 1000).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
  )

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
    },
    legend: {
      data: selectedDimensions.value.map(key => allDimensions.find(d => d.key === key)?.name || key),
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
      data: dates,
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
    },
    series: selectedDimensions.value.map(key => {
      const dim = allDimensions.find(d => d.key === key)
      return {
        name: dim?.name || key,
        type: 'line',
        smooth: true,
        data: dates.map(() => Math.floor(Math.random() * 30) + 60),
        itemStyle: { color: dim?.color },
      }
    }),
  }

  dimensionTrendInstance.setOption(option)
}

const initCorrelationChart = () => {
  if (!correlationChart.value) return

  correlationInstance = echarts.init(correlationChart.value)

  // Mock correlation data
  const data = []
  for (let i = 0; i < 5; i++) {
    for (let j = 0; j < 5; j++) {
      data.push([i, j, Math.random().toFixed(2)])
    }
  }

  const option: echarts.EChartsOption = {
    tooltip: {
      position: 'top',
      formatter: (params: any) => {
        const [x, y, value] = params.data
        return `${allDimensions[x].name} vs ${allDimensions[y].name}: ${value}`
      },
    },
    grid: {
      left: '15%',
      right: '10%',
      top: '10%',
      bottom: '15%',
    },
    xAxis: {
      type: 'category',
      data: allDimensions.map(d => d.name),
      axisLabel: { rotate: 45 },
    },
    yAxis: {
      type: 'category',
      data: allDimensions.map(d => d.name),
    },
    visualMap: {
      min: 0,
      max: 1,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: '0%',
      inRange: {
        color: ['#f5f5f5', '#409eff'],
      },
    },
    series: [
      {
        type: 'heatmap',
        data: data,
        label: {
          show: true,
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.5)',
          },
        },
      },
    ],
  }

  correlationInstance.setOption(option)
}

const initHeatmapChart = () => {
  if (!heatmapChart.value) return

  heatmapInstance = echarts.init(heatmapChart.value)

  // Mock heatmap data - dimensions vs time
  const hours = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  const dims = allDimensions.map(d => d.name)

  const data: [number, number, number][] = []
  for (let i = 0; i < dims.length; i++) {
    for (let j = 0; j < hours.length; j++) {
      data.push([j, i, Math.floor(Math.random() * 40) + 60])
    }
  }

  const option: echarts.EChartsOption = {
    tooltip: {
      position: 'top',
      formatter: (params: any) => {
        const [x, y, value] = params.data
        return `${hours[x]} ${dims[y]}: ${value}`
      },
    },
    grid: {
      left: '15%',
      right: '10%',
      top: '5%',
      bottom: '15%',
    },
    xAxis: {
      type: 'category',
      data: hours,
      splitArea: { show: true },
    },
    yAxis: {
      type: 'category',
      data: dims,
      splitArea: { show: true },
    },
    visualMap: {
      min: 50,
      max: 100,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: '0%',
      inRange: {
        color: ['#f56c6c', '#e6a23c', '#67c23a'],
      },
    },
    series: [
      {
        type: 'heatmap',
        data: data,
        label: {
          show: true,
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.5)',
          },
        },
      },
    ],
  }

  heatmapInstance.setOption(option)
}

// Fetch data
const fetchData = async () => {
  try {
    const summary = await reportApi.getSummary()
    summaryData.value = summary

    setTimeout(() => {
      initDistributionChart()
      initDimensionTrendChart()
      initCorrelationChart()
      initHeatmapChart()
    }, 100)
  } catch (error) {
    console.error('Failed to fetch data:', error)
  }
}

// Handle resize
const handleResize = () => {
  distributionInstance?.resize()
  dimensionTrendInstance?.resize()
  correlationInstance?.resize()
  heatmapInstance?.resize()
}

// Lifecycle
onMounted(() => {
  fetchData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  distributionInstance?.dispose()
  dimensionTrendInstance?.dispose()
  correlationInstance?.dispose()
  heatmapInstance?.dispose()
})

watch(timeRange, fetchData)
watch(selectedDimensions, initDimensionTrendChart)
watch(heatmapMetric, initHeatmapChart)
</script>

<style scoped lang="scss">
.analytics-page {
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;

    h2 {
      margin: 0;
    }
  }

  .summary-row {
    margin-bottom: 20px;
  }

  .summary-card {
    :deep(.el-card__body) {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .summary-icon {
      width: 64px;
      height: 64px;
      border-radius: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .summary-content {
      flex: 1;

      .summary-value {
        font-size: 28px;
        font-weight: 600;
        color: var(--text-color);
      }

      .summary-label {
        font-size: 14px;
        color: var(--text-color-secondary);
        margin-top: 4px;
      }

      .summary-trend {
        font-size: 12px;
        display: flex;
        align-items: center;
        gap: 4px;
        margin-top: 4px;

        &.positive {
          color: #67c23a;
        }

        &.negative {
          color: #f56c6c;
        }
      }
    }
  }

  .chart-row {
    margin-bottom: 20px;
  }

  .chart-card {
    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
  }

  .chart-container {
    height: 300px;
  }

  .insights-card {
    margin-bottom: 20px;

    .insight-item {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 16px;
      background: var(--bg-color);
      border-radius: 8px;

      .insight-icon {
        width: 40px;
        height: 40px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }

      .insight-content {
        flex: 1;

        h4 {
          margin: 0 0 8px 0;
          font-size: 14px;
        }

        p {
          margin: 0;
          font-size: 13px;
          color: var(--text-color-secondary);
          line-height: 1.5;
        }
      }
    }
  }

  .recommendations-card {
    .recommendations-list {
      .recommendation-item {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 16px 0;
        border-bottom: 1px solid var(--border-color);

        &:last-child {
          border-bottom: none;
        }

        .rec-number {
          width: 32px;
          height: 32px;
          border-radius: 50%;
          background: var(--primary-color);
          color: #fff;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 600;
          flex-shrink: 0;
        }

        .rec-content {
          flex: 1;

          h4 {
            margin: 0 0 8px 0;
            font-size: 14px;
          }

          p {
            margin: 0 0 8px 0;
            font-size: 13px;
            color: var(--text-color-secondary);
          }

          .rec-tags {
            display: flex;
            gap: 8px;
          }
        }

        .rec-impact {
          text-align: center;
          flex-shrink: 0;

          .impact-label {
            display: block;
            font-size: 12px;
            color: var(--text-color-secondary);
            margin-bottom: 4px;
          }

          .impact-value {
            font-size: 20px;
            font-weight: 600;
          }
        }
      }
    }
  }
}
</style>
