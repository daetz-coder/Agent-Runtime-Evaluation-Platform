# Wiki Agent 独立前端

Wiki Agent 的独立前端应用，与评估平台解耦，可单独启动。

## 启动

```bash
# 安装依赖
npm install

# 开发模式
npm run dev

# 构建生产版本
npm run build
```

默认运行在 `http://localhost:5173`，自动代理 `/api` 请求到后端 `http://127.0.0.1:8000`。

## 环境变量

创建 `.env` 文件：

```bash
# 后端 API 地址（默认 http://127.0.0.1:8000）
VITE_WIKI_API_BASE=http://127.0.0.1:8000

# API Key（可选，如果后端启用了认证）
VITE_API_KEY=your-api-key

# 评估平台地址（可选，用于跳转评估任务详情）
VITE_EVAL_BASE_URL=http://localhost:3000
```

## 目录结构

```
frontend/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
└── src/
    ├── main.ts              # 入口
    ├── App.vue              # 根组件
    ├── utils/
    │   └── auth.ts          # 认证工具
    └── wiki/
        ├── WikiAgentApp.vue # 主应用
        ├── api/
        │   └── index.js    # API 封装
        └── components/      # UI 组件
            ├── ChatView.vue
            ├── Sidebar.vue
            ├── WikiPage.vue
            ├── LinkGraph.vue
            └── ...
```

## 与评估平台的关系

- **完全独立**：不依赖评估平台的前端代码
- **共享后端**：通过 `/api/wiki/*` 和 `/api/chat/*` 与同一个 FastAPI 后端通信
- **可选集成**：通过 `VITE_EVAL_BASE_URL` 可跳转到评估平台的任务详情页
