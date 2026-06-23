<template>
  <div class="benchmark-page" v-loading="loading">
    <div class="page-header">
      <div>
        <h2>单调性基准测试</h2>
        <p class="subtitle">
          6 条合成轨迹 × 6 维评估器 — 综合分应随质量递减（参考曲线 93.1 → 20.0）
        </p>
      </div>
      <div class="header-actions">
        <el-tag v-if="monotonicResult !== null" :type="monotonicResult ? 'success' : 'danger'" size="large">
          {{ monotonicResult ? '单调性通过' : '单调性违规' }}
        </el-tag>
        <el-button type="primary" :loading="running" :disabled="running" @click="handleRun">
          {{ running ? `运行中 (${runProgress}/${totalTrajectories})` : '实时运行基准' }}
        </el-button>
      </div>
    </div>

    <el-row :gutter="20">
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>综合分曲线</span>
              <el-radio-group v-model="chartMode" size="small">
                <el-radio-button label="reference">参考数据</el-radio-button>
                <el-radio-button label="live" :disabled="!liveResults.length">实时结果</el-radio-button>
                <el-radio-button label="both" :disabled="!liveResults.length">对比</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div ref="chartRef" class="chart-container" />
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="hover" class="info-card">
          <template #header><span>轨迹说明</span></template>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item
              v-for="item in referenceScores"
              :key="item.level"
              :label="item.level"
            >
              {{ item.steps }} 步 · 参考 {{ item.overall }}
            </el-descriptions-item>
          </el-descriptions>
          <el-alert
            type="info"
            :closable="false"
            show-icon
            style="margin-top: 16px"
            title="实时运行将调用 LLM 评估全部 6 条轨迹，耗时约 2–3 分钟。"
          />
        </el-card>
      </el-col>
    </el-row>

    <el-card v-if="liveResults.length" shadow="hover" style="margin-top: 20px">
      <template #header><span>实时评估明细</span></template>
      <el-table :data="liveResults" style="width: 100%">
        <el-table-column prop="level" label="质量等级" width="100" />
        <el-table-column prop="steps" label="步数" width="80" />
        <el-table-column prop="reference" label="参考分" width="90" />
        <el-table-column prop="overall" label="实测分" width="90">
          <template #default="{ row }">
            <span :style="{ color: scoreDeltaColor(row) }">{{ row.overall?.toFixed(1) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="维度得分">
          <template #default="{ row }">
            <el-tag
              v-for="(score, dim) in row.dimensions"
              :key="dim"
              size="small"
              style="margin: 2px"
            >
              {{ dimLabels[dim] || dim }}: {{ Number(score).toFixed(0) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import { benchmarkApi } from '@/api'
import { connectBenchmarkStream } from '@/utils/evaluationStream'

const loading = ref(false)
const running = ref(false)
const runProgress = ref(0)
const totalTrajectories = ref(6)
const monotonicResult = ref<boolean | null>(null)
const chartMode = ref<'reference' | 'live' | 'both'>('reference')
const chartRef = ref<HTMLElement>()
const qualityOrder = ref<string[]>([])
const referenceScores = ref<{ level: string; overall: number; steps: number }[]>([])
const liveResults = ref<any[]>([])
let chartInstance: echarts.ECharts | null = null
let streamAbort: AbortController | null = null

const dimLabels: Record<string, string> = {
  planning: '规划',
  tactical: '战术',
  tool_use: '工具',
  memory: '记忆',
  replan: '重规划',
  retrieval: '检索',
}

const scoreDeltaColor = (row: { overall: number; reference: number }) => {
  const delta = Math.abs(row.overall - row.reference)
  if (delta <= 8) return '#67c23a'
  if (delta <= 15) return '#e6a23c'
  return '#f56c6c'
}

const buildChartOption = () => {
  const levels = qualityOrder.value.length
    ? qualityOrder.value
    : referenceScores.value.map((r) => r.level)

  const refData = levels.map(
    (level) => referenceScores.value.find((r) => r.level === level)?.overall ?? 0,
  )
  const liveData = levels.map((level) => {
    const item = liveResults.value.find((r) => r.level === level)
    return item?.overall ?? null
  })

  const series: echarts.SeriesOption[] = []

  if (chartMode.value === 'reference' || chartMode.value === 'both') {
    series.push({
      name: '参考曲线',
      type: 'line',
      smooth: true,
      data: refData,
      lineStyle: { width: 3, type: chartMode.value === 'both' ? 'dashed' : 'solid' },
      itemStyle: { color: '#909399' },
      areaStyle: chartMode.value === 'reference' ? { color: 'rgba(64, 158, 255, 0.15)' } : undefined,
    })
  }

  if ((chartMode.value === 'live' || chartMode.value === 'both') && liveResults.value.length) {
    series.push({
      name: '实时结果',
      type: 'line',
      smooth: true,
      data: liveData,
      lineStyle: { width: 3 },
      itemStyle: { color: '#409eff' },
      areaStyle: chartMode.value === 'live' ? { color: 'rgba(64, 158, 255, 0.2)' } : undefined,
    })
  }

  return {
    tooltip: { trigger: 'axis' },
    legend: series.length > 1 ? { data: series.map((s) => s.name as string) } : undefined,
    grid: { left: '3%', right: '4%', bottom: '8%', containLabel: true },
    xAxis: {
      type: 'category',
      data: levels,
      axisLabel: { interval: 0 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      name: '综合分',
    },
    series,
  }
}

const renderChart = () => {
  if (!chartRef.value) return
  if (!chartInstance) chartInstance = echarts.init(chartRef.value)
  chartInstance.setOption(buildChartOption(), true)
}

const fetchMetadata = async () => {
  loading.value = true
  try {
    const data = await benchmarkApi.getMonotonicity()
    qualityOrder.value = data.quality_order || []
    referenceScores.value = data.reference_scores || []
    totalTrajectories.value = qualityOrder.value.length || 6
    renderChart()
  } catch (error) {
    console.error('Failed to load benchmark metadata:', error)
  } finally {
    loading.value = false
  }
}

const handleRun = async () => {
  streamAbort?.abort()
  streamAbort = new AbortController()
  running.value = true
  runProgress.value = 0
  liveResults.value = []
  monotonicResult.value = null
  chartMode.value = 'live'

  try {
    await connectBenchmarkStream(
      {
        onStart: (data) => {
          totalTrajectories.value = data.total
        },
        onProgress: (data) => {
          runProgress.value = data.index - 1
        },
        onResult: (data) => {
          liveResults.value.push(data)
          runProgress.value = data.index as number
          renderChart()
        },
        onComplete: (data) => {
          monotonicResult.value = data.monotonic
          chartMode.value = 'both'
          renderChart()
        },
        onError: (message) => {
          console.error('Benchmark stream error:', message)
        },
      },
      streamAbort.signal,
    )
  } catch (error: any) {
    if (error?.name !== 'AbortError') {
      console.error('Benchmark run failed:', error)
    }
  } finally {
    running.value = false
  }
}

const handleResize = () => chartInstance?.resize()

watch(chartMode, () => renderChart())

onMounted(() => {
  fetchMetadata()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  streamAbort?.abort()
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
})
</script>

<style scoped lang="scss">
.benchmark-page {
  .page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 20px;
    gap: 16px;

    h2 {
      margin: 0 0 8px;
    }

    .subtitle {
      margin: 0;
      color: #909399;
      font-size: 14px;
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-shrink: 0;
    }
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .chart-container {
    height: 380px;
  }

  .info-card {
    height: 100%;
  }
}
</style>
