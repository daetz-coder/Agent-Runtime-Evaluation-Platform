<template>
  <div class="settings-page">
    <div class="page-header">
      <h2>系统设置</h2>
    </div>

    <el-alert
      title="本地偏好设置"
      description="此处保存的是浏览器本地偏好（如刷新间隔）。评估权重、LLM 配置由服务端 .env 控制，修改后需重启后端生效。"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 16px"
    />

    <el-tabs v-model="activeTab" class="settings-tabs">
      <!-- General Settings -->
      <el-tab-pane label="基本设置" name="general">
        <el-card shadow="never">
          <el-form :model="generalForm" label-width="150px">
            <el-form-item label="默认LLM提供商">
              <el-select v-model="generalForm.llmProvider" style="width: 300px" disabled>
                <el-option label="DeepSeek（默认）" value="deepseek" />
                <el-option label="OpenAI" value="openai" />
                <el-option label="Anthropic" value="anthropic" />
              </el-select>
              <div class="form-hint">LLM 提供商由服务端 .env 中 DEFAULT_LLM_PROVIDER 配置</div>
            </el-form-item>

            <el-form-item label="默认模型">
              <el-input v-model="generalForm.llmModel" style="width: 300px" disabled />
              <div class="form-hint">模型名称由服务端环境变量配置</div>
            </el-form-item>

            <el-form-item label="API Key">
              <el-input
                v-model="generalForm.apiKey"
                type="password"
                show-password
                placeholder="不在前端存储，请配置 .env"
                style="width: 400px"
                disabled
              />
            </el-form-item>

            <el-form-item label="自动刷新间隔">
              <el-select v-model="generalForm.refreshInterval" style="width: 200px">
                <el-option label="关闭" :value="0" />
                <el-option label="30秒" :value="30" />
                <el-option label="1分钟" :value="60" />
                <el-option label="5分钟" :value="300" />
              </el-select>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" @click="saveGeneralSettings">保存设置</el-button>
              <el-button @click="resetGeneralSettings">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- Evaluation Settings -->
      <el-tab-pane label="评估设置" name="evaluation">
        <el-card shadow="never">
          <el-alert
            title="评估参数只读"
            description="六维权重与阈值当前由后端 evaluate_parallel() 硬编码，以下配置仅供参考展示。"
            type="warning"
            :closable="false"
            show-icon
            style="margin-bottom: 16px"
          />
          <el-form :model="evaluationForm" label-width="150px">
            <el-form-item label="评估权重配置">
              <div class="weight-config">
                <div v-for="dim in dimensions" :key="dim.key" class="weight-item">
                  <span class="dim-name">{{ dim.name }}</span>
                  <el-slider
                    v-model="evaluationForm.weights[dim.key]"
                    :min="0"
                    :max="100"
                    :step="5"
                    show-input
                    style="width: 300px"
                    disabled
                  />
                </div>
              </div>
            </el-form-item>

            <el-form-item label="评分阈值">
              <div class="threshold-config">
                <div class="threshold-item">
                  <span class="threshold-label">优秀</span>
                  <el-input-number v-model="evaluationForm.thresholds.excellent" :min="0" :max="100" />
                  <span class="threshold-unit">分以上</span>
                </div>
                <div class="threshold-item">
                  <span class="threshold-label">良好</span>
                  <el-input-number v-model="evaluationForm.thresholds.good" :min="0" :max="100" />
                  <span class="threshold-unit">分以上</span>
                </div>
                <div class="threshold-item">
                  <span class="threshold-label">及格</span>
                  <el-input-number v-model="evaluationForm.thresholds.pass" :min="0" :max="100" />
                  <span class="threshold-unit">分以上</span>
                </div>
              </div>
            </el-form-item>

            <el-form-item label="并发评估数">
              <el-input-number v-model="evaluationForm.maxConcurrent" :min="1" :max="10" disabled />
              <span class="form-hint">并行评估由 EVAL_PARALLEL 环境变量控制</span>
            </el-form-item>

            <el-form-item label="超时时间">
              <el-input-number v-model="evaluationForm.timeout" :min="30" :max="600" :step="30" disabled />
              <span class="form-hint">秒</span>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- Notification Settings -->
      <el-tab-pane label="通知设置" name="notification">
        <el-card shadow="never">
          <el-alert
            title="浏览器通知"
            description="以下开关保存在本地，用于控制前端提示行为。Webhook 通知请配置服务端 EVAL_WEBHOOK_URL。"
            type="info"
            :closable="false"
            show-icon
            style="margin-bottom: 16px"
          />
          <el-form :model="notificationForm" label-width="150px">
            <el-form-item label="评估完成通知">
              <el-switch v-model="notificationForm.onComplete" />
            </el-form-item>

            <el-form-item label="评估失败通知">
              <el-switch v-model="notificationForm.onFailure" />
            </el-form-item>

            <el-form-item label="低分警告">
              <el-switch v-model="notificationForm.onLowScore" />
            </el-form-item>

            <el-form-item label="警告阈值" v-if="notificationForm.onLowScore">
              <el-input-number v-model="notificationForm.lowScoreThreshold" :min="0" :max="100" />
              <span class="form-hint">低于此分数将触发警告</span>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" @click="saveNotificationSettings">保存设置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- About -->
      <el-tab-pane label="关于" name="about">
        <el-card shadow="never">
          <div class="about-content">
            <div class="about-logo">
              <el-icon :size="64" color="#409eff"><Cpu /></el-icon>
            </div>
            <h3>Agent Runtime Evaluation Platform</h3>
            <p class="version">版本 0.1.0</p>
            <p class="description">
              Agent 运行时质量评估平台 — 六维评估体系（Planning / Tactical / Tool Use / Memory / Replan / Retrieval），
              配套 Wiki Agent RAG 演示与零侵入 SDK 接入。
            </p>

            <div class="features">
              <h4>核心功能</h4>
              <ul>
                <li><el-icon color="#67c23a"><CircleCheck /></el-icon> 六维 LLM-as-Judge 评估</li>
                <li><el-icon color="#67c23a"><CircleCheck /></el-icon> RAG 检索质量与幻觉检测</li>
                <li><el-icon color="#67c23a"><CircleCheck /></el-icon> 并行评估 · 迭代对比 · 报告导出</li>
                <li><el-icon color="#67c23a"><CircleCheck /></el-icon> Wiki Agent 评估闭环</li>
                <li><el-icon color="#67c23a"><CircleCheck /></el-icon> 多模型共识评估</li>
              </ul>
            </div>

            <div class="tech-stack">
              <h4>技术栈</h4>
              <div class="tech-tags">
                <el-tag>Vue 3</el-tag>
                <el-tag>FastAPI</el-tag>
                <el-tag>LangGraph</el-tag>
                <el-tag>ECharts</el-tag>
                <el-tag>Element Plus</el-tag>
                <el-tag>Python</el-tag>
              </div>
            </div>
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { Cpu, CircleCheck } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const activeTab = ref('general')

