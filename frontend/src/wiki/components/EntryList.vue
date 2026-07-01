<template>
  <div class="entry-list">
    <div v-if="title" class="list-header">
      <h3>{{ title }}</h3>
      <span class="list-count">{{ entries.length }} 条</span>
    </div>

    <div v-if="entries.length === 0" class="list-empty">暂无词条</div>

    <div v-else class="list-grid">
      <div
        v-for="entry in entries"
        :key="entry.path"
        class="entry-card"
        @click="$emit('select', entry.path)"
      >
        <div class="card-title">{{ entry.title }}</div>
        <div v-if="entry.snippet" class="card-snippet">{{ entry.snippet }}</div>
        <div class="card-meta">
          <span v-if="entry.score" class="card-score">相关度 {{ Math.round(entry.score * 100) }}%</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: "" },
  entries: { type: Array, default: () => [] },
});

defineEmits(["select"]);
</script>

<style scoped>
.entry-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px 32px;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.list-header h3 {
  font-size: 16px;
  font-weight: 600;
}

.list-count {
  font-size: 13px;
  color: #888;
}

.list-empty {
  text-align: center;
  padding: 40px;
  color: #999;
}

.list-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.entry-card {
  padding: 14px 16px;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.entry-card:hover {
  border-color: #4a90d9;
  box-shadow: 0 2px 8px rgba(74, 144, 217, 0.1);
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 6px;
}

.card-snippet {
  font-size: 13px;
  color: #666;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-meta {
  display: flex;
  gap: 12px;
  margin-top: 8px;
  font-size: 11px;
  color: #999;
}
</style>
