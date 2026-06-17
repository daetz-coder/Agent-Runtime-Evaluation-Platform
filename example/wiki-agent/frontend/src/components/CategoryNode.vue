<template>
  <div class="category-node">
    <div
      class="node-row"
      :class="{ active: category.path === currentPath, 'has-children': hasChildren }"
      :style="{ paddingLeft: 12 + depth * 16 + 'px' }"
      @click="handleClick"
    >
      <span v-if="hasChildren" class="arrow" :class="{ expanded }">▶</span>
      <span v-else class="arrow-space"></span>
      <span class="node-icon">{{ category.icon || "📄" }}</span>
      <span class="node-name">{{ category.name }}</span>
      <span v-if="category.children?.length" class="node-count">
        {{ category.children.length }}
      </span>
    </div>

    <div v-if="hasChildren && expanded" class="node-children">
      <CategoryNode
        v-for="child in category.children"
        :key="child.path || child.name"
        :category="child"
        :currentPath="currentPath"
        :depth="depth + 1"
        @select="$emit('select', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";

const props = defineProps({
  category: Object,
  currentPath: String,
  depth: { type: Number, default: 0 },
});

const emit = defineEmits(["select"]);

const hasChildren = computed(() => props.category.children?.length > 0);
const expanded = ref(props.depth < 1);

function handleClick() {
  if (hasChildren.value) {
    expanded.value = !expanded.value;
  } else if (props.category.path) {
    emit("select", props.category.path);
  }
}
</script>

<style scoped>
.node-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  cursor: pointer;
  font-size: 13px;
  color: #444;
  transition: all 0.15s;
  user-select: none;
  border-radius: 4px;
  margin: 1px 4px;
}

.node-row:hover {
  background: #f0f0f0;
}

.node-row.active {
  background: #e8f0fe;
  color: #1a73e8;
  font-weight: 500;
}

.arrow {
  font-size: 8px;
  width: 12px;
  text-align: center;
  transition: transform 0.15s;
  color: #999;
}

.arrow.expanded {
  transform: rotate(90deg);
}

.arrow-space {
  width: 12px;
}

.node-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.node-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-count {
  font-size: 11px;
  color: #999;
  background: #f0f0f0;
  padding: 1px 6px;
  border-radius: 10px;
}

.node-children {
  /* 子节点区域 */
}
</style>
