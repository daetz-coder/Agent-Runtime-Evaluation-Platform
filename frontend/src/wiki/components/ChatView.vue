<template>
  <div class="chat-view">
    <!-- 左侧：会话列表 -->
    <aside class="session-sidebar">
      <button class="new-session-btn" @click="createSession">
        + 新对话
      </button>
      <div class="session-list">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="session-item"
          :class="{ active: s.id === currentSessionId }"
          @click="switchSession(s.id)"
        >
          <span class="session-icon">💬</span>
          <span class="session-name">{{ s.name || '新对话' }}</span>
          <button
            class="session-delete"
            @click.stop="deleteSession(s.id)"
            title="删除"
          >×</button>
        </div>
      </div>
    </aside>

    <!-- 右侧：对话区 -->
    <main class="chat-main">
      <!-- 消息区 -->
      <div class="messages-container" ref="messagesRef">
        <div class="messages-inner">
          <!-- 空状态 -->
          <div v-if="currentMessages.length === 0" class="chat-empty">
            <div class="empty-icon">🤖</div>
            <h2>Wiki Agent</h2>
            <p>你的个人知识库助手</p>
            <p class="empty-hint">对话中的知识会自动识别，你可以选择保存到知识库</p>
            <div class="suggestions">
              <button
                v-for="s in suggestions"
                :key="s"
                class="suggestion-card"
                @click="sendMessage(s)"
              >
                {{ s }}
              </button>
            </div>
          </div>

          <!-- 消息列表 -->
          <div
            v-for="(msg, i) in currentMessages"
            :key="i"
            class="message-row"
            :class="msg.role"
          >
            <!-- 用户消息 -->
            <div v-if="msg.role === 'user'" class="msg-container user">
              <div class="msg-bubble user-bubble">
                {{ msg.content }}
              </div>
            </div>

            <!-- AI 消息 -->
            <div v-else-if="msg.role === 'assistant'" class="msg-container assistant">
              <div class="msg-avatar">🤖</div>
              <div class="msg-body">
                <!-- 状态提示 -->
                <div v-if="msg.status" class="status-hint">
                  {{ msg.status }}
                </div>
                <!-- 知识库搜索结果（可折叠） -->
                <div v-if="msg.wikiResults" class="wiki-results">
                  <details>
                    <summary>📚 知识库检索结果</summary>
                    <pre>{{ msg.wikiResults }}</pre>
                  </details>
                </div>
                <!-- AI 回复内容 -->
                <div v-if="msg.content" class="msg-bubble assistant-bubble" :class="{ streaming: msg.streaming }">
                  <div class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
                </div>
                <!-- 评估任务链接 -->
                <div v-if="msg.evaluationTaskId" class="evaluation-link-card">
                  <span>📊 运行轨迹已提交评估</span>
                  <button class="eval-link-btn" @click="goToEvaluationTask(msg.evaluationTaskId)">
                    查看评估任务 →
                  </button>
                </div>
                <!-- 加载中（还没有内容时） -->
                <div v-if="!msg.content && !msg.status" class="msg-bubble assistant-bubble">
                  <div class="typing-dots">
                    <span></span><span></span><span></span>
                  </div>
                </div>

                <!-- 知识提取结果卡片 -->
                <div v-if="msg.extraction" class="extraction-card" :class="msg.extractionStatus">
                  <div class="extraction-header">
                    <span class="extraction-icon">{{ msg.extractionStatus === 'confirmed' ? '✅' : msg.extractionStatus === 'rejected' ? '🚫' : '💡' }}</span>
                    <span class="extraction-title">
                      {{ msg.extractionStatus === 'confirmed' ? '已保存到知识库' : msg.extractionStatus === 'rejected' ? '已忽略' : '发现可保存的知识' }}
                    </span>
                    <span v-if="!msg.extractionStatus" class="extraction-action" :class="msg.extraction.action">
                      {{ msg.extraction.action === 'create' ? '新建' : msg.extraction.action === 'update' ? '更新' : '删除' }}
                    </span>
                  </div>

                  <!-- 待确认时显示详情 -->
                  <template v-if="!msg.extractionStatus">
                    <div class="extraction-reason">{{ msg.extraction.reason }}</div>

                    <!-- 提取内容预览 -->
                    <div v-if="showExtractionDetail !== i" class="extraction-preview">
                      <span class="preview-label">标题：</span>{{ msg.extraction.title || msg.extraction.path?.replace(/\.md$/, '').split('/').pop() || '未命名' }}
                      <span v-if="msg.extraction.path" class="preview-path">
                        {{ msg.extraction.path }}
                      </span>
                    </div>

                    <!-- 详细编辑模式 -->
                    <div v-if="showExtractionDetail === i" class="extraction-detail">
                      <div class="detail-field">
                        <label>标题</label>
                        <input v-model="editExtraction.title" class="detail-input" />
                      </div>
                      <div class="detail-field" v-if="msg.extraction.action === 'create'">
                        <label>分类</label>
                        <input v-model="editExtraction.category" class="detail-input" placeholder="如 programming/python" />
                      </div>
                      <div class="detail-field" v-if="msg.extraction.action === 'update'">
                        <label>目标路径</label>
                        <input v-model="editExtraction.target_path" class="detail-input" />
                      </div>
                      <div class="detail-field">
                        <label>内容 (Markdown)</label>
                        <textarea v-model="editExtraction.content" class="detail-textarea" rows="10"></textarea>
                      </div>
                      <div class="detail-field">
                        <label>标签</label>
                        <input v-model="editExtraction.tagsStr" class="detail-input" placeholder="逗号分隔" />
                      </div>
                    </div>

                    <!-- 操作按钮 -->
                    <div class="extraction-actions">
                      <button
                        v-if="showExtractionDetail !== i"
                        class="btn-detail"
                        @click="startEditExtraction(i, msg.extraction)"
                      >
                        查看详情
                      </button>
                      <button
                        v-if="showExtractionDetail === i"
                        class="btn-detail"
                        @click="showExtractionDetail = -1"
                      >
                        收起
                      </button>
                      <button
                        class="btn-save"
                        @click="confirmExtraction(msg)"
                        :disabled="savingExtraction"
                      >
                        {{ savingExtraction ? '保存中...' : '确认保存' }}
                      </button>
                      <button
                        class="btn-ignore"
                        @click="rejectExtraction(msg)"
                        :disabled="savingExtraction"
                      >
                        忽略
                      </button>
                    </div>
                  </template>

                  <!-- 已确认/已忽略时显示简要信息 -->
                  <div v-if="msg.extractionStatus === 'confirmed'" class="extraction-saved-info">
                    {{ msg.extraction.title }} 已保存到知识库
                  </div>
                  <div v-if="msg.extractionStatus === 'rejected'" class="extraction-ignored-info">
                    已忽略该知识提取
                  </div>

                  <!-- 操作结果（错误时显示） -->
                  <div v-if="msg.extractionResult && msg.extractionResult.status === 'error'" class="extraction-result error">
                    {{ msg.extractionResult.message }}
                  </div>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <div class="input-wrapper">
          <textarea
            v-model="input"
            placeholder="输入消息，按 Enter 发送..."
            rows="1"
            @keydown.enter.exact.prevent="handleSend"
            @input="autoResize"
            ref="inputRef"
          />
          <button
            class="send-btn"
            @click="handleSend"
            :disabled="!input.trim() || loading"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
            </svg>
          </button>
        </div>
        <div class="input-hint">Enter 发送，Shift+Enter 换行</div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { wikiApi } from "../api/index.js";
