<template>
  <div class="system-inspector">
    <h2>系统检查器</h2>

    <!-- Overview Cards -->
    <el-row :gutter="16" class="overview-cards">
      <el-col :span="5" v-for="card in overviewCards" :key="card.key">
        <el-card shadow="hover">
          <el-statistic :title="card.label" :value="overview[card.key] ?? '-'" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Tabs -->
    <el-tabs v-model="activeTab" type="border-card" class="inspector-tabs">
      <!-- Sessions Tab -->
      <el-tab-pane label="Sessions" name="sessions">
        <el-table :data="sessions" stripe @expand-change="onSessionExpand" row-key="id">
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="expand-content" v-if="sessionDetails[row.id]">
                <h4>Key Facts ({{ sessionDetails[row.id].key_facts?.length || 0 }})</h4>
                <el-tag v-for="(fact, i) in sessionDetails[row.id].key_facts" :key="i" class="fact-tag">
                  {{ fact }}
                </el-tag>
                <span v-if="!sessionDetails[row.id].key_facts?.length" class="text-muted">无</span>

                <h4>Messages ({{ sessionDetails[row.id].messages?.length || 0 }})</h4>
                <div v-for="msg in sessionDetails[row.id].messages" :key="msg.id" class="msg-item">
                  <el-tag :type="msg.role === 'user' ? 'primary' : 'success'" size="small">
                    {{ msg.role }}
                  </el-tag>
                  <span class="msg-content">{{ msg.content?.slice(0, 200) }}</span>
                  <span v-if="msg.wiki_results" class="msg-meta">📚 wiki results</span>
                  <span v-if="msg.extraction" class="msg-meta">📝 extraction</span>
                </div>
              </div>
              <el-skeleton v-else-if="loadingDetails[row.id]" :rows="3" animated />
              <div v-else class="text-muted" style="padding: 12px">加载中...</div>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="名称" min-width="150" />
          <el-table-column prop="message_count" label="消息数" width="80" align="center" />
          <el-table-column label="Key Facts" width="120" align="center">
            <template #default="{ row }">
              <el-badge :value="row.key_facts?.length || 0" type="info" />
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="170" />
          <el-table-column prop="updated_at" label="更新时间" width="170" />
        </el-table>
      </el-tab-pane>

      <!-- Checkpoints Tab -->
      <el-tab-pane label="Checkpoints" name="checkpoints">
        <el-table :data="checkpoints" stripe @expand-change="onCheckpointExpand" row-key="thread_id">
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="expand-content" v-if="checkpointDetails[row.thread_id]">
                <div v-for="(cp, i) in checkpointDetails[row.thread_id].checkpoints" :key="cp.checkpoint_id" class="cp-item">
                  <div class="cp-header">
                    <el-tag size="small">#{{ i + 1 }}</el-tag>
                    <code class="cp-id">{{ cp.checkpoint_id?.slice(0, 16) }}...</code>
                    <span v-if="cp.parent_checkpoint_id" class="cp-parent">
                      ← parent: {{ cp.parent_checkpoint_id?.slice(0, 12) }}
                    </span>
                  </div>

                  <div v-if="cp.checkpoint_summary" class="cp-channels">
                    <el-descriptions :column="2" border size="small">
                      <el-descriptions-item
                        v-for="(val, key) in cp.checkpoint_summary"
                        :key="key"
                        :label="String(key)"
                      >
                        <span class="channel-val">{{ typeof val === 'object' ? JSON.stringify(val) : val }}</span>
                      </el-descriptions-item>
                    </el-descriptions>
                  </div>

                  <div v-if="cp.channels && Object.keys(cp.channels).length" class="cp-writes">
                    <h5>Channel Writes:</h5>
                    <el-tag v-for="(val, key) in cp.channels" :key="key" class="channel-tag" size="small">
                      {{ key }}: {{ typeof val === 'string' ? val.slice(0, 80) : JSON.stringify(val)?.slice(0, 80) }}
                    </el-tag>
                  </div>
                </div>
              </div>
              <el-skeleton v-else-if="loadingCpDetails[row.thread_id]" :rows="4" animated />
              <div v-else class="text-muted" style="padding: 12px">加载中...</div>
            </template>
          </el-table-column>
          <el-table-column prop="thread_id" label="Thread ID" min-width="200">
            <template #default="{ row }">
              <code>{{ row.thread_id?.slice(0, 20) }}...</code>
            </template>
          </el-table-column>
          <el-table-column prop="checkpoint_count" label="Checkpoints" width="110" align="center" />
          <el-table-column label="Latest ID" width="200">
            <template #default="{ row }">
              <code>{{ row.latest_checkpoint_id?.slice(0, 16) }}...</code>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- BM25 Tab -->
      <el-tab-pane label="BM25 Index" name="bm25">
        <el-row :gutter="16" v-if="bm25">
          <el-col :span="8">
            <el-card shadow="hover">
              <el-statistic title="文档数" :value="bm25.total_docs" />
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card shadow="hover">
              <el-statistic title="总 Token 数" :value="bm25.total_tokens" />
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card shadow="hover">
              <el-statistic title="唯一 Token" :value="bm25.unique_tokens" />
            </el-card>
          </el-col>
        </el-row>

        <el-row :gutter="16" style="margin-top: 16px">
          <el-col :span="12">
            <el-card>
              <template #header>Top 30 高频词</template>
              <el-table :data="bm25?.top_tokens || []" size="small" max-height="400">
                <el-table-column prop="token" label="词" />
                <el-table-column prop="count" label="频次" width="80" align="right" />
              </el-table>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card>
              <template #header>路径分布</template>
              <el-table :data="bm25?.path_distribution || []" size="small" max-height="400">
                <el-table-column prop="path" label="路径" min-width="200" />
                <el-table-column prop="chunks" label="分块数" width="80" align="right" />
              </el-table>
            </el-card>
          </el-col>
        </el-row>

        <el-card style="margin-top: 16px">
          <template #header>Chunk 列表 (前 100)</template>
          <el-table :data="bm25?.chunks || []" size="small" max-height="400">
            <el-table-column prop="path" label="路径" min-width="180" />
            <el-table-column prop="title" label="标题" width="150" />
            <el-table-column prop="snippet" label="摘要" min-width="250" />
            <el-table-column prop="chunk_index" label="#" width="60" align="center" />
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- Vectors Tab -->
      <el-tab-pane label="Vectors" name="vectors">
        <el-alert
          title="向量管理请使用专门的向量管理页面"
          type="info"
          :closable="false"
          show-icon
        >
          <router-link to="/vector-admin">前往向量管理 →</router-link>
        </el-alert>
        <el-card style="margin-top: 16px" v-if="overview.vectors > 0">
          <el-statistic title="向量总数" :value="overview.vectors" />
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { debugApi } from '@/api'

