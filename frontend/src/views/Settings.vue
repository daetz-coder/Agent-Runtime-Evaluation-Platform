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

      <!-- System Status -->
      <el-tab-pane label="系统状态" name="status">
        <el-card shadow="never" v-loading="statusLoading">
          <div class="status-actions">
            <el-button type="primary" @click="loadSystemStatus">刷新状态</el-button>
            <el-button @click="router.push('/vector-admin')">打开向量管理</el-button>
          </div>

          <el-descriptions v-if="systemStatus" :column="2" border style="margin-top: 16px">
            <el-descriptions-item label="整体状态">
              <el-tag :type="systemStatus.status === 'healthy' ? 'success' : 'warning'">
                {{ systemStatus.status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="数据库">{{ systemStatus.database }}</el-descriptions-item>
            <el-descriptions-item label="Milvus">
              <el-tag :type="systemStatus.wiki?.milvus?.available ? 'success' : 'danger'" size="small">
                {{ systemStatus.wiki?.milvus?.available ? '可用' : '不可用' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="向量分块">{{ systemStatus.wiki?.milvus?.total_chunks ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="BM25 分块">{{ systemStatus.wiki?.bm25_chunks ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="知识页数">{{ systemStatus.wiki?.knowledge_pages ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="Milvus URI" :span="2">
              <code>{{ systemStatus.wiki?.milvus?.uri }}</code>
            </el-descriptions-item>
            <el-descriptions-item label="知识库目录" :span="2">
              <code>{{ systemStatus.wiki?.knowledge_dir }}</code>
            </el-descriptions-item>
          </el-descriptions>

          <el-alert
            v-if="systemStatus?.wiki?.milvus?.error"
            :title="systemStatus.wiki.milvus.error"
            type="error"
            show-icon
            :closable="false"
            style="margin-top: 16px"
          />
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
                <el-tag>Milvus</el-tag>
              </div>
            </div>
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Cpu, CircleCheck } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { systemApi } from '@/api'

const router = useRouter()
const activeTab = ref('general')
const statusLoading = ref(false)
const systemStatus = ref<any>(null)

// General settings form (local UI preferences only)
const generalForm = reactive({
  llmProvider: 'deepseek',
  llmModel: 'deepseek-chat',
  apiKey: '',
  refreshInterval: 60,
})

// Notification settings form
const notificationForm = reactive({
  onComplete: true,
  onFailure: true,
  onLowScore: true,
  lowScoreThreshold: 60,
})

const loadSystemStatus = async () => {
  statusLoading.value = true
  try {
    systemStatus.value = await systemApi.getHealth()
  } catch (err: any) {
    ElMessage.error(err.message || '加载系统状态失败')
  } finally {
    statusLoading.value = false
  }
}

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
  try {
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
  } catch {
    localStorage.removeItem('generalSettings')
    localStorage.removeItem('notificationSettings')
  }
}

// Lifecycle
loadSettings()
onMounted(loadSystemStatus)
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

  .status-actions {
    display: flex;
    gap: 8px;
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
