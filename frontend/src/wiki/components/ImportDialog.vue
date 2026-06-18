<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal modal-wide">
      <h3>导入知识</h3>

      <div class="form-group">
        <label>来源类型</label>
        <div class="source-options">
          <button
            v-for="opt in sourceOptions"
            :key="opt.value"
            class="source-btn"
            :class="{ active: source === opt.value }"
            @click="source = opt.value"
          >
            <span class="source-icon">{{ opt.icon }}</span>
            <span>{{ opt.label }}</span>
          </button>
        </div>
      </div>

      <div class="form-group">
        <label>目标路径</label>
        <input v-model="path" placeholder="例: programming/python/decorators.md" />
      </div>

      <div class="form-group">
        <label>内容</label>
        <textarea
          v-model="content"
          rows="12"
          placeholder="粘贴 Markdown 内容..."
        />
      </div>

      <div class="form-group">
        <label class="checkbox-label">
          <input type="checkbox" v-model="overwrite" />
          覆盖已存在的条目
        </label>
      </div>

      <div class="modal-actions">
        <button class="btn-cancel" @click="$emit('close')">取消</button>
        <button class="btn-import" @click="handleImport" :disabled="!canImport">
          {{ importing ? "导入中..." : "导入" }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import { wikiApi } from "../api/index.js";

const emit = defineEmits(["close", "imported"]);

const path = ref("");
const content = ref("");
const source = ref("import");
const overwrite = ref(false);
const importing = ref(false);

const sourceOptions = [
  { value: "import", label: "手动导入", icon: "📋" },
  { value: "web-clip", label: "网页摘录", icon: "🌐" },
  { value: "ai-conversation", label: "AI 对话", icon: "🤖" },
  { value: "book", label: "书籍", icon: "📖" },
  { value: "document", label: "文档", icon: "📄" },
];

const canImport = computed(
  () => path.value.trim() && content.value.trim() && !importing.value
);

async function handleImport() {
  if (!canImport.value) return;
  importing.value = true;
  try {
    await wikiApi.importMarkdown({
      path: path.value,
      content: content.value,
      source: source.value,
      overwrite: overwrite.value,
    });
    emit("imported", path.value);
  } catch (e) {
    alert("导入失败: " + e.message);
  } finally {
    importing.value = false;
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: #fff;
  border-radius: 12px;
  padding: 28px;
  width: 440px;
  max-width: 90vw;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

.modal-wide {
  width: 560px;
}

.modal h3 {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 20px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #666;
  margin-bottom: 6px;
}

.form-group input,
.form-group textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
  outline: none;
  font-family: inherit;
}

.form-group textarea {
  font-family: "SF Mono", Monaco, monospace;
  font-size: 13px;
  line-height: 1.5;
  resize: vertical;
}

.form-group input:focus,
.form-group textarea:focus {
  border-color: #4a90d9;
}

.source-options {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.source-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: #f5f5f5;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: #555;
  transition: all 0.15s;
}

.source-btn:hover {
  border-color: #4a90d9;
}

.source-btn.active {
  background: #e8f0fe;
  border-color: #4a90d9;
  color: #1a73e8;
}

.source-icon {
  font-size: 16px;
}

.checkbox-label {
  display: flex !important;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-weight: 400 !important;
}

.checkbox-label input {
  width: auto;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 24px;
}

.btn-cancel {
  padding: 8px 18px;
  background: #f5f5f5;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  color: #666;
}

.btn-import {
  padding: 8px 20px;
  background: #4a90d9;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.btn-import:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-import:hover:not(:disabled) {
  background: #357abd;
}
</style>
