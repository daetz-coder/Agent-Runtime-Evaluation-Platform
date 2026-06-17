<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal">
      <h3>新建知识条目</h3>

      <div class="form-group">
        <label>知识分类</label>
        <select v-model="selectedCategory">
          <option value="">选择分类...</option>
          <option
            v-for="cat in categories"
            :key="cat.path"
            :value="cat.path"
          >
            {{ cat.name }}
          </option>
        </select>
      </div>

      <div class="form-group">
        <label>标题</label>
        <input v-model="title" placeholder="知识条目标题" @keyup.enter="handleCreate" />
      </div>

      <div class="form-group">
        <label>标签</label>
        <div class="tags-input">
          <span v-for="(tag, i) in tags" :key="i" class="tag-chip">
            {{ tag }}
            <button class="tag-remove" @click="tags.splice(i, 1)">×</button>
          </span>
          <input
            v-model="newTag"
            placeholder="添加标签..."
            @keyup.enter="addTag"
          />
        </div>
      </div>

      <div class="modal-actions">
        <button class="btn-cancel" @click="$emit('close')">取消</button>
        <button class="btn-create" @click="handleCreate" :disabled="!canCreate">创建</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import { wikiApi } from "../api/index.js";

const props = defineProps({ categories: Array });
const emit = defineEmits(["close", "created"]);

const selectedCategory = ref("");
const title = ref("");
const tags = ref([]);
const newTag = ref("");

const canCreate = computed(() => title.value.trim());

function addTag() {
  const tag = newTag.value.trim();
  if (tag && !tags.value.includes(tag)) {
    tags.value.push(tag);
  }
  newTag.value = "";
}

async function handleCreate() {
  if (!canCreate.value) return;

  const safeTitle = title.value
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^\w一-龥-]/g, "");

  const prefix = selectedCategory.value || "notes";
  const path = `${prefix}/${safeTitle}.md`;

  try {
    await wikiApi.createPage(path, {
      title: title.value.trim(),
      content: `# ${title.value.trim()}\n\n`,
      tags: tags.value,
      source: "manual",
    });
    emit("created", path);
  } catch (e) {
    alert("创建失败: " + e.message);
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
.form-group select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
  outline: none;
}

.form-group input:focus,
.form-group select:focus {
  border-color: #4a90d9;
}

.tags-input {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  padding: 6px 10px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
}

.tags-input:focus-within {
  border-color: #4a90d9;
}

.tags-input input {
  border: none;
  outline: none;
  flex: 1;
  min-width: 80px;
  padding: 2px;
  font-size: 13px;
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

.btn-create {
  padding: 8px 20px;
  background: #4a90d9;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.btn-create:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-create:hover:not(:disabled) {
  background: #357abd;
}
</style>
