<template>
  <div class="app">
    <!-- 顶部导航 -->
    <nav class="top-nav">
      <div class="nav-left">
        <span class="logo">📖</span>
        <span class="logo-text">Wiki Agent</span>
      </div>
      <div class="nav-tabs">
        <button
          class="nav-tab"
          :class="{ active: mode === 'wiki' }"
          @click="mode = 'wiki'"
        >
          知识库
        </button>
        <button
          class="nav-tab"
          :class="{ active: mode === 'chat' }"
          @click="mode = 'chat'"
        >
          对话
        </button>
      </div>
      <div class="nav-right">
        <button
          v-if="mode === 'wiki'"
          class="nav-action"
          :class="{ active: showHistory }"
          @click="showHistory = !showHistory; if (showHistory) { currentPage = null; searchResults = []; }"
          title="变更流"
        >
          🕐 变更流
        </button>
        <input
          v-if="mode === 'wiki'"
          v-model="searchQuery"
          placeholder="搜索知识..."
          class="search-input"
          @keyup.enter="handleSearch"
        />
      </div>
    </nav>

    <!-- Wiki 模式 -->
    <div v-if="mode === 'wiki'" class="wiki-layout">
      <Sidebar
        :categories="categories"
        :currentPath="currentPath"
        @select="handleSelect"
        @create="handleCreate"
      />

      <main class="wiki-main">
        <!-- 搜索结果 -->
        <div v-if="searchResults.length" class="search-results">
          <div class="search-header">
            <span>找到 {{ searchResults.length }} 条结果</span>
            <button class="btn-link" @click="searchResults = []">清除</button>
          </div>
          <div
            v-for="r in searchResults"
            :key="r.path"
            class="search-item"
            @click="handleSelect(r.path)"
          >
            <div class="search-title">{{ r.title }}</div>
            <div class="search-snippet">{{ r.snippet }}</div>
          </div>
        </div>

        <!-- 全局变更流 -->
        <HistoryPanel
          v-else-if="showHistory"
          @select="handleSelectFromHistory"
          @rolled-back="handleRolledBack"
        />

        <!-- Wiki 页面 -->
        <WikiPage
          v-else-if="currentPage"
          :page="currentPage"
          @save="handleSave"
          @delete="handleDelete"
        />

        <!-- 空状态 -->
        <div v-else class="welcome">
          <div class="welcome-content">
            <h2>欢迎来到你的知识库</h2>
            <p>从左侧选择一个知识分类开始浏览，或切换到「对话」模式与 Agent 交互。</p>
            <div class="welcome-actions">
              <button class="btn-primary" @click="showImport = true">导入知识</button>
              <button class="btn-secondary" @click="handleCreate">新建条目</button>
              <button class="btn-secondary" @click="mode = 'chat'">与 Agent 对话</button>
            </div>
          </div>
        </div>
      </main>
    </div>

    <!-- Chat 模式 -->
    <ChatView
      v-else-if="mode === 'chat'"
      @knowledgeUpdated="handleKnowledgeUpdated"
      @navigateTo="handleNavigateFromChat"
    />

    <!-- 弹窗 -->
    <ImportDialog
      v-if="showImport"
      @close="showImport = false"
      @imported="handleImported"
    />
    <CreateDialog
      v-if="showCreate"
      :categories="flatCategories"
      @close="showCreate = false"
      @created="handleCreated"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { wikiApi } from "./api/index.js";
import Sidebar from "./components/Sidebar.vue";
import WikiPage from "./components/WikiPage.vue";
import HistoryPanel from "./components/HistoryPanel.vue";
import ImportDialog from "./components/ImportDialog.vue";
import CreateDialog from "./components/CreateDialog.vue";
import ChatView from "./components/ChatView.vue";

const mode = ref("wiki");
const categories = ref([]);
const currentPage = ref(null);
const currentPath = ref("");
const searchQuery = ref("");
const searchResults = ref([]);
const showImport = ref(false);
const showCreate = ref(false);
const showHistory = ref(false);

async function loadCategories() {
  try {
    const tree = await wikiApi.getTree();
    categories.value = buildCategories(tree);
  } catch (e) {
    console.error("加载分类失败:", e);
  }
}

function buildCategories(tree) {
  const cats = [];
  if (tree.children) {
    for (const child of tree.children) {
      if (child.is_dir) {
        cats.push({
          name: formatName(child.name),
          icon: getCategoryIcon(child.name),
          path: child.path,
          children: buildSubCategories(child),
        });
      } else {
        cats.push({
          name: formatName(child.name.replace(".md", "")),
          icon: "📄",
          path: child.path,
          children: [],
        });
      }
    }
  }
  return cats;
}

function buildSubCategories(node) {
  const items = [];
  if (node.children) {
    for (const child of node.children) {
      if (child.is_dir) {
        items.push({
          name: formatName(child.name),
          icon: getCategoryIcon(child.name),
          path: child.path,
          children: buildSubCategories(child),
        });
      } else {
        items.push({
          name: formatName(child.name.replace(".md", "")),
          icon: "📄",
          path: child.path,
          children: [],
        });
      }
    }
  }
  return items;
}

