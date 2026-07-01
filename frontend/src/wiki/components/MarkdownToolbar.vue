<template>
  <div class="md-toolbar">
    <button v-for="btn in buttons" :key="btn.label" class="toolbar-btn" :title="btn.label" @click="$emit('insert', btn.syntax)">
      <span v-html="btn.icon"></span>
    </button>
  </div>
</template>

<script setup>
defineEmits(["insert"]);

const buttons = [
  { label: "标题 H1", icon: "<b>H1</b>", syntax: "# " },
  { label: "标题 H2", icon: "<b>H2</b>", syntax: "## " },
  { label: "标题 H3", icon: "<b>H3</b>", syntax: "### " },
  { label: "加粗", icon: "<b>B</b>", syntax: "**", wrap: true },
  { label: "斜体", icon: "<i>I</i>", syntax: "*", wrap: true },
  { label: "行内代码", icon: "<code>&lt;/&gt;</code>", syntax: "`", wrap: true },
  { label: "代码块", icon: "{ }", syntax: "```\n", suffix: "\n```" },
  { label: "链接", icon: "🔗", syntax: "[", suffix: "](url)" },
  { label: "列表", icon: "• ", syntax: "- " },
  { label: "Wiki 链接", icon: "⟦⟧", syntax: "[[", suffix: "]]" },
  { label: "图片", icon: "🖼️", syntax: "![", suffix: "](url)" },
  { label: "分割线", icon: "—", syntax: "\n---\n" },
];
</script>

<style scoped>
.md-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  padding: 6px 8px;
  background: #f8f9fa;
  border: 1px solid #d9d9d9;
  border-bottom: none;
  border-radius: 6px 6px 0 0;
}

.toolbar-btn {
  width: 32px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  color: #555;
  transition: all 0.15s;
}

.toolbar-btn:hover {
  background: #e8f0fe;
  border-color: #b3d4fc;
  color: #1a73e8;
}

.toolbar-btn :deep(code) {
  background: none;
  padding: 0;
  font-size: 11px;
}
</style>
