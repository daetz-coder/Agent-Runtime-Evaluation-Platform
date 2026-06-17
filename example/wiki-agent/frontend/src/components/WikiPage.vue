<template>
  <div class="wiki-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="page-meta">
        <span class="meta-source">{{ page.source }}</span>
        <span class="meta-dot">·</span>
        <span class="meta-date">更新于 {{ formatDate(page.updated) }}</span>
        <span v-if="page.tags.length" class="meta-dot">·</span>
        <span v-for="(tag, i) in page.tags" :key="i" class="meta-tag">{{ tag }}</span>
      </div>
      <div class="page-actions">
        <button class="btn-ghost" @click="toggleEdit">
          {{ isEditing ? "取消" : "编辑" }}
        </button>
        <button v-if="isEditing" class="btn-primary" @click="handleSave">保存</button>
        <button class="btn-ghost btn-danger" @click="$emit('delete', page.path)">删除</button>
      </div>
    </div>

    <!-- 阅读模式 -->
    <div v-if="!isEditing" class="page-content">
      <div class="page-body markdown-body" v-html="renderedContent"></div>

      <!-- 关联条目 -->
      <div v-if="page.links.length" class="page-links">
        <h3>关联条目</h3>
        <div class="links-list">
          <a
            v-for="link in page.links"
            :key="link"
            class="link-item"
            @click.prevent="$emit('select', link)"
          >
            {{ formatLinkName(link) }}
          </a>
        </div>
      </div>
    </div>

    <!-- 编辑模式 -->
    <div v-else class="page-edit">
      <div class="edit-field">
        <label>标题</label>
        <input v-model="editTitle" class="edit-input" />
      </div>
      <div class="edit-field">
        <label>标签</label>
        <div class="tags-editor">
          <span v-for="(tag, i) in editTags" :key="i" class="tag-chip">
            {{ tag }}
            <button class="tag-remove" @click="editTags.splice(i, 1)">×</button>
          </span>
          <input
            v-model="newTag"
            class="tag-input"
            placeholder="添加标签..."
            @keyup.enter="addTag"
          />
        </div>
      </div>
      <div class="edit-field edit-field-grow">
        <label>内容 <span class="label-hint">（Markdown 格式）</span></label>
        <textarea
          v-model="editContent"
          class="edit-textarea"
          placeholder="输入知识内容..."
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from "vue";

const props = defineProps({ page: Object });
const emit = defineEmits(["save", "delete", "edit"]);

const isEditing = ref(false);
const editTitle = ref("");
const editContent = ref("");
const editTags = ref([]);
const newTag = ref("");

watch(
  () => props.page,
  (p) => {
    editTitle.value = p.title;
    editContent.value = p.content;
    editTags.value = [...p.tags];
    isEditing.value = false;
  },
  { immediate: true }
);

function toggleEdit() {
  isEditing.value = !isEditing.value;
  if (isEditing.value) {
    editTitle.value = props.page.title;
    editContent.value = props.page.content;
    editTags.value = [...props.page.tags];
  }
}

function addTag() {
  const tag = newTag.value.trim();
  if (tag && !editTags.value.includes(tag)) {
    editTags.value.push(tag);
  }
  newTag.value = "";
}

function handleSave() {
  emit("save", {
    path: props.page.path,
    data: {
      title: editTitle.value,
      content: editContent.value,
      tags: editTags.value,
    },
  });
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  const now = new Date();
  const diff = now - d;
  if (diff < 60000) return "刚刚";
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
  return d.toLocaleDateString("zh-CN");
}

function formatLinkName(path) {
  return path.replace(".md", "").replace(/\//g, " > ").replace(/-/g, " ");
}

// 简单 Markdown 渲染
const renderedContent = computed(() => {
  let html = props.page.content
    // 代码块
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="lang-$1">$2</code></pre>')
    // 标题
    .replace(/^#### (.+)$/gm, "<h4>$1</h4>")
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    // 粗体/斜体
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    // 行内代码
    .replace(/`(.+?)`/g, "<code>$1</code>")
    // 链接
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank">$1</a>')
    // 列表
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    // 换行
    .replace(/\n\n/g, "</p><p>")
    .replace(/\n/g, "<br>");
  return "<p>" + html + "</p>";
});
</script>

<style scoped>
.wiki-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── 页面头部 ── */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 20px 32px 16px;
  border-bottom: 1px solid #f0f0f0;
  background: #fff;
  flex-shrink: 0;
}

.page-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #999;
  flex-wrap: wrap;
}

