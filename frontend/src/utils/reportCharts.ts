import dayjs from 'dayjs'
import type { EChartsOption } from 'echarts'

export interface ReportDimension {
  key: string
  name: string
  color: string
  trendKey: string
}

export const REPORT_DIMENSIONS: ReportDimension[] = [
  { key: 'planning', name: '规划质量', color: '#409eff', trendKey: 'avg_planning' },
  { key: 'tactical', name: '战术决策', color: '#67c23a', trendKey: 'avg_tactical' },
  { key: 'tool_use', name: '工具使用', color: '#e6a23c', trendKey: 'avg_tool_use' },
  { key: 'memory', name: '记忆保持', color: '#f56c6c', trendKey: 'avg_memory' },
  { key: 'replan', name: '重规划', color: '#909399', trendKey: 'avg_replan' },
  { key: 'retrieval', name: '检索质量', color: '#9b59b6', trendKey: 'avg_retrieval' },
]

/** Filter trend rows by UI time range (client-side). */
export function filterTrendsByRange(trends: any[], range: string): any[] {
  if (!trends?.length || range === 'all') return trends || []
  const days = range === 'week' ? 7 : range === 'month' ? 30 : 90
  const cutoff = dayjs().subtract(days, 'day').format('YYYY-MM-DD')
  return trends.filter((row) => String(row.date) >= cutoff)
}

/** Bucket overall scores into histogram bins. */
export function bucketScores(scores: number[]): number[] {
  const buckets = [0, 0, 0, 0, 0]
  for (const score of scores) {
    if (score < 20) buckets[0]++
    else if (score < 40) buckets[1]++
    else if (score < 60) buckets[2]++
    else if (score < 80) buckets[3]++
    else buckets[4]++
  }
  return buckets
}

/** Pearson correlation; returns null when insufficient paired samples. */
export function pearsonCorrelation(xs: number[], ys: number[]): number | null {
  const n = Math.min(xs.length, ys.length)
  if (n < 2) return null

  const x = xs.slice(0, n)
  const y = ys.slice(0, n)
  const meanX = x.reduce((a, b) => a + b, 0) / n
  const meanY = y.reduce((a, b) => a + b, 0) / n

  let num = 0
  let denX = 0
  let denY = 0
  for (let i = 0; i < n; i++) {
    const dx = x[i] - meanX
    const dy = y[i] - meanY
    num += dx * dy
    denX += dx * dx
    denY += dy * dy
  }
  if (denX === 0 || denY === 0) return null
  return Math.max(-1, Math.min(1, num / Math.sqrt(denX * denY)))
}

/** ECharts placeholder when a chart has nothing to plot. */
export function chartEmptyOption(message = '暂无评估数据'): EChartsOption {
  return {
    graphic: {
      type: 'text',
      left: 'center',
      top: 'middle',
      style: {
        text: message,
        fill: '#909399',
        fontSize: 14,
      },
    },
  }
}

/** Delta percent between first and last trend point. */
export function trendDeltaPercent(trends: any[], field = 'avg_overall'): number | null {
  if (!trends?.length || trends.length < 2) return null
  const first = Number(trends[0][field] || 0)
  const last = Number(trends[trends.length - 1][field] || 0)
  if (first === 0) return null
  return Math.round(((last - first) / first) * 1000) / 10
}
