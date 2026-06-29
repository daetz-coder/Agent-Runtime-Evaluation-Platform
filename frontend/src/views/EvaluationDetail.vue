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
      <!-- In-progress: SSE stream progress -->
      <el-card
        v-if="evaluation.status === 'in_progress' && shouldUseStream"
        class="stream-progress-card"
        shadow="hover"
      >
        <template #header>
          <div class="card-header">
            <span>评估进行中</span>
            <el-tag type="info" size="small">SSE 实时进度</el-tag>
          </div>
        </template>
        <el-progress
          :percentage="streamProgressPercent"
          :stroke-width="14"
          :status="streamError ? 'exception' : undefined"
          style="margin-bottom: 20px"
        />
        <el-steps :active="streamProgress.completed" finish-status="success" align-center>
          <el-step
            v-for="dim in streamDimensions"
            :key="dim.key"
            :title="dim.name"
            :description="streamStepDescription(dim.key)"
          />
        </el-steps>
        <p v-if="streamError" class="stream-error">{{ streamError }}</p>
        <p v-else-if="streaming" class="stream-hint">
          <el-icon class="is-loading"><Loading /></el-icon>
          正在运行 6 个评估器（约 15–30 秒）…
        </p>
      </el-card>

      <!-- In-progress: legacy polling fallback -->
      <el-alert
        v-else-if="evaluation.status === 'in_progress'"
        title="评估正在进行中，页面将自动刷新..."
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 20px"
      >
        <template #default>
          <div style="display: flex; align-items: center; gap: 8px">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>正在运行 6 个评估器，请稍候（约 15-30 秒）</span>
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
            <h3>{{ localizeEvaluationText(evaluation.evaluation?.summary) || '评估完成' }}</h3>
            <div class="recommendations">
              <h4>改进建议：</h4>
              <ul>
                <li v-for="(rec, index) in evaluation.evaluation?.recommendations" :key="index">
                  {{ localizeEvaluationText(rec) }}
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
                {{ getDimensionScoreLabel(dim.key) }}
              </span>
            </div>
          </div>

          <div class="dimension-detail">
            <div v-for="(metric, key) in dim.metrics" :key="key" class="metric-item">
              <span class="metric-name">{{ metric }}</span>
              <el-progress
                v-if="isDimensionApplicable(dim.key)"
                :percentage="getMetricScore(dim.key, key)"
                :color="getScoreColor(getMetricScore(dim.key, key))"
                :stroke-width="8"
                :show-text="false"
              />
              <div v-else class="metric-na-line"></div>
              <span class="metric-value">
                {{ isDimensionApplicable(dim.key) ? getMetricScore(dim.key, key) : 'N/A' }}
              </span>
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
            <el-button
              v-if="evaluation?.status === 'completed'"
              size="small"
              type="primary"
              plain
              :icon="VideoPlay"
              style="margin-left: auto"
              @click="showReplayPanel = !showReplayPanel"
            >
              {{ showReplayPanel ? '隐藏调试器' : 'Replay 调试器' }}
            </el-button>
            <el-button
              v-if="evaluation?.status === 'completed'"
              size="small"
              type="success"
              plain
              style="margin-left: 8px"
              @click="openDiffDialog"
            >
              A/B 对比
            </el-button>
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

      <!-- Replay Debugger Panel -->
      <el-card
        v-if="showReplayPanel && replayData"
        class="replay-card"
        shadow="hover"
      >
        <template #header>
          <div class="card-header">
            <span><el-icon color="#409eff"><VideoPlay /></el-icon> Replay 调试器</span>
            <el-tag type="info">{{ replayData.step_count }} 步</el-tag>
          </div>
        </template>

        <div class="replay-timeline">
          <el-timeline>
            <el-timeline-item
              v-for="step in replayData.steps"
              :key="step.step_number"
              :type="getReplayStepType(step.action_type)"
              placement="top"
            >
              <template #default>
                <div class="replay-step-header">
                  <strong>步骤 {{ step.step_number }}</strong>
                  <el-tag :type="getReplayStepType(step.action_type)" size="small">
                    {{ step.action_type }}
                  </el-tag>
                  <el-tag v-if="step.llm_model !== 'unknown'" size="small" type="info">
                    {{ step.llm_model }}
                  </el-tag>
                  <el-tag v-if="step.latency_ms > 0" size="small" type="success">
                    {{ step.latency_ms.toFixed(0) }}ms
                  </el-tag>
                </div>

                <el-collapse>
                  <el-collapse-item title="LLM 原始 Prompt" name="prompt">
                    <pre class="llm-raw-text">{{ step.llm_prompt || '(无记录)' }}</pre>
                  </el-collapse-item>
                  <el-collapse-item title="LLM 原始 Response" name="response">
                    <pre class="llm-raw-text">{{ step.llm_response || '(无记录)' }}</pre>
                  </el-collapse-item>
                </el-collapse>
              </template>
            </el-timeline-item>
          </el-timeline>
        </div>
      </el-card>

      <!-- Judge Raw Panel -->
      <el-card
        v-if="evaluation?.status === 'completed' && !loading"
        class="judge-raw-card"
        shadow="hover"
      >
        <template #header>
          <div class="card-header">
            <span><el-icon color="#e6a23c"><View /></el-icon> Judge 透明度面板</span>
            <el-radio-group v-model="selectedJudgeDim" size="small">
              <el-radio-button v-for="dim in dimensions" :key="dim.key" :label="dim.key">
                {{ dim.name }}
              </el-radio-button>
            </el-radio-group>
            <el-button
              size="small"
              type="warning"
              plain
              @click="fetchJudgeRaw()"
              :loading="judgeRawLoading"
            >
              查看原始 Judge 输出
            </el-button>
          </div>
        </template>

        <div v-if="judgeRawData" class="judge-raw-content">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="维度">{{ selectedJudgeDim }}</el-descriptions-item>
            <el-descriptions-item label="Judge 模型">{{ judgeRawData[selectedJudgeDim]?.judge_model || 'N/A' }}</el-descriptions-item>
            <el-descriptions-item label="综合得分" :span="2">
              <el-tag :type="getScoreTagType(judgeRawData[selectedJudgeDim]?.score)">
                {{ judgeRawData[selectedJudgeDim]?.score ?? 'N/A' }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>

          <div v-if="judgeRawData[selectedJudgeDim]?.score_breakdown" style="margin-top:12px">
            <h4>子维度得分</h4>
            <div v-for="(val, key) in judgeRawData[selectedJudgeDim]?.score_breakdown" :key="key" class="subscore-row">
              <span class="subscore-label">{{ key }}</span>
              <el-progress
                :percentage="Number(val)"
                :color="getScoreColor(Number(val))"
                :stroke-width="8"
                style="flex:1;margin:0 8px"
              />
              <span class="subscore-value">{{ val }}</span>
            </div>
          </div>

          <el-collapse style="margin-top:16px">
            <el-collapse-item title="Judge Prompt（完整）">
              <pre class="llm-raw-text">{{ judgeRawData[selectedJudgeDim]?.judge_prompt || '(无记录)' }}</pre>
            </el-collapse-item>
            <el-collapse-item title="Judge Response（原始 JSON）">
              <pre class="llm-raw-text">{{ judgeRawData[selectedJudgeDim]?.judge_response || '(无记录)' }}</pre>
            </el-collapse-item>
          </el-collapse>
        </div>

        <el-empty v-else-if="!judgeRawLoading" description='点击 "查看原始 Judge 输出" 按钮加载数据' />
      </el-card>

      <!-- Multi-model Consensus -->
      <el-card class="consensus-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span>多模型共识评估</span>
            <el-button
              v-if="!consensusData && evaluation?.status === 'completed'"
              type="primary"
              link
              :loading="consensusLoading"
              @click="loadConsensus"
            >
              加载共识评估
            </el-button>
            <template v-if="consensusData">
              <el-tag :type="consensusData.result.consensus_type === 'cross_provider' ? 'success' : 'warning'" size="small">
                {{ consensusData.result.consensus_type === 'cross_provider' ? '跨厂商' : '同厂商' }}
              </el-tag>
              <el-tag
                v-if="consensusData.result.std_score !== undefined"
                :type="consensusData.result.std_score < 10 ? 'success' : 'warning'"
                size="small"
                style="margin-left:4px"
              >
                std={{ consensusData.result.std_score.toFixed(1) }}
              </el-tag>
            </template>
          </div>
        </template>
        <el-row v-if="consensusData" :gutter="16">
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
        <el-empty v-else description='点击上方「加载共识评估」获取多模型对比（将消耗额外 API 配额）' />
      </el-card>

      <!-- Retrieval Quality / Hallucination Inspector -->
      <el-card class="retrieval-card" shadow="hover" v-if="retrievalFeedback">
        <template #header>
          <div class="card-header">
            <span>检索质量分析</span>
            <el-tag v-if="retrievalFeedback.hallucination_detected" type="danger" size="small" effect="dark">
              幻觉告警
            </el-tag>
            <el-tag v-else type="success" size="small">无幻觉</el-tag>
          </div>
        </template>
        <el-row :gutter="16">
          <el-col :span="12">
            <div class="retrieval-scores">
              <div class="retrieval-score-item">
                <span class="label">相关性 (Relevance)</span>
                <el-progress :percentage="retrievalFeedback.relevance || 0" :stroke-width="10" color="#409eff" />
              </div>
              <div class="retrieval-score-item">
                <span class="label">证据准确性 (Evidence Accuracy)</span>
                <el-progress :percentage="retrievalFeedback.evidence_accuracy || 0" :stroke-width="10" color="#67c23a" />
              </div>
              <div class="retrieval-score-item">
                <span class="label">覆盖度 (Coverage)</span>
                <el-progress :percentage="retrievalFeedback.coverage || 0" :stroke-width="10" color="#e6a23c" />
              </div>
            </div>
          </el-col>
          <el-col :span="12">
            <div v-if="retrievalFeedback.missing_info?.length" class="missing-info">
              <h4>缺失信息</h4>
              <el-tag v-for="info in retrievalFeedback.missing_info" :key="info" type="warning" style="margin:2px">
                {{ info }}
              </el-tag>
            </div>
            <div v-if="retrievalFeedback.feedback" class="feedback-section" style="margin-top:12px">
              <h4>评估反馈</h4>
              <p>{{ retrievalFeedback.feedback }}</p>
            </div>
          </el-col>
        </el-row>
      </el-card>
    </template>

    <!-- Diff Dialog (A/B Comparison) -->
    <el-dialog v-model="diffDialogVisible" title="A/B 对比" width="80%" top="5vh">
      <template v-if="diffData">
        <div class="diff-summary">
          <el-alert
            :title="`共 ${diffData.total_changes} 处变化`"
            :type="diffData.total_changes > 0 ? 'warning' : 'success'"
            :description="`新增 ${diffData.steps_added} · 删除 ${diffData.steps_removed} · 修改 ${diffData.steps_modified}`"
            show-icon
            style="margin-bottom: 16px"
          />
        </div>

        <el-table :data="diffData.steps" stripe size="small" max-height="500">
          <el-table-column prop="step_number" label="步骤" width="80" />
          <el-table-column label="变化" width="100">
            <template #default="{ row }">
              <el-tag
                :type="row.change_type === 'unchanged' ? 'info' : row.change_type === 'added' ? 'success' : row.change_type === 'removed' ? 'danger' : 'warning'"
                size="small"
              >
                {{ row.change_type === 'added' ? '新增' : row.change_type === 'removed' ? '删除' : row.change_type === 'changed' ? '修改' : '不变' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="变更前" min-width="200">
            <template #default="{ row }">
              <pre v-if="row.before" class="diff-pre">{{ formatActionDetail(row.before) }}</pre>
              <span v-else class="diff-empty">—</span>
            </template>
          </el-table-column>
          <el-table-column label="变更后" min-width="200">
            <template #default="{ row }">
              <pre v-if="row.after" class="diff-pre">{{ formatActionDetail(row.after) }}</pre>
              <span v-else class="diff-empty">—</span>
            </template>
          </el-table-column>
          <el-table-column label="变更字段" min-width="160">
            <template #default="{ row }">
              <el-tag v-for="f in row.field_changes" :key="f" size="small" type="warning" style="margin: 2px">
                {{ f }}
              </el-tag>
              <span v-if="!row.field_changes?.length" class="diff-empty">—</span>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <div v-else-if="diffLoading" style="text-align:center;padding:40px">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        <p>加载对比数据...</p>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { ArrowLeft, VideoPlay, View, Warning, CircleCheck, Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { evaluationApi, taskApi, withSilent } from '@/api'
import { connectEvaluationStream } from '@/utils/evaluationStream'
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
let streamAbort: AbortController | null = null
const consensusData = ref<any>(null)
const consensusLoading = ref(false)
const consensusChart = ref<HTMLElement>()

// Replay Debugger
const showReplayPanel = ref(false)
const replayData = ref<any>(null)
const replayLoading = ref(false)

// Judge Transparency
const selectedJudgeDim = ref('planning')
const judgeRawData = ref<Record<string, any> | null>(null)
const judgeRawLoading = ref(false)

// Diff
const diffDialogVisible = ref(false)
const diffData = ref<any>(null)
const diffLoading = ref(false)

const streamStartedForId = ref<string | null>(null)

const shouldUseStream = computed(
  () => evaluation.value?.stream_mode === true || route.query.stream === '1',
)
const streaming = ref(false)
const streamError = ref('')
const streamProgress = ref({
  completed: 0,
  total: 6,
  scores: {} as Record<string, number | null>,
  overall: null as number | null,
})

const streamDimensions = [
  { key: 'planning', name: '规划' },
  { key: 'tactical', name: '战术' },
  { key: 'tool_use', name: '工具' },
  { key: 'memory', name: '记忆' },
  { key: 'replan', name: '重规划' },
  { key: 'retrieval', name: '检索' },
]

const streamProgressPercent = computed(() =>
  Math.round((streamProgress.value.completed / streamProgress.value.total) * 100),
)

const streamStepDescription = (key: string) => {
  const score = streamProgress.value.scores[key]
  if (score != null) return `${score.toFixed(1)} 分`
  if (Object.prototype.hasOwnProperty.call(streamProgress.value.scores, key)) return '不适用'
  const idx = streamDimensions.findIndex((d) => d.key === key)
  if (idx < streamProgress.value.completed) return '完成'
  if (idx === streamProgress.value.completed && streaming.value) return '评估中…'
  return '等待'
}

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

const retrievalFeedback = computed(() => {
  return evaluation.value?.evaluation?.retrieval || null
})

const currentDimensionData = computed(() => {
  return evaluation.value?.evaluation?.[selectedDimension.value] || {}
})

const currentFeedback = computed(() => {
  return localizeEvaluationText(currentDimensionData.value.feedback) || '暂无反馈'
})

const currentIssues = computed(() => {
  const data = currentDimensionData.value
  return data.missing_milestones || data.problematic_actions || data.inefficient_calls || data.forgotten_facts || data.missed_replan_opportunities || []
})

const currentSuggestions = computed(() => {
  return (currentDimensionData.value.suggestions || []).map((item: string) => localizeEvaluationText(item))
})

const textTranslations: Record<string, string> = {
  'Improve RAG retrieval relevance and evidence grounding.': '改进检索质量：提升 RAG 检索相关性、证据准确性和引用依据。',
  'Improve planning before execution.': '改进规划：执行前补充关键步骤、依赖关系和验收标准。',
  'Improve next-action selection and tactical decisions.': '改进战术决策：确保每一步行动都服务于当前目标和上下文。',
  'Improve tool selection, parameters, and result use.': '改进工具使用：加强工具选择、参数校验和结果利用。',
  'Improve retention and consistency across context.': '改进记忆保持：记录并复用关键事实，避免上下文不一致。',
  'Improve replanning when failures or new facts appear.': '改进重规划：在失败、新事实或路径受阻时及时调整计划。',
  'Continue maintaining high performance across all evaluation dimensions.': '继续保持当前表现，并持续监控各维度是否出现波动。',
}

const dimensionNameTranslations: Record<string, string> = {
  planning: '规划质量',
  tactical: '战术决策',
  tool_use: '工具使用',
  memory: '记忆保持',
  replan: '重规划',
  retrieval: '检索质量',
}

const localizeEvaluationText = (text?: string) => {
  if (!text) return ''
  if (textTranslations[text]) return textTranslations[text]
  return text
    .replace(/^Overall score:\s*([0-9.]+)\/100\.\s*/i, '综合得分：$1/100。')
    .replace(/Strongest dimension:\s*(planning|tactical|tool_use|memory|replan|retrieval)\s*\(([0-9.]+)\)\./i, (_, dim, score) => `最强维度：${dimensionNameTranslations[dim] || dim}（${score}）。`)
    .replace(/Weakest dimension:\s*(planning|tactical|tool_use|memory|replan|retrieval)\s*\(([0-9.]+)\)\./i, (_, dim, score) => `待改进维度：${dimensionNameTranslations[dim] || dim}（${score}）。`)
}

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

const isDimensionApplicable = (dimKey: string) => {
  return evaluation.value?.evaluation?.[dimKey]?.applicable !== false
}

const getDimensionScoreLabel = (dimKey: string) => {
  return isDimensionApplicable(dimKey) ? getDimensionScore(dimKey) : '不适用'
}

const getMetricScore = (dimKey: string, metricKey: string) => {
  return Math.round(evaluation.value?.evaluation?.[dimKey]?.[metricKey] || 0)
}

const getDimensionFeedback = (dimKey: string) => {
  const data = evaluation.value?.evaluation?.[dimKey]
  if (data?.applicable === false) {
    return data.not_applicable_reason || data.feedback || '该维度不适用于本次轨迹，已从综合评分中剔除。'
  }
  return data?.feedback || ''
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

// ── Replay Debugger methods ──

const getReplayStepType = (type: string) => {
  const map: Record<string, string> = {
    plan: 'primary',
    tool_call: 'success',
    think: 'warning',
    replan: 'danger',
    failure: 'danger',
    memory_write: 'info',
    memory_read: 'info',
  }
  return map[type] || 'info'
}

// ── Judge Transparency methods ──

const fetchJudgeRaw = async () => {
  if (!evaluation.value?.id) return
  judgeRawLoading.value = true
  try {
    judgeRawData.value = await evaluationApi.getJudgeRaw(
      evaluation.value.id,
      undefined,
      withSilent(),
    )
  } catch {
    judgeRawData.value = null
  } finally {
    judgeRawLoading.value = false
  }
}

const getScoreTagType = (score: number | null | undefined) => {
  if (score == null) return 'info'
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'danger'
}

// ── Diff / A/B Comparison methods ──

const openDiffDialog = async () => {
  if (!evaluation.value?.id) return
  diffLoading.value = true
  diffDialogVisible.value = true
  diffData.value = null

  // Prompt user for the base evaluation ID
  const baseId = prompt('输入基准 Evaluation ID（留空使用当前 evaluation 作为 head）')
  if (!baseId) {
    diffLoading.value = false
    return
  }

  try {
    diffData.value = await evaluationApi.getDiff(baseId, evaluation.value.id, withSilent())
  } catch {
    diffData.value = null
    ElMessage.error('加载对比数据失败，请检查 Evaluation ID')
  } finally {
    diffLoading.value = false
  }
}

// Initialize radar chart
const initRadarChart = () => {
  if (!radarChart.value) return

  radarInstance = echarts.init(radarChart.value)

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'item',
      formatter: () => dimensions.map((d) => {
        const label = isDimensionApplicable(d.key) ? `${getDimensionScore(d.key)}` : 'N/A'
        return `${d.name}: ${label}`
      }).join('<br/>'),
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

    // Stream mode: drive evaluation via SSE instead of polling
    if (data.status === 'in_progress' && (data.stream_mode || route.query.stream === '1')) {
      if (streamStartedForId.value !== evalId) {
        streamStartedForId.value = evalId
        startEvaluationStream(data.task_id, evalId)
      }
    } else if (data.status === 'in_progress') {
      startPolling(evalId)
    }
  } catch (error) {
    console.error('Failed to fetch evaluation:', error)
  } finally {
    loading.value = false
  }
}

const stopStream = () => {
  streamAbort?.abort()
  streamAbort = null
  streaming.value = false
}

const startEvaluationStream = async (taskId: string, evalId: string) => {
  stopStream()
  stopPolling()
  streamError.value = ''
  streamProgress.value = { completed: 0, total: 6, scores: {}, overall: null }
  streaming.value = true
  streamAbort = new AbortController()

  try {
    await connectEvaluationStream(
      taskId,
      evalId,
      {
        onProgress: (data) => {
          streamProgress.value.completed = data.progress
          streamProgress.value.scores[data.dimension] = data.score
        },
        onResult: (data) => {
          streamProgress.value.overall = data.overall
        },
        onError: (data) => {
          streamError.value = data.message
        },
        onDone: async () => {
          streaming.value = false
          streamStartedForId.value = null
          await fetchData()
        },
      },
      streamAbort.signal,
    )
  } catch (error: any) {
    if (error?.name !== 'AbortError') {
      streamError.value = error?.message || '流式评估连接失败'
      streaming.value = false
      startPolling(evalId)
    }
  } finally {
    streaming.value = false
  }
}

const loadConsensus = async () => {
  const taskId = evaluation.value?.task_id
  if (!taskId || consensusLoading.value) return
  consensusLoading.value = true
  try {
    consensusData.value = await evaluationApi.getConsensus(taskId)
    setTimeout(initConsensusChart, 200)
  } catch {
    consensusData.value = null
  } finally {
    consensusLoading.value = false
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
  stopStream()
})

watch(() => route.params.id, () => {
  streamStartedForId.value = null
  stopPolling()
  stopStream()
  fetchData()
})

watch(selectedDimension, () => {
  // Update radar chart highlight if needed
})

// Fetch replay data when panel is opened
watch(showReplayPanel, async (show) => {
  if (show && !replayData.value && evaluation.value?.id) {
    replayLoading.value = true
    try {
      replayData.value = await evaluationApi.getReplay(evaluation.value.id, withSilent())
    } catch {
      replayData.value = null
    } finally {
      replayLoading.value = false
    }
  }
})

// Watch judge dimension changes to auto-refresh if data already loaded
watch(selectedJudgeDim, () => {
  // Data is already fetched — just display different dimension
})
</script>

<style scoped lang="scss">
.evaluation-detail {
  .stream-progress-card {
    margin-bottom: 20px;

    .stream-hint {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 16px;
      color: #909399;
      font-size: 14px;
    }

    .stream-error {
      margin-top: 12px;
      color: #f56c6c;
      font-size: 14px;
    }
  }

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

        .metric-na-line {
          flex: 1;
          height: 8px;
          border-radius: 999px;
          background: repeating-linear-gradient(
            90deg,
            #e4e7ed 0,
            #e4e7ed 8px,
            transparent 8px,
            transparent 14px
          );
        }

        .metric-value {
          width: 36px;
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

.retrieval-card {
  margin-top: 20px;
  .retrieval-scores {
    .retrieval-score-item {
      margin-bottom: 12px;
      .label {
        display: block;
        font-size: 13px;
        color: #606266;
        margin-bottom: 4px;
      }
    }
  }
  .missing-info {
    h4 {
      font-size: 14px;
      margin: 0 0 8px 0;
      color: #303133;
    }
  }
  .feedback-section {
    h4 {
      font-size: 14px;
      margin: 0 0 8px 0;
      color: #303133;
    }
    p {
      font-size: 13px;
      color: #606266;
      line-height: 1.6;
    }
  }

  // Diff dialog styles
  .diff-pre {
    background: #f5f7fa;
    border-radius: 4px;
    padding: 8px;
    font-size: 12px;
    max-height: 150px;
    overflow-y: auto;
    margin: 0;
    white-space: pre-wrap;
    word-break: break-all;
  }

  .diff-empty {
    color: #c0c4cc;
    font-style: italic;
  }
}
</style>