.meta-dot {
  color: #ddd;
}

.meta-tag {
  background: #f0f0f0;
  padding: 1px 8px;
  border-radius: 10px;
  color: #666;
}

.page-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.btn-ghost {
  padding: 5px 12px;
  background: transparent;
  border: 1px solid #d9d9d9;
  border-radius: 5px;
  cursor: pointer;
  font-size: 12px;
  color: #555;
  transition: all 0.2s;
}

.btn-ghost:hover {
  border-color: #4a90d9;
  color: #4a90d9;
}

.btn-primary {
  padding: 5px 16px;
  background: #4a90d9;
  color: #fff;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-size: 12px;
}

.btn-danger:hover {
  border-color: #d93025;
  color: #d93025;
}

/* ── 阅读模式 ── */
.page-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
}

.page-body {
  max-width: 780px;
  line-height: 1.8;
  font-size: 15px;
}

.page-body :deep(h1) {
  font-size: 28px;
  font-weight: 700;
  margin: 32px 0 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e8e8e8;
}

.page-body :deep(h2) {
  font-size: 22px;
  font-weight: 600;
  margin: 28px 0 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid #f0f0f0;
}

.page-body :deep(h3) {
  font-size: 18px;
  font-weight: 600;
  margin: 24px 0 10px;
}

.page-body :deep(h4) {
  font-size: 16px;
  font-weight: 600;
  margin: 20px 0 8px;
}

.page-body :deep(p) {
  margin: 12px 0;
}

.page-body :deep(code) {
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 13px;
  font-family: "SF Mono", Monaco, monospace;
}

.page-body :deep(pre) {
  background: #f5f5f5;
  padding: 16px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 16px 0;
}

.page-body :deep(pre code) {
  background: none;
  padding: 0;
}

.page-body :deep(li) {
  margin: 4px 0;
  padding-left: 8px;
  list-style: disc;
  margin-left: 20px;
}

.page-body :deep(strong) {
  font-weight: 600;
}

.page-body :deep(a) {
  color: #4a90d9;
  text-decoration: none;
}

.page-body :deep(a:hover) {
  text-decoration: underline;
}

/* ── 关联条目 ── */
.page-links {
  margin-top: 40px;
  padding-top: 20px;
  border-top: 1px solid #e8e8e8;
}

.page-links h3 {
  font-size: 14px;
  font-weight: 600;
  color: #666;
  margin-bottom: 12px;
}

.links-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.link-item {
  padding: 4px 12px;
  background: #f0f7ff;
  color: #4a90d9;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
  text-decoration: none;
}

.link-item:hover {
  background: #e0efff;
}

/* ── 编辑模式 ── */
.page-edit {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 20px 32px;
  gap: 16px;
  overflow: hidden;
}

.edit-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.edit-field-grow {
  flex: 1;
  overflow: hidden;
}

.edit-field label {
  font-size: 13px;
  font-weight: 500;
  color: #666;
}

.label-hint {
  font-weight: 400;
  color: #999;
}

.edit-input {
  padding: 8px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 15px;
  outline: none;
}

.edit-input:focus {
  border-color: #4a90d9;
}

.tags-editor {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 10px;
  background: #e8f0fe;
  color: #1a73e8;
  border-radius: 12px;
  font-size: 12px;
}

.tag-remove {
  background: none;
  border: none;
  cursor: pointer;
  color: #1a73e8;
  font-size: 14px;
  line-height: 1;
  padding: 0;
}

.tag-input {
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 12px;
  outline: none;
  min-width: 100px;
}

.edit-textarea {
  flex: 1;
  padding: 16px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
  font-family: "SF Mono", Monaco, "Cascadia Code", monospace;
  line-height: 1.6;
  resize: none;
  outline: none;
}

.edit-textarea:focus {
  border-color: #4a90d9;
}
</style>
