<template>
  <div class="wiki-page">
    <!-- 面包屑导航 -->
    <div v-if="!isEditing" class="breadcrumb">
      <span class="breadcrumb-item" @click="$emit('navigate', '')">知识库</span>
      <template v-for="(seg, i) in breadcrumbSegments" :key="i">
        <span class="breadcrumb-sep">/</span>
        <span
          class="breadcrumb-item"
          :class="{ active: i === breadcrumbSegments.length - 1 }"
          @click="seg.path && $emit('navigate', seg.path)"
        >{{ seg.name }}</span>
      </template>
    </div>

    <!-- 页面头部 -->
    <div class="page-header">
      <div class="page-header-row">
        <div class="page-meta">
          <span v-if="page.category" class="meta-category">{{ page.category }}</span>
          <span v-if="page.category" class="meta-dot">·</span>
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
      <div v-if="page.summary && !isEditing" class="page-summary">{{ page.summary }}</div>
    </div>

    <!-- 阅读模式 -->
    <div v-if="!isEditing" class="page-content">
      <div class="page-body markdown-body" v-html="renderedContent" @click="handleContentClick"></div>

      <!-- 反向链接 -->
      <div v-if="backlinks.length" class="backlinks-panel">
        <h3 class="backlinks-title">
          <span class="backlinks-icon">🔗</span>
          反向链接 ({{ backlinks.length }})
        </h3>
        <div class="backlinks-list">
          <div
            v-for="bl in backlinks"
            :key="bl.path"
            class="backlink-item"
            @click="$emit('navigate', bl.path)"
          >
            <div class="backlink-title">{{ bl.title }}</div>
            <div class="backlink-snippet">{{ bl.snippet }}</div>
          </div>
        </div>
      </div>

      <!-- 关联条目 -->
      <div v-if="page.links.length" class="page-links">
        <h3>关联条目</h3>
        <div class="links-list">
          <a
            v-for="link in page.links"
            :key="link"
            class="link-item"
            @click.prevent="$emit('navigate', link)"
          >
            {{ formatLinkName(link) }}
          </a>
        </div>
      </div>
    </div>

    <!-- 编辑模式：分栏编辑器 -->
    <div v-else class="page-edit">
      <div class="edit-meta-row">
        <div class="edit-field edit-field-title">
          <label>标题</label>
          <input v-model="editTitle" class="edit-input" />
        </div>
        <div class="edit-field edit-field-summary">
          <label>摘要/定义</label>
          <input v-model="editSummary" class="edit-input" placeholder="一句话定义" />
        </div>
      </div>
      <div class="edit-meta-row">
        <div class="edit-field edit-field-category">
          <label>分类</label>
          <input v-model="editCategory" class="edit-input" placeholder="如：技术/编程语言" />
        </div>
        <div class="edit-field edit-field-tags">
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
      </div>

      <!-- 工具栏 + 分栏 -->
      <div class="edit-split">
        <div class="edit-pane">
          <MarkdownToolbar @insert="handleToolbarInsert" />
          <textarea
            ref="textareaRef"
            v-model="editContent"
            class="edit-textarea"
            placeholder="输入 Markdown 内容... 支持 [[页面名称]] 语法"
            @paste="handlePaste"
          />
        </div>
        <div class="preview-pane">
          <div class="preview-header">预览</div>
          <div class="preview-body markdown-body" v-html="editPreview"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed, onMounted } from "vue";
import { marked } from "marked";
import { wikiApi } from "../api/index.js";
import MarkdownToolbar from "./MarkdownToolbar.vue";

const props = defineProps({ page: Object });
const emit = defineEmits(["save", "delete", "navigate"]);

const isEditing = ref(false);
const editTitle = ref("");
const editSummary = ref("");
const editCategory = ref("");
const editContent = ref("");
const editTags = ref([]);
const newTag = ref("");
const backlinks = ref([]);
const textareaRef = ref(null);

// ── Marked 配置 + WikiLink 扩展 ──

