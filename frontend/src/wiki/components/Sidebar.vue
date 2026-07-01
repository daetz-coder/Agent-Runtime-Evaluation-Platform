<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <span class="logo">📖</span>
      <span class="logo-text">知识库</span>
    </div>

    <div class="sidebar-search">
      <input
        v-model="filter"
        placeholder="筛选分类..."
        class="filter-input"
      />
    </div>

    <nav class="sidebar-nav">
      <CategoryNode
        v-for="cat in filteredCategories"
        :key="cat.name"
        :category="cat"
        :currentPath="currentPath"
        :depth="0"
        @select="$emit('select', $event)"
      />
    </nav>

    <!-- 标签区域 -->
    <div class="sidebar-tags">
      <div class="tags-toggle" @click="showTags = !showTags">
        <span>🏷️ 标签</span>
        <span class="toggle-arrow" :class="{ expanded: showTags }">▶</span>
      </div>
      <div v-if="showTags" class="tags-content">
        <TagPanel @select="$emit('select', $event)" @filter="$emit('tagFilter', $event)" />
      </div>
    </div>

    <div class="sidebar-footer">
      <button class="btn-new" @click="$emit('create')">+ 新建条目</button>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed } from "vue";
import CategoryNode from "./CategoryNode.vue";
import TagPanel from "./TagPanel.vue";

const props = defineProps({
  categories: Array,
  currentPath: String,
});

defineEmits(["select", "create", "tagFilter"]);

const filter = ref("");
const showTags = ref(false);

const filteredCategories = computed(() => {
  if (!filter.value.trim()) return props.categories;
  const q = filter.value.toLowerCase();
  return props.categories.filter(
    (cat) =>
      cat.name.toLowerCase().includes(q) ||
      cat.children?.some((c) => c.name.toLowerCase().includes(q))
  );
});
</script>

<style scoped>
.sidebar {
  width: 260px;
  background: #fff;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 16px 12px;
  border-bottom: 1px solid #f0f0f0;
}

.logo { font-size: 20px; }

.logo-text {
  font-size: 15px;
  font-weight: 600;
  color: #1a1a1a;
}

.sidebar-search {
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
}

.filter-input {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  font-size: 12px;
  outline: none;
  background: #fafafa;
}

.filter-input:focus {
  border-color: #4a90d9;
  background: #fff;
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

/* ── 标签区域 ── */
.sidebar-tags {
  border-top: 1px solid #f0f0f0;
  flex-shrink: 0;
}

.tags-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: #666;
  transition: background 0.15s;
}

.tags-toggle:hover {
  background: #f8f9fa;
}

.toggle-arrow {
  font-size: 10px;
  transition: transform 0.2s;
}

.toggle-arrow.expanded {
  transform: rotate(90deg);
}

.tags-content {
  padding: 0 14px 10px;
  max-height: 200px;
  overflow-y: auto;
}

.sidebar-footer {
  padding: 12px;
  border-top: 1px solid #f0f0f0;
}

.btn-new {
  width: 100%;
  padding: 8px;
  background: #f8f9fa;
  border: 1px dashed #d0d0d0;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: #666;
  transition: all 0.2s;
}

.btn-new:hover {
  border-color: #4a90d9;
  color: #4a90d9;
  background: #f0f7ff;
}
</style>