import { streamAuthHeaders } from "@/api";
import { marked } from 'marked'

const router = useRouter();
const emit = defineEmits(["knowledgeUpdated", "navigateTo"]);

const input = ref("");
const loading = ref(false);
const messagesRef = ref(null);
const inputRef = ref(null);
const savingExtraction = ref(false);
const showExtractionDetail = ref(-1);
const editExtraction = reactive({
  title: "",
  category: "",
  content: "",
  target_path: "",
  tagsStr: "",
});

// 会话管理
const sessions = ref([]);
const currentSessionId = ref("");
const sessionsLoaded = ref(false);

const currentMessages = computed(() => {
  const s = sessions.value.find((s) => s.id === currentSessionId.value);
  return s?.messages || [];
});

const suggestions = [
  "帮我搜索关于 Python 的知识",
  "列出知识库的目录结构",
  "创建一个关于 Git 常用命令的条目",
  "总结一下知识库里有什么内容",
];

// 加载会话列表
async function loadSessions() {
  try {
    const res = await fetch("/api/chat/sessions", { headers: streamAuthHeaders() });
    const data = await res.json();
    sessions.value = data.sessions.map((s) => ({
      ...s,
      messages: [], // 消息延迟加载
    }));

    // 如果没有会话，创建默认会话
    if (sessions.value.length === 0) {
      await createSession();
    } else {
      // 选择第一个会话
      currentSessionId.value = sessions.value[0].id;
      await loadSessionMessages(currentSessionId.value);
    }
    sessionsLoaded.value = true;
  } catch (e) {
    console.error("加载会话列表失败:", e);
    // 创建默认会话
    await createSession();
    sessionsLoaded.value = true;
  }
}

