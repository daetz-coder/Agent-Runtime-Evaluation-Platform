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

    <el-alert
      v-if="!hasEvaluationData"
      title="暂无评估数据"
      description="创建任务并运行评估后，此处将展示真实统计与趋势分析。"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 20px"
    />

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
            <div v-if="periodEvalCount !== null" class="summary-trend neutral">
              本周期 {{ periodEvalCount }} 次
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
            <div class="summary-value">{{ overallAverageScore }}</div>
            <div class="summary-label">综合均分</div>
            <div v-if="scoreTrend !== null" class="summary-trend" :class="scoreTrend >= 0 ? 'positive' : 'negative'">
              <el-icon><Top v-if="scoreTrend >= 0" /><Bottom v-else /></el-icon>
              {{ Math.abs(scoreTrend) }}%
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
              <span>维度 × 日期</span>
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
          <span>数据洞察</span>
          <el-tag type="info">基于评估汇总</el-tag>
        </div>
      </template>

      <el-empty v-if="displayInsights.length === 0" description="完成评估后将自动生成问题洞察" />
      <el-row v-else :gutter="20">
        <el-col :span="8" v-for="insight in displayInsights" :key="insight.title">
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

      <el-empty v-if="displayRecommendations.length === 0" description="暂无改进建议" />
      <div v-else class="recommendations-list">
        <div v-for="(rec, index) in displayRecommendations" :key="index" class="recommendation-item">
          <div class="rec-number">{{ index + 1 }}</div>
          <div class="rec-content">
            <p>{{ rec.description }}</p>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import { DataAnalysis, TrendCharts, Trophy, Warning, Top, Bottom, InfoFilled } from '@element-plus/icons-vue'
import { reportApi } from '@/api'
import {
  REPORT_DIMENSIONS,
  bucketScores,
  chartEmptyOption,
  filterTrendsByRange,
  pearsonCorrelation,
  trendDeltaPercent,
} from '@/utils/reportCharts'

// State
const timeRange = ref('month')
const selectedDimensions = ref(['planning', 'tactical', 'tool_use', 'memory', 'replan', 'retrieval'])
const heatmapMetric = ref('score')
const summaryData = ref<any>({})
const trendData = ref<any[]>([])

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

const allDimensions = REPORT_DIMENSIONS

const filteredTrends = computed(() => filterTrendsByRange(trendData.value, timeRange.value))

const hasEvaluationData = computed(() => (summaryData.value?.total_evaluations || 0) > 0)

const overallAverageScore = computed(() => {
  const score = summaryData.value?.average_scores?.overall
  return typeof score === 'number' ? Math.round(score) : 0
})

const scoreTrend = computed(() => trendDeltaPercent(filteredTrends.value, 'avg_overall'))

const periodEvalCount = computed(() => {
  if (!filteredTrends.value.length) return null
  return filteredTrends.value.reduce((sum, row) => sum + (row.count || 0), 0)
})

const bestDimension = computed(() => {
  const scores = summaryData.value?.average_scores || {}
  let best = { key: '', score: -1 }
  for (const dim of allDimensions) {
    const score = scores[dim.key]
    if (typeof score === 'number' && score > best.score) {
      best = { key: dim.key, score }
    }
  }
  return allDimensions.find((d) => d.key === best.key)?.name || '-'
})

const worstDimension = computed(() => {
  const scores = summaryData.value?.average_scores || {}
  let worst = { key: '', score: 101 }
  for (const dim of allDimensions) {
    const score = scores[dim.key]
    if (typeof score === 'number' && score < worst.score) {
      worst = { key: dim.key, score }
    }
  }
  return allDimensions.find((d) => d.key === worst.key)?.name || '-'
})

const insightIconMap: Record<string, { icon: string; color: string }> = {
  planning: { icon: 'TrendCharts', color: '#409eff' },
  tactical: { icon: 'Aim', color: '#67c23a' },
  tool_use: { icon: 'Warning', color: '#e6a23c' },
  memory: { icon: 'Warning', color: '#f56c6c' },
  replan: { icon: 'TrendCharts', color: '#909399' },
  retrieval: { icon: 'Warning', color: '#9b59b6' },
}

