<template>
  <div class="vector-admin" v-loading="loading">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <h2>Milvus 向量管理</h2>
        <span class="subtitle">查看 Wiki Agent 写入 Milvus 的分块向量与元数据</span>
      </div>
      <div class="header-right">
        <el-button @click="refreshAll" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- Stats Cards -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="4" v-for="stat in statCards" :key="stat.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">{{ stat.label }}</div>
          <div class="stat-value" :class="{ small: stat.small }">
            <template v-if="stat.badge !== undefined">
              <el-tag :type="stat.badge ? 'success' : 'danger'" size="small">{{ stat.badge ? '可用' : '不可用' }}</el-tag>
            </template>
            <template v-else>{{ stat.value }}</template>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Filters -->
    <el-card shadow="hover" class="filter-card">
      <el-row :gutter="12" align="bottom">
        <el-col :span="10">
          <div class="filter-label">按页面路径筛选</div>
          <el-select v-model="pathFilter" placeholder="全部页面" clearable filterable style="width:100%">
            <el-option label="全部页面" value="" />
            <el-option v-for="p in paths" :key="p.path" :label="`${p.path} (${p.chunk_count})`" :value="p.path" />
          </el-select>
        </el-col>
        <el-col :span="10">
          <div class="filter-label">文档关键词</div>
          <el-input v-model="keywordFilter" placeholder="搜索 document 字段..." @keyup.enter="search" clearable />
        </el-col>
        <el-col :span="4">
          <el-button type="primary" @click="search" style="width:100%">查询</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- Chunks Table -->
    <el-card shadow="hover" class="table-card">
      <el-table :data="chunks" stripe max-height="520" style="width:100%">
        <el-table-column prop="chunk_id" label="Chunk ID" width="200">
          <template #default="{ row }">
            <code>{{ row.chunk_id }}</code>
          </template>
        </el-table-column>
        <el-table-column label="路径 / 标题" min-width="200">
          <template #default="{ row }">
            <div><code>{{ row.path }}</code></div>
            <div class="text-muted">{{ row.title }}</div>
          </template>
        </el-table-column>
        <el-table-column label="分块" width="100">
          <template #default="{ row }">
            {{ row.chunk_index + 1 }} / {{ row.total_chunks }}
          </template>
        </el-table-column>
        <el-table-column prop="tags" label="标签" width="120">
          <template #default="{ row }">
            {{ row.tags || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">
            <code>{{ row.updated_at || '—' }}</code>
          </template>
        </el-table-column>
        <el-table-column label="内容预览" min-width="250" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.document_preview }}
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <span class="page-info">显示 {{ fromRow }}–{{ toRow }} / 共 {{ total }} 条</span>
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="loadChunks"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'

const loading = ref(false)
const pathFilter = ref('')
const keywordFilter = ref('')
const currentPage = ref(1)
const pageSize = 20
const total = ref(0)
const chunks = ref<any[]>([])
const paths = ref<{ path: string; chunk_count: number }[]>([])

const fromRow = computed(() => (total.value === 0 ? 0 : (currentPage.value - 1) * pageSize + 1))
const toRow = computed(() => Math.min(currentPage.value * pageSize, total.value))

const statCards = ref([
  { label: '集合', value: '—', small: true },
  { label: 'URI', value: '—', small: true },
  { label: '维度', value: '—' },
  { label: '分块总数', value: '—' },
  { label: '页面数', value: '—' },
  { label: '状态', value: '—', badge: false },
])

async function loadStats() {
  try {
    const res = await fetch('/api/wiki/vector-stats')
    const data = await res.json()
    statCards.value = [
      { label: '集合', value: data.collection, small: true },
      { label: 'URI', value: data.uri, small: true },
      { label: '维度', value: String(data.embedding_dim) },
      { label: '分块总数', value: String(data.total_chunks) },
      { label: '页面数', value: String(data.unique_pages) },
      { label: '状态', value: '', badge: data.available },
    ]
  } catch {}
}

async function loadPaths() {
  try {
    const res = await fetch('/api/wiki/vector-paths')
    const data = await res.json()
    paths.value = data.items || []
  } catch {}
}

async function loadChunks(page = 1) {
  currentPage.value = page
  const offset = (page - 1) * pageSize
  const params = new URLSearchParams({ offset: String(offset), limit: String(pageSize) })
  if (pathFilter.value) params.set('path', pathFilter.value)
  if (keywordFilter.value) params.set('keyword', keywordFilter.value)

  try {
    const res = await fetch(`/api/wiki/vector-chunks?${params}`)
    const data = await res.json()
    chunks.value = data.items || []
    total.value = data.total
  } catch {
    chunks.value = []
    total.value = 0
  }
}

function search() {
  currentPage.value = 1
  loadChunks(1)
}

async function refreshAll() {
  loading.value = true
  await Promise.all([loadStats(), loadPaths(), loadChunks(currentPage.value)])
  loading.value = false
}

onMounted(refreshAll)
</script>

<style scoped lang="scss">
.vector-admin {
  padding: 20px;

  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;

    .header-left {
      h2 { margin: 0; font-size: 1.5rem; }
      .subtitle { color: #909399; font-size: 0.875rem; margin-top: 4px; display: block; }
    }
  }

  .stats-row {
    margin-bottom: 16px;

    .stat-card {
      :deep(.el-card__body) { padding: 16px; }
      .stat-label { color: #909399; font-size: 0.75rem; text-transform: uppercase; }
      .stat-value {
        font-size: 1.3rem; font-weight: 600; margin-top: 6px; word-break: break-all;
        &.small { font-size: 0.9rem; font-weight: 500; }
      }
    }
  }

  .filter-card {
    margin-bottom: 16px;
    :deep(.el-card__body) { padding: 16px; }
    .filter-label { color: #909399; font-size: 0.8rem; margin-bottom: 6px; }
  }

  .table-card {
    :deep(.el-card__body) { padding: 0; }

    .pagination-wrap {
      display: flex; align-items: center; justify-content: space-between;
      padding: 12px 16px;
      .page-info { color: #909399; font-size: 0.875rem; }
    }
  }

  .text-muted { color: #909399; font-size: 0.8rem; }
  code { font-size: 0.8rem; }
}
</style>
