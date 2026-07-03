<template>
  <div class="diff-view">
    <div class="diff-header">
      <div class="diff-file-path">{{ diff.path }}</div>
      <div class="diff-meta">
        <span class="diff-hash old">{{ diff.old_hash }}</span>
        <span class="diff-arrow">→</span>
        <span class="diff-hash new">{{ diff.new_hash }}</span>
      </div>
      <div class="diff-stats">
        <span class="stat-add">+{{ addCount }}</span>
        <span class="stat-remove">-{{ removeCount }}</span>
      </div>
      <div class="diff-actions">
        <button
          class="btn-mode"
          :class="{ active: viewMode === 'split' }"
          @click="viewMode = 'split'"
        >
          并排
        </button>
        <button
          class="btn-mode"
          :class="{ active: viewMode === 'unified' }"
          @click="viewMode = 'unified'"
        >
          统一
        </button>
      </div>
    </div>

    <!-- 无差异 -->
    <div v-if="!diff.hunks?.length" class="diff-empty">
      两个版本之间没有差异
    </div>

    <!-- 并排视图 -->
    <div v-else-if="viewMode === 'split'" class="diff-split">
      <div class="diff-pane diff-pane-left">
        <div class="pane-header">旧版本 ({{ diff.old_hash }})</div>
        <div v-for="(row, i) in splitRows" :key="i" class="diff-row" :class="row.leftClass">
          <span class="line-num">{{ row.leftNum || "" }}</span>
          <span class="line-content">{{ row.leftContent }}</span>
        </div>
      </div>
      <div class="diff-pane diff-pane-right">
        <div class="pane-header">新版本 ({{ diff.new_hash }})</div>
        <div v-for="(row, i) in splitRows" :key="i" class="diff-row" :class="row.rightClass">
          <span class="line-num">{{ row.rightNum || "" }}</span>
          <span class="line-content">{{ row.rightContent }}</span>
        </div>
      </div>
    </div>

    <!-- 统一视图 -->
    <div v-else class="diff-unified">
      <div v-for="(hunk, hi) in diff.hunks" :key="hi" class="hunk-block">
        <div class="hunk-header">{{ hunk.header || `Hunk ${hi + 1}` }}</div>
        <div
          v-for="(line, li) in hunk.lines"
          :key="li"
          class="diff-row"
          :class="'diff-' + line.type"
        >
          <span class="line-num old-num">{{ line.old_line ?? "" }}</span>
          <span class="line-num new-num">{{ line.new_line ?? "" }}</span>
          <span class="line-prefix">{{ linePrefix(line.type) }}</span>
          <span class="line-content">{{ line.content }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";

const props = defineProps({
  diff: { type: Object, required: true },
});

const viewMode = ref("split");

const addCount = computed(() => {
  let count = 0;
  for (const hunk of props.diff.hunks || []) {
    for (const line of hunk.lines) {
      if (line.type === "add") count++;
    }
  }
  return count;
});

const removeCount = computed(() => {
  let count = 0;
  for (const hunk of props.diff.hunks || []) {
    for (const line of hunk.lines) {
      if (line.type === "remove") count++;
    }
  }
  return count;
});

// 并排视图的行数据
const splitRows = computed(() => {
  const rows = [];
  for (const hunk of props.diff.hunks || []) {
    let i = 0;
    const lines = hunk.lines;
    while (i < lines.length) {
      const line = lines[i];
      if (line.type === "context") {
        rows.push({
          leftNum: line.old_line,
          rightNum: line.new_line,
          leftContent: line.content,
          rightContent: line.content,
          leftClass: "diff-context",
          rightClass: "diff-context",
        });
        i++;
      } else if (line.type === "remove") {
        // 收集连续的 remove 行
        const removes = [];
        while (i < lines.length && lines[i].type === "remove") {
          removes.push(lines[i]);
          i++;
        }
        // 收集连续的 add 行
        const adds = [];
        while (i < lines.length && lines[i].type === "add") {
          adds.push(lines[i]);
          i++;
        }
        // 配对输出
        const maxLen = Math.max(removes.length, adds.length);
        for (let j = 0; j < maxLen; j++) {
          const rm = removes[j];
          const ad = adds[j];
          rows.push({
            leftNum: rm?.old_line ?? "",
            rightNum: ad?.new_line ?? "",
            leftContent: rm?.content ?? "",
            rightContent: ad?.content ?? "",
            leftClass: rm ? "diff-remove" : "diff-empty-side",
            rightClass: ad ? "diff-add" : "diff-empty-side",
          });
        }
      } else if (line.type === "add") {
        rows.push({
          leftNum: "",
          rightNum: line.new_line,
          leftContent: "",
          rightContent: line.content,
          leftClass: "diff-empty-side",
          rightClass: "diff-add",
        });
        i++;
      } else {
        i++;
      }
    }
  }
  return rows;
});

function linePrefix(type) {
  if (type === "add") return "+";
  if (type === "remove") return "-";
  return " ";
}
</script>

<style scoped>
.diff-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.diff-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  background: #f8f9fa;
  border-bottom: 1px solid #e8e8e8;
  flex-shrink: 0;
}