const displayInsights = computed(() => {
  const issues: string[] = (summaryData.value?.top_issues || []).filter(
    (item: string) => item && !item.includes('No significant') && !item.includes('No evaluations')
  )
  return issues.slice(0, 3).map((description, index) => {
    const dimKey = allDimensions[index]?.key || 'planning'
    const meta = insightIconMap[dimKey] || insightIconMap.planning
    return {
      title: `洞察 ${index + 1}`,
      description,
      icon: meta.icon,
      color: meta.color,
      bgColor: `${meta.color}1a`,
    }
  })
})

const displayRecommendations = computed(() => {
  const recs: string[] = (summaryData.value?.recommendations || []).filter(Boolean)
  return recs.map((description) => ({ description }))
})

const distributionColors = ['#f56c6c', '#e6a23c', '#409eff', '#67c23a', '#67c23a']

const initDistributionChart = () => {
  if (!distributionChart.value) return

  distributionInstance = echarts.init(distributionChart.value)

  const overallScores: number[] = summaryData.value?.score_distribution?.overall || []
  if (!overallScores.length) {
    distributionInstance.setOption(chartEmptyOption())
    return
  }

  const bucketValues = bucketScores(overallScores)

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
        data: bucketValues.map((value, index) => ({
          value,
          itemStyle: { color: distributionColors[index] },
        })),
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

  const tData = filteredTrends.value
  if (!tData.length) {
    dimensionTrendInstance.setOption(chartEmptyOption())
    return
  }

  const dates = tData.map((t: any) => dayjs(t.date).format('MM/DD'))

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
      const trendKey = dim?.trendKey || `avg_${key}`
      return {
        name: dim?.name || key,
        type: 'line',
        smooth: true,
        data: tData.map((t: any) => t[trendKey] || 0),
        itemStyle: { color: dim?.color },
      }
    }),
  }

  dimensionTrendInstance.setOption(option)
}

const initCorrelationChart = () => {
  if (!correlationChart.value) return

  correlationInstance = echarts.init(correlationChart.value)

  const dims = allDimensions.map((d) => d.key)
  const dist = summaryData.value?.score_distribution || {}
  const data: [number, number, number][] = []

  for (let i = 0; i < dims.length; i++) {
    for (let j = 0; j < dims.length; j++) {
      const distI: number[] = dist[dims[i]] || []
      const distJ: number[] = dist[dims[j]] || []
      const pairedLen = Math.min(distI.length, distJ.length)
      const corr = pairedLen >= 2 ? pearsonCorrelation(distI.slice(0, pairedLen), distJ.slice(0, pairedLen)) : null
      const val = corr !== null ? corr : i === j ? 1 : 0
      data.push([i, j, Number(val.toFixed(2))])
    }
  }

  if (!data.some(([, , v]) => v !== 0 && v !== 1)) {
    correlationInstance.setOption(chartEmptyOption('评估样本不足，无法计算相关性'))
    return
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

  const tData = filteredTrends.value
  if (!tData.length) {
    heatmapInstance.setOption(chartEmptyOption())
    return
  }

  const dates = tData.map((t: any) => dayjs(t.date).format('MM/DD'))
  const dims = allDimensions.map((d) => d.name)
  const data: [number, number, number][] = []

  for (let i = 0; i < allDimensions.length; i++) {
    const dim = allDimensions[i]
    for (let j = 0; j < tData.length; j++) {
      const value = heatmapMetric.value === 'count'
        ? (tData[j].count || 0)
        : (tData[j][dim.trendKey] || 0)
      data.push([j, i, Math.round(value)])
    }
  }

  const values = data.map(([, , v]) => v)
  const minVal = Math.min(...values)
  const maxVal = Math.max(...values)

  const option: echarts.EChartsOption = {
    tooltip: {
      position: 'top',
      formatter: (params: any) => {
        const [x, y, value] = params.data
        return `${dates[x]} ${dims[y]}: ${value}`
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
      data: dates,
      splitArea: { show: true },
    },
    yAxis: {
      type: 'category',
      data: dims,
      splitArea: { show: true },
    },
    visualMap: {
      min: minVal,
      max: maxVal || 100,
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
    const [summary, trends] = await Promise.all([
      reportApi.getSummary(),
      reportApi.getTrends(),
    ])
    summaryData.value = summary
    trendData.value = trends || []

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

watch(timeRange, () => {
  initDimensionTrendChart()
  initHeatmapChart()
})
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

        &.neutral {
          color: #909399;
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
