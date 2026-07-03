<template>
  <div class="tag-panel">
    <div class="tag-header">
      <h3>标签</h3>
      <button v-if="selectedTag" class="btn-clear" @click="clearFilter">清除筛选</button>
    </div>

    <div v-if="loading" class="tag-loading">加载中...</div>

    <div v-else class="tag-cloud">
      <span
        v-for="tag in tags"
        :key="tag.tag"
        class="tag-item"
        :class="{ active: selectedTag === tag.tag }"
        :style="{ fontSize: tagFontSize(tag.count) + 'px' }"
        @click="selectTag(tag)"
      >
        {{ tag.tag }}
        <span class="tag-count">{{ tag.count }}</span>
      </span>
    </div>

    <div v-if="selectedTag && selectedPages.length" class="tag-pages">
      <div class="tag-pages-title">「{{ selectedTag }}」关联页面：</div>
      <div
        v-for="page in selectedPages"
        :key="page"
        class="tag-page-item"
        @click="$emit('select', page)"
      >
        {{ formatPath(page) }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { wikiApi } from "../api/index.js";

const emit = defineEmits(["select", "filter"]);

const loading = ref(true);
const tags = ref([]);
const selectedTag = ref("");

async function loadTags() {
  loading.value = true;
  try {
    tags.value = await wikiApi.getTags();
  } catch (e) {
    console.error("加载标签失败:", e);
  } finally {
    loading.value = false;
  }
}

const selectedPages = computed(() => {
  if (!selectedTag.value) return [];
  const tag = tags.value.find((t) => t.tag === selectedTag.value);
  return tag?.pages || [];
});

function tagFontSize(count) {
  const maxCount = Math.max(...tags.value.map((t) => t.count), 1);
  const ratio = count / maxCount;
  return Math.round(12 + ratio * 10); // 12px ~ 22px
}

function selectTag(tag) {
  if (selectedTag.value === tag.tag) {
    clearFilter();
  } else {
    selectedTag.value = tag.tag;
    emit("filter", tag.tag);
  }
}

function clearFilter() {
  selectedTag.value = "";
  emit("filter", "");
}

function formatPath(path) {
  return path.replace(".md", "").replace(/\//g, " > ");
}

onMounted(loadTags);
</script>

<style scoped>
.tag-panel {
  padding: 0;
}

.tag-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.tag-header h3 {
  font-size: 13px;
  font-weight: 600;
  color: #666;
  margin: 0;
}

.btn-clear {
  background: none;
  border: none;
  color: #4a90d9;
  cursor: pointer;
  font-size: 11px;
  padding: 0;
}

.btn-clear:hover {
  text-decoration: underline;
}

.tag-loading {
  color: #999;
  font-size: 12px;
  padding: 8px 0;
}

.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.tag-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 10px;
  background: #f0f0f0;
  border-radius: 12px;
  cursor: pointer;
  color: #555;
  transition: all 0.15s;
  white-space: nowrap;
}

.tag-item:hover {
  background: #e0efff;
  color: #4a90d9;
}

.tag-item.active {
  background: #4a90d9;
  color: #fff;
}

.tag-count {
  font-size: 10px;
  opacity: 0.6;
}

.tag-pages {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid #f0f0f0;
}

.tag-pages-title {
  font-size: 12px;
  color: #888;
  margin-bottom: 6px;
}

.tag-page-item {
  font-size: 12px;
  color: #4a90d9;
  padding: 3px 0;
  cursor: pointer;
  transition: color 0.15s;
}

.tag-page-item:hover {
  color: #1d4ed8;
  text-decoration: underline;
}
</style>