.diff-file-path {
  font-weight: 600;
  font-size: 14px;
  color: #333;
}

.diff-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #888;
}

.diff-hash {
  font-family: "SF Mono", Monaco, monospace;
  padding: 2px 6px;
  border-radius: 3px;
  background: #f0f0f0;
}

.diff-stats {
  display: flex;
  gap: 8px;
  font-size: 12px;
  font-weight: 500;
}

.stat-add {
  color: #16a34a;
}

.stat-remove {
  color: #dc2626;
}

.diff-actions {
  margin-left: auto;
  display: flex;
  gap: 4px;
}

.btn-mode {
  padding: 4px 10px;
  background: transparent;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  color: #666;
  transition: all 0.15s;
}

.btn-mode.active {
  background: #4a90d9;
  border-color: #4a90d9;
  color: #fff;
}

.btn-mode:hover:not(.active) {
  border-color: #4a90d9;
  color: #4a90d9;
}

.diff-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
  font-size: 14px;
}

/* ── 并排视图 ── */
.diff-split {
  flex: 1;
  display: flex;
  overflow: auto;
}

.diff-pane {
  flex: 1;
  min-width: 0;
  overflow-x: auto;
}

.diff-pane-left {
  border-right: 1px solid #e8e8e8;
}

.pane-header {
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 500;
  color: #888;
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  position: sticky;
  top: 0;
  z-index: 1;
}

.diff-row {
  display: flex;
  font-family: "SF Mono", Monaco, "Cascadia Code", monospace;
  font-size: 13px;
  line-height: 1.5;
  min-height: 22px;
}

.line-num {
  display: inline-block;
  width: 48px;
  min-width: 48px;
  padding: 0 8px;
  text-align: right;
  color: #999;
  background: #fafafa;
  border-right: 1px solid #e8e8e8;
  user-select: none;
  flex-shrink: 0;
}

.line-content {
  flex: 1;
  padding: 0 12px;
  white-space: pre-wrap;
  word-break: break-all;
  min-width: 0;
}

/* 颜色 */
.diff-context {
  background: #fff;
}

.diff-add {
  background: #dcfce7;
}

.diff-add .line-num {
  background: #bbf7d0;
  color: #16a34a;
}

.diff-remove {
  background: #fee2e2;
}

.diff-remove .line-num {
  background: #fecaca;
  color: #dc2626;
}

.diff-empty-side {
  background: #f9fafb;
}

/* ── 统一视图 ── */
.diff-unified {
  flex: 1;
  overflow: auto;
}

.hunk-block {
  margin-bottom: 4px;
}

.hunk-header {
  padding: 6px 12px;
  background: #e8f4fd;
  color: #1e40af;
  font-size: 12px;
  font-family: "SF Mono", Monaco, monospace;
  border-bottom: 1px solid #bfdbfe;
}

.diff-unified .diff-row {
  display: flex;
  font-family: "SF Mono", Monaco, "Cascadia Code", monospace;
  font-size: 13px;
  line-height: 1.5;
}

.diff-unified .old-num,
.diff-unified .new-num {
  display: inline-block;
  width: 40px;
  min-width: 40px;
  padding: 0 6px;
  text-align: right;
  color: #999;
  background: #fafafa;
  border-right: 1px solid #e8e8e8;
  user-select: none;
  flex-shrink: 0;
}

.line-prefix {
  display: inline-block;
  width: 16px;
  min-width: 16px;
  text-align: center;
  color: #888;
  user-select: none;
  flex-shrink: 0;
}

.diff-unified .diff-add {
  background: #dcfce7;
}

.diff-unified .diff-add .old-num,
.diff-unified .diff-add .new-num {
  background: #bbf7d0;
}

.diff-unified .diff-remove {
  background: #fee2e2;
}

.diff-unified .diff-remove .old-num,
.diff-unified .diff-remove .new-num {
  background: #fecaca;
}
</style>