// 加载会话消息
async function loadSessionMessages(sessionId) {
  try {
    const res = await fetch(`/api/chat/sessions/${sessionId}`, { headers: streamAuthHeaders() });
    if (!res.ok) return;
    const data = await res.json();

    const session = sessions.value.find((s) => s.id === sessionId);
    if (session) {
      session.messages = data.messages.map((m) => ({
        role: m.role,
        content: m.content,
        wikiResults: m.wiki_results,
        extraction: m.extraction,
        extractionStatus: m.extraction?.status || (m.extraction?.auto_saved ? 'confirmed' : null),
        streaming: false,
      }));
    }
    await scrollToBottom({ immediate: true });
  } catch (e) {
    console.error("加载会话消息失败:", e);
  }
}

async function createSession() {
  const id = `session-${Date.now()}`;
  try {
    const res = await fetch(`/api/chat/sessions?session_id=${id}&name=${encodeURIComponent("新对话")}`, {
      method: "POST",
      headers: streamAuthHeaders(),
    });
    const data = await res.json();
    sessions.value.unshift({ id: data.id, name: data.name, messages: [] });
  } catch (e) {
    sessions.value.unshift({ id, name: "新对话", messages: [] });
  }
  currentSessionId.value = id;
}

async function switchSession(id) {
  if (currentSessionId.value === id) return;
  currentSessionId.value = id;

  // 加载该会话的消息
  const session = sessions.value.find((s) => s.id === id);
  if (session && session.messages.length === 0) {
    await loadSessionMessages(id);
  } else {
    await scrollToBottom({ immediate: true });
  }
}

async function deleteSession(id) {
  try {
    await fetch(`/api/chat/sessions/${id}`, { method: "DELETE", headers: streamAuthHeaders() });
  } catch (e) {}

  sessions.value = sessions.value.filter((s) => s.id !== id);
  if (currentSessionId.value === id) {
    currentSessionId.value = sessions.value[0]?.id || "";
    if (!sessions.value.length) {
      await createSession();
    } else {
      await loadSessionMessages(currentSessionId.value);
    }
  }
}

function autoResize(e) {
  const el = e.target;
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 160) + "px";
}

function handleSend() {
  const text = input.value.trim();
  if (!text || loading.value) return;
  input.value = "";
  nextTick(() => {
    if (inputRef.value) inputRef.value.style.height = "auto";
  });
  sendMessage(text);
}