const wikilinkExt = {
  name: "wikilink",
  level: "inline",
  start(src) {
    return src.match(/\[\[/)?.index;
  },
  tokenizer(src) {
    const match = src.match(/^\[\[([^\]]+)\]\]/);
    if (match) {
      return { type: "wikilink", raw: match[0], text: match[1].trim() };
    }
  },
  renderer(token) {
    return `<a class="wikilink" data-target="${token.text}" href="javascript:void(0)">${token.text}</a>`;
  },
};

marked.use({ extensions: [wikilinkExt] });

const renderedContent = computed(() => marked.parse(props.page.content || ""));
const editPreview = computed(() => marked.parse(editContent.value || ""));

// ── 面包屑 ──

const breadcrumbSegments = computed(() => {
  const path = props.page?.path || "";
  const parts = path.replace(".md", "").split("/").filter(Boolean);
  return parts.map((part, i) => ({
    name: part.replace(/-/g, " "),
    path: i < parts.length - 1 ? parts.slice(0, i + 1).join("/") + ".md" : null,
  }));
});

// ── 加载反向链接 ──

async function loadBacklinks() {
  if (!props.page?.path) {
    backlinks.value = [];
    return;
  }
  try {
    backlinks.value = await wikiApi.getBacklinks(props.page.path);
  } catch (e) {
    backlinks.value = [];
  }
}

// ── 监听页面变化 ──

watch(
  () => props.page,
  (p) => {
    editTitle.value = p.title;
    editSummary.value = p.summary || "";
    editCategory.value = p.category || "";
    editContent.value = p.content;
    editTags.value = [...p.tags];
    isEditing.value = false;
    loadBacklinks();
  },
  { immediate: true }
);

onMounted(loadBacklinks);

// ── 编辑逻辑 ──

function toggleEdit() {
  isEditing.value = !isEditing.value;
  if (isEditing.value) {
    editTitle.value = props.page.title;
    editSummary.value = props.page.summary || "";
    editCategory.value = props.page.category || "";
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
      summary: editSummary.value,
      category: editCategory.value,
      content: editContent.value,
      tags: editTags.value,
    },
  });
}

// ── 工具栏插入 ──

function handleToolbarInsert(syntax) {
  const ta = textareaRef.value;
  if (!ta) return;

  const start = ta.selectionStart;
  const end = ta.selectionEnd;
  const text = editContent.value;
  const selected = text.substring(start, end);

  // 如果语法是 wrap 类型（如 **、*、`），包裹选中文本
  const wrapChars = ["**", "*", "`", "[[", "["];
  const isWrap = wrapChars.includes(syntax);
  const suffixMap = { "**": "**", "*": "*", "`": "`", "[[": "]]", "[": "](url)" };
  const suffix = suffixMap[syntax] || "";

  let insertText;
  if (isWrap && selected) {
    insertText = syntax + selected + suffix;
  } else if (syntax.endsWith(" ") || syntax.startsWith("\n")) {
    // 前缀类型（标题、列表、分割线）
    insertText = syntax + selected;
  } else if (suffix) {
    insertText = syntax + (selected || "文本") + suffix;
  } else {
    insertText = syntax + selected;
  }

  editContent.value = text.substring(0, start) + insertText + text.substring(end);

  // 恢复光标位置
  const newPos = start + insertText.length;
  requestAnimationFrame(() => {
    ta.focus();
    ta.setSelectionRange(newPos, newPos);
  });
}

// ── 图片粘贴 ──

async function handlePaste(e) {
  const items = e.clipboardData?.items;
  if (!items) return;

  for (const item of items) {
    if (item.type.startsWith("image/")) {
      e.preventDefault();
      const file = item.getAsFile();
      if (!file) continue;

      try {
        const result = await wikiApi.uploadFile(file);
        const imgMarkdown = `![图片](${result.url})`;
        const ta = textareaRef.value;
        const pos = ta?.selectionStart || editContent.value.length;
        editContent.value =
          editContent.value.substring(0, pos) +
          imgMarkdown +
          editContent.value.substring(pos);
      } catch (err) {
        console.error("图片上传失败:", err);
      }
      break;
    }
  }
}

