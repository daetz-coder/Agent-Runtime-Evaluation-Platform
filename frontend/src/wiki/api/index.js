const BASE = "/api/wiki";

async function request(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "请求失败");
  }
  if (res.status === 204) return null;
  return res.json();
}

export const wikiApi = {
  // 目录树
  getTree(path = "") {
    return request(`${BASE}/tree?path=${encodeURIComponent(path)}`);
  },

  // CRUD
  getPage(path) {
    return request(`${BASE}/page/${path}`);
  },

  createPage(path, data) {
    return request(`${BASE}/page/${path}`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  updatePage(path, data) {
    return request(`${BASE}/page/${path}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  deletePage(path) {
    return request(`${BASE}/page/${path}`, { method: "DELETE" });
  },

  // 搜索
  search(q) {
    return request(`${BASE}/search?q=${encodeURIComponent(q)}`);
  },

  // 版本历史
  getHistory(path) {
    return request(`${BASE}/page/${path}/history`);
  },

  getGlobalHistory(limit = 50) {
    return request(`${BASE}/history?limit=${limit}`);
  },

  rollback(path, hash) {
    return request(`${BASE}/page/${path}/rollback?commit_hash=${hash}`, {
      method: "POST",
    });
  },

  // Diff
  getDiff(path, oldHash, newHash = "HEAD") {
    return request(`${BASE}/page/${path}/diff?old=${oldHash}&new=${newHash}`);
  },

  // Backlinks
  getBacklinks(path) {
    return request(`${BASE}/page/${path}/backlinks`);
  },

  // 导入
  importMarkdown(data) {
    return request(`${BASE}/import`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  // 保存从对话中提取的知识
  saveKnowledge(data) {
    return request(`/api/chat/save-knowledge`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
};