function formatName(name) {
  return name.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function getCategoryIcon(name) {
  const icons = {
    programming: "💻", python: "🐍", javascript: "⚡",
    ai: "🤖", ml: "🧠", devops: "🔧", tools: "🛠️",
    imported: "📥", daily: "📅", notes: "📝",
  };
  return icons[name.toLowerCase()] || "📁";
}

const flatCategories = computed(() => {
  const list = [];
  function flatten(cats, prefix = "") {
    for (const cat of cats) {
      const fullPath = prefix ? `${prefix}/${cat.name}` : cat.name;
      list.push({ name: fullPath, path: cat.path || fullPath.toLowerCase().replace(/ /g, "-") });
      if (cat.children?.length) flatten(cat.children, fullPath);
    }
  }
  flatten(categories.value);
  return list;
});

async function handleSelect(path) {
  try {
    currentPath.value = path;
    currentPage.value = await wikiApi.getPage(path);
    showHistory.value = false;
    searchResults.value = [];
  } catch (e) {
    console.error("加载条目失败:", e);
  }
}

function handleSelectFromHistory(path) {
  showHistory.value = false;
  handleSelect(path);
}

async function handleRolledBack(files) {
  await loadCategories();
  if (currentPath.value && files.includes(currentPath.value)) {
    try {
      currentPage.value = await wikiApi.getPage(currentPath.value);
    } catch (e) {
      console.error("刷新条目失败:", e);
    }
  }
}

async function handleSave({ path, data }) {
  try {
    currentPage.value = await wikiApi.updatePage(path, data);
  } catch (e) {
    alert("保存失败: " + e.message);
  }
}

async function handleDelete(path) {
  if (!confirm("确认删除此条目？")) return;
  try {
    await wikiApi.deletePage(path);
    currentPage.value = null;
    currentPath.value = "";
    await loadCategories();
  } catch (e) {
    alert("删除失败: " + e.message);
  }
}

function handleCreate() {
  showCreate.value = true;
}

async function handleCreated(path) {
  showCreate.value = false;
  await loadCategories();
  await handleSelect(path);
}

async function handleSearch() {
  if (!searchQuery.value.trim()) return;
  try {
    searchResults.value = await wikiApi.search(searchQuery.value);
  } catch (e) {
    alert("搜索失败: " + e.message);
  }
}

async function handleImported(path) {
  showImport.value = false;
  await loadCategories();
  await handleSelect(path);
}

async function handleKnowledgeUpdated() {
  await loadCategories();
  if (currentPath.value) {
    try {
      currentPage.value = await wikiApi.getPage(currentPath.value);
    } catch (e) {}
  }
}

async function handleNavigateFromChat(path) {
  // 从对话页面跳转到 Wiki 页面
  mode.value = "wiki";
  await handleSelect(path);
}

onMounted(loadCategories);
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", sans-serif;
  background: #f8f9fa;
  color: #1a1a1a;
  line-height: 1.6;
}

.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

/* ── 顶部导航 ── */
.top-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 48px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  flex-shrink: 0;
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 200px;
}

.logo {
  font-size: 18px;
}

.logo-text {
  font-size: 15px;
  font-weight: 600;
}

.nav-tabs {
  display: flex;
  gap: 4px;
  background: #f0f0f0;
  padding: 3px;
  border-radius: 8px;
}

.nav-tab {
  padding: 6px 20px;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: #666;
  transition: all 0.2s;
}

.nav-tab.active {
  background: #fff;
  color: #1a1a1a;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.nav-tab:hover:not(.active) {
  color: #333;
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.nav-action {
  padding: 6px 12px;
  background: transparent;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: #666;
  transition: all 0.15s;
  white-space: nowrap;
}

.nav-action:hover {
  border-color: #4a90d9;
  color: #4a90d9;
}

.nav-action.active {
  background: #4a90d9;
  border-color: #4a90d9;
  color: #fff;
}

.search-input {
  width: 180px;
  padding: 6px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 13px;
  outline: none;
}

.search-input:focus {
  border-color: #4a90d9;
}

/* ── Wiki 布局 ── */
.wiki-layout {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.wiki-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

/* ── 搜索结果 ── */
.search-results {
  flex: 1;
  overflow-y: auto;
  padding: 20px 32px;
}

.search-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  font-size: 14px;
  color: #888;
}

.search-item {
  padding: 14px 16px;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: border-color 0.15s;
}

.search-item:hover {
  border-color: #4a90d9;
}

.search-title {
  font-weight: 500;
  margin-bottom: 4px;
}

.search-snippet {
  font-size: 13px;
  color: #888;
}

/* ── 欢迎页 ── */
.welcome {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.welcome-content {
  text-align: center;
  max-width: 440px;
}

.welcome-content h2 {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 12px;
}

.welcome-content p {
  color: #888;
  margin-bottom: 24px;
  line-height: 1.8;
}

.welcome-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}

.btn-primary {
  padding: 8px 20px;
  background: #4a90d9;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.btn-primary:hover {
  background: #357abd;
}

.btn-secondary {
  padding: 8px 20px;
  background: #fff;
  color: #555;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.btn-secondary:hover {
  border-color: #4a90d9;
  color: #4a90d9;
}

.btn-link {
  background: none;
  border: none;
  color: #4a90d9;
  cursor: pointer;
  font-size: 13px;
}
</style>