// ── WikiLink 点击 ──

function handleContentClick(e) {
  const link = e.target.closest("a.wikilink");
  if (link) {
    e.preventDefault();
    const target = link.dataset.target;
    if (target) emit("navigate", target);
  }
}

// ── 工具函数 ──

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
</script>

<style scoped>
.wiki-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── 面包屑 ── */
.breadcrumb {
  padding: 10px 32px 0;
  font-size: 12px;
  color: #999;
  flex-shrink: 0;
}

.breadcrumb-item {
  cursor: pointer;
  transition: color 0.15s;
}

.breadcrumb-item:hover {
  color: #4a90d9;
}

.breadcrumb-item.active {
  color: #333;
  cursor: default;
}

.breadcrumb-sep {
  margin: 0 4px;
  color: #ddd;
}

/* ── 页面头部 ── */
.page-header {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.page-header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 12px 32px 12px;
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

.meta-dot { color: #ddd; }

.meta-category {
  background: #e8f5e9;
  color: #2e7d32;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 11px;
}

.meta-tag {
  background: #f0f0f0;
  padding: 1px 8px;
  border-radius: 10px;
  color: #666;
}

.page-summary {
  font-size: 14px;
  color: #666;
  line-height: 1.6;
  padding: 0 4px;
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

.page-body :deep(h1) { font-size: 28px; font-weight: 700; margin: 32px 0 16px; padding-bottom: 8px; border-bottom: 1px solid #e8e8e8; }
.page-body :deep(h2) { font-size: 22px; font-weight: 600; margin: 28px 0 12px; padding-bottom: 6px; border-bottom: 1px solid #f0f0f0; }
.page-body :deep(h3) { font-size: 18px; font-weight: 600; margin: 24px 0 10px; }
.page-body :deep(h4) { font-size: 16px; font-weight: 600; margin: 20px 0 8px; }
.page-body :deep(p) { margin: 12px 0; }
.page-body :deep(code) { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-size: 13px; font-family: "SF Mono", Monaco, monospace; }
.page-body :deep(pre) { background: #f5f5f5; padding: 16px; border-radius: 6px; overflow-x: auto; margin: 16px 0; }
.page-body :deep(pre code) { background: none; padding: 0; }
.page-body :deep(li) { margin: 4px 0; padding-left: 8px; list-style: disc; margin-left: 20px; }
.page-body :deep(strong) { font-weight: 600; }
.page-body :deep(a) { color: #4a90d9; text-decoration: none; }
.page-body :deep(a:hover) { text-decoration: underline; }
.page-body :deep(a.wikilink) { color: #6366f1; background: #eef2ff; padding: 1px 6px; border-radius: 3px; font-weight: 500; cursor: pointer; text-decoration: none; transition: all 0.15s; }
.page-body :deep(a.wikilink:hover) { background: #c7d2fe; color: #4338ca; text-decoration: none; }
.page-body :deep(table) { border-collapse: collapse; margin: 16px 0; width: 100%; }
.page-body :deep(th), .page-body :deep(td) { border: 1px solid #e8e8e8; padding: 8px 12px; text-align: left; }
.page-body :deep(th) { background: #f8f9fa; font-weight: 600; }
.page-body :deep(blockquote) { border-left: 4px solid #e8e8e8; margin: 16px 0; padding: 8px 16px; color: #666; background: #fafafa; }

/* ── 反向链接 ── */
.backlinks-panel { margin-top: 40px; padding-top: 20px; border-top: 1px solid #e8e8e8; }
.backlinks-title { font-size: 14px; font-weight: 600; color: #666; margin-bottom: 12px; display: flex; align-items: center; gap: 6px; }
.backlinks-icon { font-size: 16px; }
.backlinks-list { display: flex; flex-direction: column; gap: 8px; }
.backlink-item { padding: 10px 14px; background: #fafbff; border: 1px solid #e0e7ff; border-radius: 6px; cursor: pointer; transition: all 0.15s; }
.backlink-item:hover { border-color: #818cf8; background: #eef2ff; }
.backlink-title { font-weight: 500; font-size: 14px; color: #4338ca; margin-bottom: 4px; }
.backlink-snippet { font-size: 12px; color: #888; line-height: 1.5; }

/* ── 关联条目 ── */
.page-links { margin-top: 40px; padding-top: 20px; border-top: 1px solid #e8e8e8; }
.page-links h3 { font-size: 14px; font-weight: 600; color: #666; margin-bottom: 12px; }
.links-list { display: flex; flex-wrap: wrap; gap: 8px; }
.link-item { padding: 4px 12px; background: #f0f7ff; color: #4a90d9; border-radius: 4px; font-size: 13px; cursor: pointer; text-decoration: none; }
.link-item:hover { background: #e0efff; }

/* ── 编辑模式 ── */
.page-edit {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px 32px;
  gap: 12px;
  overflow: hidden;
}

.edit-meta-row {
  display: flex;
  gap: 16px;
  flex-shrink: 0;
}

.edit-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.edit-field-title { flex: 1; }
.edit-field-summary { flex: 2; }
.edit-field-category { flex: 1; }
.edit-field-tags { flex: 2; }

.edit-field label {
  font-size: 12px;
  font-weight: 500;
  color: #888;
}

.edit-input {
  padding: 6px 10px;
  border: 1px solid #d9d9d9;
  border-radius: 5px;
  font-size: 14px;
  outline: none;
}

.edit-input:focus { border-color: #4a90d9; }

.tags-editor {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  background: #e8f0fe;
  color: #1a73e8;
  border-radius: 10px;
  font-size: 11px;
}

.tag-remove {
  background: none;
  border: none;
  cursor: pointer;
  color: #1a73e8;
  font-size: 13px;
  line-height: 1;
  padding: 0;
}

.tag-input {
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  padding: 3px 6px;
  font-size: 11px;
  outline: none;
  min-width: 80px;
}

/* ── 分栏编辑器 ── */
.edit-split {
  flex: 1;
  display: flex;
  gap: 0;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  overflow: hidden;
  min-height: 0;
}

.edit-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  border-right: 1px solid #e8e8e8;
}

.edit-textarea {
  flex: 1;
  padding: 12px;
  border: none;
  font-size: 13px;
  font-family: "SF Mono", Monaco, "Cascadia Code", monospace;
  line-height: 1.6;
  resize: none;
  outline: none;
  tab-size: 2;
}

.preview-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: #fff;
}

.preview-header {
  padding: 6px 12px;
  font-size: 11px;
  font-weight: 500;
  color: #999;
  background: #f8f9fa;
  border-bottom: 1px solid #e8e8e8;
  flex-shrink: 0;
}

.preview-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.7;
}

.preview-body :deep(h1) { font-size: 22px; font-weight: 700; margin: 20px 0 10px; }
.preview-body :deep(h2) { font-size: 18px; font-weight: 600; margin: 18px 0 8px; }
.preview-body :deep(h3) { font-size: 16px; font-weight: 600; margin: 14px 0 6px; }
.preview-body :deep(p) { margin: 8px 0; }
.preview-body :deep(code) { background: #f5f5f5; padding: 2px 4px; border-radius: 3px; font-size: 12px; }
.preview-body :deep(pre) { background: #f5f5f5; padding: 12px; border-radius: 4px; overflow-x: auto; }
.preview-body :deep(pre code) { background: none; padding: 0; }
.preview-body :deep(li) { margin: 3px 0; list-style: disc; margin-left: 18px; }
.preview-body :deep(a.wikilink) { color: #6366f1; background: #eef2ff; padding: 1px 4px; border-radius: 3px; }
.preview-body :deep(table) { border-collapse: collapse; margin: 10px 0; width: 100%; }
.preview-body :deep(th), .preview-body :deep(td) { border: 1px solid #e8e8e8; padding: 6px 10px; font-size: 13px; }
.preview-body :deep(th) { background: #f8f9fa; }
</style>