async function sendMessage(text) {
  const session = sessions.value.find((s) => s.id === currentSessionId.value);
  if (!session) return;

  // 更新会话名称（用第一条消息）
  if (session.messages.length === 0) {
    session.name = text.slice(0, 30) + (text.length > 30 ? "..." : "");
  }

  session.messages.push({ role: "user", content: text });
  scrollToBottom();

  // 创建 AI 消息（使用 reactive 确保属性变更触发响应式更新）
  const aiMsg = reactive({
    role: "assistant",
    content: "",
    wikiResults: null,
    status: null,
    extraction: null,
    extractionResult: null,
    evaluationTaskId: null,
    streaming: true,
  });
  session.messages.push(aiMsg);
  loading.value = true;

  try {
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: streamAuthHeaders(),
      body: JSON.stringify({
        session_id: currentSessionId.value,
        message: text,
      }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let aiContent = "";
    let wikiResults = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const data = JSON.parse(line.slice(6));

          if (data.type === "wiki_results") {
            wikiResults = data.results;
            aiMsg.wikiResults = wikiResults;
            scrollToBottom();
          } else if (data.type === "content") {
            aiContent += data.text;
            aiMsg.content = aiContent;
            aiMsg.status = null; // 收到内容后清除状态
            scrollToBottom();
          } else if (data.type === "status") {
            aiMsg.status = data.message;
            scrollToBottom();
          } else if (data.type === "extraction") {
            aiMsg.extraction = data.data;
            aiMsg.status = null;
            aiMsg.extractionStatus = null; // 待确认状态
            scrollToBottom();
          } else if (data.type === "evaluation_task") {
            aiMsg.evaluationTaskId = data.task_id;
            scrollToBottom();
          } else if (data.type === "done") {
            if (data.evaluation_task_id) {
              aiMsg.evaluationTaskId = data.evaluation_task_id;
            }
            aiMsg.streaming = false;
          } else if (data.type === "error") {
            aiMsg.content = `错误: ${data.message}`;
            aiMsg.streaming = false;
          }
        } catch (e) {}
      }
    }

    if (wikiResults) emit("knowledgeUpdated");
  } catch (e) {
    aiMsg.content = `连接失败: ${e.message}`;
  } finally {
    aiMsg.streaming = false;
    loading.value = false;
    scrollToBottom();
  }
}

function startEditExtraction(index, extraction) {
  showExtractionDetail.value = index;
  editExtraction.title = extraction.title || extraction.path?.replace(/\.md$/, '').split('/').pop() || "";
  editExtraction.category = extraction.category || "";
  editExtraction.content = extraction.content || "";
  editExtraction.target_path = extraction.target_path || extraction.path || "";
  editExtraction.tagsStr = (extraction.tags || []).join(", ");
}

async function confirmExtraction(msg) {
  if (!msg.extraction || !msg.extraction.thread_id) return;

  savingExtraction.value = true;
  try {
    const res = await fetch("/api/chat/confirm", {
      method: "POST",
      headers: streamAuthHeaders(),
      body: JSON.stringify({
        thread_id: msg.extraction.thread_id,
        confirm: true,
        session_id: currentSessionId.value,
      }),
    });
    const result = await res.json();
    msg.extractionResult = result;

    if (result.status === "ok") {
      msg.extractionStatus = "confirmed";
      emit("knowledgeUpdated");
    } else if (result.status === "error") {
      msg.extractionResult = { status: "error", message: result.message || "操作失败" };
    }
  } catch (e) {
    msg.extractionResult = { status: "error", message: `保存失败: ${e.message}` };
  } finally {
    savingExtraction.value = false;
    showExtractionDetail.value = -1;
  }
}

function goToEvaluationTask(taskId) {
  router.push(`/tasks/${taskId}`);
}

async function rejectExtraction(msg) {
  if (!msg.extraction || !msg.extraction.thread_id) return;

  savingExtraction.value = true;
  try {
    await fetch("/api/chat/confirm", {
      method: "POST",
      headers: streamAuthHeaders(),
      body: JSON.stringify({
        thread_id: msg.extraction.thread_id,
        confirm: false,
        session_id: currentSessionId.value,
      }),
    });
    msg.extractionStatus = "rejected";
  } catch (e) {
    console.error("忽略操作失败:", e);
  } finally {
    savingExtraction.value = false;
    showExtractionDetail.value = -1;
  }
}