const activeTab = ref('sessions')
const overview = reactive<Record<string, number>>({})
const sessions = ref<any[]>([])
const checkpoints = ref<any[]>([])
const bm25 = ref<any>(null)

// 响应式详情数据（用 Map 存储，key 为 id/thread_id）
const sessionDetails = reactive<Record<string, any>>({})
const loadingDetails = reactive<Record<string, boolean>>({})
const checkpointDetails = reactive<Record<string, any>>({})
const loadingCpDetails = reactive<Record<string, boolean>>({})

const overviewCards = [
  { key: 'sessions', label: 'Sessions' },
  { key: 'messages', label: 'Messages' },
  { key: 'checkpoints', label: 'Checkpoints' },
  { key: 'bm25_docs', label: 'BM25 Chunks' },
  { key: 'vectors', label: 'Vectors' },
]

onMounted(async () => {
  try {
    Object.assign(overview, await debugApi.getOverview())
  } catch { /* ignore */ }
  loadSessions()
  loadCheckpoints()
  loadBm25()
})

async function loadSessions() {
  try { sessions.value = await debugApi.getSessions() as any } catch { /* */ }
}

async function loadCheckpoints() {
  try { checkpoints.value = await debugApi.getCheckpoints() as any } catch { /* */ }
}

async function loadBm25() {
  try { bm25.value = await debugApi.getBm25Stats() } catch { /* */ }
}

async function onSessionExpand(row: any, expandedRows: any[]) {
  const isExpanded = expandedRows.some((r: any) => r.id === row.id)
  if (isExpanded && !sessionDetails[row.id]) {
    loadingDetails[row.id] = true
    try {
      sessionDetails[row.id] = await debugApi.getSessionDetail(row.id)
    } catch {
      sessionDetails[row.id] = { messages: [], key_facts: [] }
    } finally {
      loadingDetails[row.id] = false
    }
  }
}

async function onCheckpointExpand(row: any, expandedRows: any[]) {
  const isExpanded = expandedRows.some((r: any) => r.thread_id === row.thread_id)
  if (isExpanded && !checkpointDetails[row.thread_id]) {
    loadingCpDetails[row.thread_id] = true
    try {
      checkpointDetails[row.thread_id] = await debugApi.getCheckpointDetail(row.thread_id)
    } catch {
      checkpointDetails[row.thread_id] = { checkpoints: [] }
    } finally {
      loadingCpDetails[row.thread_id] = false
    }
  }
}
</script>

<style scoped>
.system-inspector {
  padding: 0;
}
.overview-cards {
  margin-bottom: 20px;
}
.inspector-tabs {
  margin-top: 8px;
}
.expand-content {
  padding: 12px 20px;
}
.expand-content h4 {
  margin: 12px 0 8px;
  font-size: 14px;
}
.fact-tag {
  margin: 2px 4px;
}
.text-muted {
  color: #999;
  font-size: 12px;
}
.eval-link {
  margin: 8px 0;
}
.msg-item {
  padding: 6px 0;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.msg-content {
  flex: 1;
  font-size: 13px;
  color: #333;
}
.msg-meta {
  font-size: 11px;
  color: #999;
}
.cp-item {
  padding: 10px 0;
  border-bottom: 1px solid #eee;
}
.cp-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.cp-id {
  font-size: 12px;
  color: #666;
}
.cp-parent {
  font-size: 11px;
  color: #999;
}
.cp-channels {
  margin: 8px 0;
}
.channel-val {
  font-size: 12px;
  word-break: break-all;
}
.cp-writes h5 {
  font-size: 12px;
  margin: 8px 0 4px;
}
.channel-tag {
  margin: 2px;
  max-width: 400px;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