// Dimensions config
const dimensions = [
  { key: 'planning', name: '规划质量' },
  { key: 'tactical', name: '战术决策' },
  { key: 'tool_use', name: '工具使用' },
  { key: 'memory', name: '记忆保持' },
  { key: 'replan', name: '重规划' },
  { key: 'retrieval', name: '检索质量' },
]

// General settings form (local UI preferences only)
const generalForm = reactive({
  llmProvider: 'deepseek',
  llmModel: 'deepseek-chat',
  apiKey: '',
  refreshInterval: 60,
})

// Evaluation settings form (read-only reference values)
const evaluationForm = reactive({
  weights: {
    planning: 20,
    tactical: 20,
    tool_use: 15,
    memory: 15,
    replan: 15,
    retrieval: 15,
  } as Record<string, number>,
  thresholds: {
    excellent: 80,
    good: 60,
    pass: 40,
  },
  maxConcurrent: 3,
  timeout: 120,
})

// Notification settings form
const notificationForm = reactive({
  onComplete: true,
  onFailure: true,
  onLowScore: true,
  lowScoreThreshold: 60,
})

// Methods
const saveGeneralSettings = () => {
  localStorage.setItem('generalSettings', JSON.stringify({
    refreshInterval: generalForm.refreshInterval,
  }))
  ElMessage.success('本地偏好已保存')
}

const resetGeneralSettings = () => {
  generalForm.refreshInterval = 60
}

const saveNotificationSettings = () => {
  localStorage.setItem('notificationSettings', JSON.stringify(notificationForm))
  ElMessage.success('通知偏好已保存（本地）')
}

// Load settings from localStorage
const loadSettings = () => {
  const general = localStorage.getItem('generalSettings')
  if (general) {
    const parsed = JSON.parse(general)
    if (parsed.refreshInterval !== undefined) {
      generalForm.refreshInterval = parsed.refreshInterval
    }
  }

  const notification = localStorage.getItem('notificationSettings')
  if (notification) {
    Object.assign(notificationForm, JSON.parse(notification))
  }
}

// Lifecycle
loadSettings()
</script>

<style scoped lang="scss">
.settings-page {
  .page-header {
    margin-bottom: 20px;

    h2 {
      margin: 0;
    }
  }

  .settings-tabs {
    :deep(.el-tabs__content) {
      padding: 20px 0;
    }
  }

  .weight-config {
    .weight-item {
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 16px;

      .dim-name {
        width: 80px;
        font-size: 14px;
      }
    }
  }

  .threshold-config {
    display: flex;
    flex-direction: column;
    gap: 12px;

    .threshold-item {
      display: flex;
      align-items: center;
      gap: 12px;

      .threshold-label {
        width: 40px;
        font-size: 14px;
      }

      .threshold-unit {
        font-size: 12px;
        color: var(--text-color-secondary);
      }
    }
  }

  .form-hint {
    margin-left: 12px;
    font-size: 12px;
    color: var(--text-color-secondary);
  }

  .about-content {
    text-align: center;
    max-width: 600px;
    margin: 0 auto;

    .about-logo {
      margin-bottom: 20px;
    }

    h3 {
      margin: 0 0 8px 0;
      font-size: 24px;
    }

    .version {
      color: var(--text-color-secondary);
      margin-bottom: 20px;
    }

    .description {
      font-size: 14px;
      line-height: 1.6;
      color: var(--text-color);
      margin-bottom: 30px;
    }

    .features {
      text-align: left;
      margin-bottom: 30px;

      h4 {
        margin: 0 0 16px 0;
        font-size: 16px;
      }

      ul {
        list-style: none;
        padding: 0;

        li {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 12px;
          font-size: 14px;
        }
      }
    }

    .tech-stack {
      text-align: left;

      h4 {
        margin: 0 0 16px 0;
        font-size: 16px;
      }

      .tech-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
    }
  }
}
</style>