async function scrollToBottom(options = {}) {
  const { immediate = false } = options;
  await nextTick();
  await new Promise((resolve) => requestAnimationFrame(resolve));
  if (messagesRef.value) {
    messagesRef.value.scrollTo({
      top: messagesRef.value.scrollHeight,
      behavior: immediate ? "auto" : "smooth",
    });
  }
}

function renderMarkdown(text) {
  if (!text) return "";
  try {
    if (!renderMarkdown._init) {
      marked.setOptions({ breaks: true, gfm: true });
      renderMarkdown._init = true;
    }
    return marked.parse(text);
  } catch {
    let html = text
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
      .replace(/^### (.+)$/gm, "<h3>$1</h3>")
      .replace(/^## (.+)$/gm, "<h2>$1</h2>")
      .replace(/^# (.+)$/gm, "<h1>$1</h1>")
      .replace(/\n\n/g, "</p><p>")
      .replace(/\n/g, "<br>");
    return html;
  }
}

// 注册全局导航函数，让内联 onclick 能触发
onMounted(async () => {
  inputRef.value?.focus();
  window.__wikiNavigate = (path) => {
    emit("navigateTo", path);
  };

  // 加载会话列表
  await loadSessions();
});
</script>

<style scoped>
.chat-view {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ── 左侧会话列表 ── */
.session-sidebar {
  width: 260px;
  background: #1a1a1a;
  color: #fff;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.new-session-btn {
  margin: 12px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: #fff;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.15s;
}

.new-session-btn:hover {
  background: rgba(255, 255, 255, 0.15);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
  transition: background 0.15s;
  margin-bottom: 2px;
}

.session-item:hover {
  background: rgba(255, 255, 255, 0.1);
}

.session-item.active {
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
}

.session-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.session-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-delete {
  opacity: 0;
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  font-size: 16px;
  padding: 0 4px;
  transition: opacity 0.15s;
}

.session-item:hover .session-delete {
  opacity: 1;
}

.session-delete:hover {
  color: #ff6b6b;
}

/* ── 右侧对话区 ── */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
  min-width: 0;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
}

.messages-inner {
  max-width: 780px;
  margin: 0 auto;
  padding: 24px 20px;
}

/* ── 空状态 ── */
.chat-empty {
  text-align: center;
  padding: 80px 20px 40px;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.chat-empty h2 {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 8px;
}

.chat-empty p {
  color: #888;
  margin-bottom: 4px;
}

.empty-hint {
  font-size: 13px;
  color: #aaa;
  margin-bottom: 32px !important;
}

.suggestions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  max-width: 500px;
  margin: 0 auto;
}

.suggestion-card {
  padding: 14px 16px;
  background: #f8f9fa;
  border: 1px solid #e8e8e8;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
  color: #444;
  text-align: left;
  line-height: 1.4;
  transition: all 0.15s;
}

.suggestion-card:hover {
  border-color: #4a90d9;
  background: #f0f7ff;
  color: #2a6cb8;
}

/* ── 消息行 ── */
.message-row {
  margin-bottom: 20px;
}

.msg-container {
  display: flex;
  gap: 12px;
  max-width: 100%;
}

.msg-container.user {
  justify-content: flex-end;
}

.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
}

.msg-body {
  flex: 1;
  min-width: 0;
}

/* ── 消息气泡 ── */
.msg-bubble {
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
}

.user-bubble {
  background: #4a90d9;
  color: #fff;
  max-width: 70%;
  margin-left: auto;
  border-radius: 12px 12px 4px 12px;
}

.assistant-bubble {
  background: #f5f7fa;
  color: #1a1a1a;
  border: 1px solid #edf0f4;
  max-width: 100%;
}

.assistant-bubble.streaming .markdown-body::after {
  content: "";
  display: inline-block;
  width: 7px;
  height: 16px;
  margin-left: 3px;
  vertical-align: -2px;
  border-radius: 2px;
  background: #4a90d9;
  animation: cursor-blink 1s step-end infinite;
}

@keyframes cursor-blink {
  0%, 45% { opacity: 1; }
  46%, 100% { opacity: 0; }
}

.markdown-body {
  color: #202124;
  line-height: 1.75;
  overflow-wrap: anywhere;
}

.markdown-body :deep(*) {
  max-width: 100%;
}

.markdown-body :deep(:first-child) {
  margin-top: 0;
}

.markdown-body :deep(:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(p) {
  margin: 0.45rem 0;
}

.markdown-body :deep(h1) {
  font-size: 20px;
  line-height: 1.35;
  margin: 14px 0 8px;
}

.markdown-body :deep(h2) {
  font-size: 17px;
  line-height: 1.4;
  margin: 12px 0 7px;
}

.markdown-body :deep(h3) {
  font-size: 15px;
  line-height: 1.45;
  margin: 10px 0 6px;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0.45rem 0;
  padding-left: 1.35rem;
}

.markdown-body :deep(li) {
  margin: 0.18rem 0;
  padding-left: 0.1rem;
}

.markdown-body :deep(li > p) {
  margin: 0.15rem 0;
}

.markdown-body :deep(blockquote) {
  margin: 0.7rem 0;
  padding: 0.15rem 0 0.15rem 0.85rem;
  color: #5f6368;
  border-left: 3px solid #c9d7e8;
}

.markdown-body :deep(code) {
  background: #e8e8e8;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 12px;
  font-family: "SF Mono", Monaco, monospace;
}

.markdown-body :deep(pre) {
  background: #20242a;
  color: #e8eaed;
  padding: 13px 14px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 0.75rem 0;
  font-size: 13px;
  line-height: 1.6;
}

.markdown-body :deep(pre code) {
  background: none;
  color: inherit;
  padding: 0;
  white-space: pre;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.75rem 0;
  display: block;
  overflow-x: auto;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #d8dee8;
  padding: 6px 8px;
  text-align: left;
}

.markdown-body :deep(th) {
  background: #eef3f8;
  font-weight: 600;
}

.markdown-body :deep(a) {
  color: #256fc2;
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

.markdown-body :deep(hr) {
  height: 1px;
  margin: 0.9rem 0;
  border: 0;
  background: #dfe5ec;
}

.markdown-body :deep(strong) {
  font-weight: 600;
}

.assistant-bubble :deep(.source-link) {
  display: inline-block;
  background: #e8f0fe;
  color: #1a73e8;
  padding: 1px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-family: monospace;
  cursor: pointer;
  margin: 2px 0;
  transition: background 0.15s;
}

.assistant-bubble :deep(.source-link:hover) {
  background: #d0e3f7;
  text-decoration: underline;
}

/* ── 状态提示 ── */
.status-hint {
  font-size: 12px;
  color: #999;
  padding: 4px 0;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

/* ── 知识库检索结果 ── */
.wiki-results {
  margin-bottom: 8px;
}

.wiki-results details {
  background: #f0f7ff;
  border: 1px solid #d0e3f7;
  border-radius: 8px;
  padding: 8px 12px;
}

.wiki-results summary {
  cursor: pointer;
  font-size: 13px;
  color: #4a90d9;
  font-weight: 500;
}

.wiki-results pre {
  margin: 8px 0 0;
  font-size: 12px;
  color: #555;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
}

/* ── 评估任务链接 ── */
.evaluation-link-card {
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  background: #f0f9ff;
  border: 1px solid #b3d8ff;
  border-radius: 10px;
  font-size: 13px;
  color: #409eff;
}

.eval-link-btn {
  border: none;
  background: #409eff;
  color: #fff;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}

.eval-link-btn:hover {
  background: #66b1ff;
}

/* ── 知识提取卡片 ── */
.extraction-card {
  margin-top: 12px;
  background: #fffbe6;
  border: 1px solid #ffe58f;
  border-radius: 10px;
  padding: 16px;
  transition: all 0.3s ease;
}

.extraction-card.confirmed {
  background: #f6ffed;
  border-color: #b7eb8f;
}

.extraction-card.rejected {
  background: #f5f5f5;
  border-color: #d9d9d9;
  opacity: 0.7;
}

.extraction-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.extraction-icon {
  font-size: 18px;
}

.extraction-title {
  font-weight: 600;
  font-size: 14px;
  color: #333;
}

.extraction-action {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.extraction-action.create {
  background: #e6f7ff;
  color: #1890ff;
}

.extraction-action.update {
  background: #fff7e6;
  color: #fa8c16;
}

.extraction-reason {
  font-size: 13px;
  color: #666;
  margin-bottom: 12px;
  line-height: 1.5;
}

.extraction-preview {
  font-size: 13px;
  color: #555;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 6px;
  margin-bottom: 12px;
}

.preview-label {
  color: #999;
}

.preview-category {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 8px;
  background: #f0f0f0;
  border-radius: 10px;
  font-size: 11px;
  color: #666;
}

.preview-path {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 8px;
  background: #e6f7ff;
  border-radius: 10px;
  font-size: 11px;
  color: #1890ff;
}

.extraction-detail {
  margin-bottom: 12px;
}

.detail-field {
  margin-bottom: 10px;
}

.detail-field label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: #666;
  margin-bottom: 4px;
}

.detail-input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 13px;
  outline: none;
  font-family: inherit;
}

.detail-input:focus {
  border-color: #4a90d9;
}

.detail-textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 13px;
  font-family: "SF Mono", Monaco, monospace;
  line-height: 1.6;
  resize: vertical;
  outline: none;
}

.detail-textarea:focus {
  border-color: #4a90d9;
}

.extraction-actions {
  display: flex;
  gap: 8px;
}

.btn-detail {
  padding: 6px 14px;
  background: transparent;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  color: #555;
  transition: all 0.15s;
}

.btn-detail:hover {
  border-color: #4a90d9;
  color: #4a90d9;
}

.btn-save {
  padding: 6px 16px;
  background: #52c41a;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: background 0.15s;
}

.btn-save:hover:not(:disabled) {
  background: #389e0d;
}

.btn-save:disabled {
  background: #b7eb8f;
  cursor: not-allowed;
}

.btn-ignore {
  padding: 6px 14px;
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 12px;
  color: #999;
  transition: color 0.15s;
}

.btn-ignore:hover {
  color: #666;
}

.extraction-result {
  margin-top: 10px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
}

.extraction-result.ok {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  color: #52c41a;
}

.extraction-result.error {
  background: #fff2f0;
  border: 1px solid #ffccc7;
  color: #ff4d4f;
}

.extraction-saved-info {
  font-size: 13px;
  color: #52c41a;
  padding: 8px 0;
}

.extraction-ignored-info {
  font-size: 13px;
  color: #999;
  padding: 8px 0;
}

/* ── 打字动画 ── */
.typing-dots {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.typing-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #999;
  animation: dot-bounce 1.2s infinite;
}

.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes dot-bounce {
  0%, 60%, 100% { opacity: 0.3; transform: translateY(0); }
  30% { opacity: 1; transform: translateY(-4px); }
}

/* ── 输入区 ── */
.input-area {
  padding: 12px 20px 16px;
  border-top: 1px solid #e8e8e8;
  background: #fff;
}

.input-wrapper {
  max-width: 780px;
  margin: 0 auto;
  display: flex;
  gap: 10px;
  align-items: flex-end;
  background: #f5f7fa;
  border: 1px solid #d9d9d9;
  border-radius: 12px;
  padding: 8px 12px;
  transition: border-color 0.2s;
}

.input-wrapper:focus-within {
  border-color: #4a90d9;
  background: #fff;
}

.input-wrapper textarea {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  font-family: inherit;
  line-height: 1.5;
  resize: none;
  min-height: 24px;
  max-height: 160px;
}

.send-btn {
  width: 36px;
  height: 36px;
  background: #4a90d9;
  color: #fff;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.15s;
}

.send-btn:disabled {
  background: #c0c0c0;
  cursor: not-allowed;
}

.send-btn:hover:not(:disabled) {
  background: #357abd;
}

.input-hint {
  text-align: center;
  font-size: 11px;
  color: #bbb;
  margin-top: 6px;
}
</style>
