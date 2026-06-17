<template>
  <div class="settings-page">
    <div class="page-header">
      <h2>系统设置</h2>
    </div>

    <el-tabs v-model="activeTab" class="settings-tabs">
      <!-- General Settings -->
      <el-tab-pane label="基本设置" name="general">
        <el-card shadow="never">
          <el-form :model="generalForm" label-width="150px">
            <el-form-item label="默认LLM提供商">
              <el-select v-model="generalForm.llmProvider" style="width: 300px">
                <el-option label="OpenAI" value="openai" />
                <el-option label="Anthropic" value="anthropic" />
              </el-select>
            </el-form-item>

            <el-form-item label="默认模型">
              <el-select v-model="generalForm.llmModel" style="width: 300px">
                <el-option v-for="model in models" :key="model.value" :label="model.label" :value="model.value" />
              </el-select>
            </el-form-item>

            <el-form-item label="API Key">
              <el-input
                v-model="generalForm.apiKey"
                type="password"
                show-password
                placeholder="输入API Key"
                style="width: 400px"
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
              <el-input-number v-model="evaluationForm.maxConcurrent" :min="1" :max="10" />
              <span class="form-hint">同时运行的最大评估数量</span>
            </el-form-item>

            <el-form-item label="超时时间">
              <el-input-number v-model="evaluationForm.timeout" :min="30" :max="600" :step="30" />
              <span class="form-hint">秒</span>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" @click="saveEvaluationSettings">保存设置</el-button>
              <el-button @click="resetEvaluationSettings">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- Notification Settings -->
      <el-tab-pane label="通知设置" name="notification">
        <el-card shadow="never">
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
            <p class="version">版本 1.0.0</p>
            <p class="description">
              一个用于评估AI Agent运行时质量的专业平台，支持对规划、战术决策、工具使用、记忆保持和重规划五个维度进行全面评估。
            </p>

            <div class="features">
              <h4>核心功能</h4>
              <ul>
                <li><el-icon color="#67c23a"><CircleCheck /></el-icon> 多维度评估体系</li>
                <li><el-icon color="#67c23a"><CircleCheck /></el-icon> LangGraph工作流编排</li>
                <li><el-icon color="#67c23a"><CircleCheck /></el-icon> 实时可视化分析</li>
                <li><el-icon color="#67c23a"><CircleCheck /></el-icon> 详细的评估报告</li>
                <li><el-icon color="#67c23a"><CircleCheck /></el-icon> 灵活的配置选项</li>
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
]

// Models list
const models = [
  { label: 'GPT-4 Turbo', value: 'gpt-4-turbo-preview' },
  { label: 'GPT-4', value: 'gpt-4' },
  { label: 'GPT-3.5 Turbo', value: 'gpt-3.5-turbo' },
  { label: 'Claude 3 Opus', value: 'claude-3-opus-20240229' },
  { label: 'Claude 3 Sonnet', value: 'claude-3-sonnet-20240229' },
  { label: 'Claude 3 Haiku', value: 'claude-3-haiku-20240307' },
]

// General settings form
const generalForm = reactive({
  llmProvider: 'openai',
  llmModel: 'gpt-4-turbo-preview',
  apiKey: '',
  refreshInterval: 60,
})

// Evaluation settings form
const evaluationForm = reactive({
  weights: {
    planning: 25,
    tactical: 25,
    tool_use: 20,
    memory: 15,
    replan: 15,
  },
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
  // Save to localStorage or API
  localStorage.setItem('generalSettings', JSON.stringify(generalForm))
  ElMessage.success('基本设置已保存')
}

const resetGeneralSettings = () => {
  generalForm.llmProvider = 'openai'
  generalForm.llmModel = 'gpt-4-turbo-preview'
  generalForm.apiKey = ''
  generalForm.refreshInterval = 60
}

const saveEvaluationSettings = () => {
  localStorage.setItem('evaluationSettings', JSON.stringify(evaluationForm))
  ElMessage.success('评估设置已保存')
}

const resetEvaluationSettings = () => {
  evaluationForm.weights = {
    planning: 25,
    tactical: 25,
    tool_use: 20,
    memory: 15,
    replan: 15,
  }
  evaluationForm.thresholds = {
    excellent: 80,
    good: 60,
    pass: 40,
  }
  evaluationForm.maxConcurrent = 3
  evaluationForm.timeout = 120
}

const saveNotificationSettings = () => {
  localStorage.setItem('notificationSettings', JSON.stringify(notificationForm))
  ElMessage.success('通知设置已保存')
}

// Load settings from localStorage
const loadSettings = () => {
  const general = localStorage.getItem('generalSettings')
  if (general) {
    Object.assign(generalForm, JSON.parse(general))
  }

  const evaluation = localStorage.getItem('evaluationSettings')
  if (evaluation) {
    Object.assign(evaluationForm, JSON.parse(evaluation))
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
