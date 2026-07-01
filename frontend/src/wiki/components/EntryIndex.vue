<template>
  <div class="entry-index">
    <div class="index-header">
      <h2>词条索引</h2>
      <span class="index-desc">按字母顺序浏览所有词条（共 {{ totalCount }} 条）</span>
    </div>

    <!-- 字母导航栏 -->
    <nav class="alpha-nav">
      <button
        v-for="letter in allLetters"
        :key="letter"
        class="alpha-btn"
        :class="{ active: activeLetter === letter, disabled: !indexData[letter]?.length }"
        @click="scrollToLetter(letter)"
      >
        {{ letter }}
      </button>
    </nav>

    <div v-if="loading" class="index-loading">加载中...</div>
    <div v-else-if="totalCount === 0" class="index-empty">暂无词条</div>

    <!-- 词条列表 -->
    <div v-else class="index-body" ref="indexBodyRef">
      <div
        v-for="letter in availableLetters"
        :key="letter"
        class="letter-group"
        :id="'letter-' + letter"
      >
        <div class="letter-heading">{{ letter }}</div>
        <div
          v-for="entry in indexData[letter]"
          :key="entry.path"
          class="entry-card"
          @click="$emit('navigate', entry.path)"
        >
          <div class="entry-title">{{ entry.title }}</div>
          <div v-if="entry.summary" class="entry-summary">{{ entry.summary }}</div>
          <div v-if="entry.category" class="entry-category">{{ entry.category }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { wikiApi } from "../api/index.js";

const emit = defineEmits(["navigate"]);

const loading = ref(true);
const indexData = ref({});
const indexBodyRef = ref(null);

const allLetters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0-9#".split("");

const availableLetters = computed(() =>
  allLetters.filter((l) => indexData.value[l]?.length)
);

const totalCount = computed(() =>
  Object.values(indexData.value).reduce((sum, arr) => sum + arr.length, 0)
);

const activeLetter = ref("");

async function loadIndex() {
  loading.value = true;
  try {
    indexData.value = await wikiApi.getEntryIndex();
  } catch (e) {
    console.error("加载索引失败:", e);
  } finally {
    loading.value = false;
  }
}

function scrollToLetter(letter) {
  if (!indexData.value[letter]?.length) return;
  activeLetter.value = letter;
  const el = document.getElementById("letter-" + letter);
  if (el) {
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

onMounted(loadIndex);
</script>

<style scoped>
.entry-index {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 24px 32px;
}

.index-header {
  margin-bottom: 16px;
}

.index-header h2 {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 4px;
}

.index-desc {
  font-size: 13px;
  color: #888;
}

/* ── 字母导航栏 ── */
.alpha-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 20px;
  padding: 10px 0;
  border-bottom: 1px solid #e8e8e8;
  flex-shrink: 0;
}

.alpha-btn {
  width: 36px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8f9fa;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: #333;
  transition: all 0.15s;
}

.alpha-btn:hover:not(.disabled) {
  background: #e0efff;
  border-color: #4a90d9;
  color: #4a90d9;
}

.alpha-btn.active {
  background: #4a90d9;
  border-color: #4a90d9;
  color: #fff;
}

.alpha-btn.disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* ── 词条列表 ── */
.index-body {
  flex: 1;
  overflow-y: auto;
}

.index-loading,
.index-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
  font-size: 14px;
}

.letter-group {
  margin-bottom: 24px;
}

.letter-heading {
  font-size: 22px;
  font-weight: 700;
  color: #4a90d9;
  padding: 8px 0;
  border-bottom: 2px solid #4a90d9;
  margin-bottom: 10px;
}

.entry-card {
  padding: 10px 14px;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  margin-bottom: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.entry-card:hover {
  border-color: #4a90d9;
  background: #f8fbff;
}

.entry-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 4px;
}

.entry-summary {
  font-size: 13px;
  color: #666;
  line-height: 1.5;
}

.entry-category {
  font-size: 11px;
  color: #999;
  margin-top: 4px;
}
</style>
