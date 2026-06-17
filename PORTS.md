# 端口配置说明

## 📊 端口分配

| 服务 | 端口 | 说明 |
|------|------|------|
| **评估平台后端** | 8001 | FastAPI 后端 |
| **评估平台前端** | 3000 | Vue 前端 |
| **webRAGChat** | 8000 | Agent 服务 |

---

## 🔧 配置文件位置

### 评估平台后端

```env
# D:\Agent Runtime Evaluation Platform\.env
HOST="0.0.0.0"
PORT=8001
```

### 评估平台前端

```typescript
// D:\Agent Runtime Evaluation Platform\frontend\vite.config.ts
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8001',  // 代理到后端
      changeOrigin: true,
    },
  },
},
```

### webRAGChat

```env
# D:\2026Agent\webRAGChat\.env
HOST="0.0.0.0"
PORT=8000
```

---

## 🚀 启动顺序

```bash
# 1. 启动评估平台后端 (端口 8001)
cd D:\Agent\Runtime\Evaluation\Platform
python -m app.main

# 2. 启动评估平台前端 (端口 3000)
cd D:\Agent\Runtime\Evaluation\Platform\frontend
npm run dev

# 3. 启动 webRAGChat (端口 8000)
cd D:\2026Agent\webRAGChat
python run_server.py
```

---

## 🔗 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| 评估平台前端 | http://localhost:3000 | 可视化界面 |
| 评估平台后端 | http://localhost:8001 | API 接口 |
| 评估平台文档 | http://localhost:8001/docs | Swagger 文档 |
| webRAGChat | http://localhost:8000 | Agent 服务 |

---

## 💡 为什么这样分配？

- **webRAGChat 用 8000**：这是 Agent 服务的标准端口
- **评估平台用 8001**：避免与 Agent 服务冲突
- **前端用 3000**：这是前端开发的标准端口

---

## ❓ 常见问题

### Q: 端口被占用怎么办？

A: 检查端口使用情况：
```bash
# Windows
netstat -ano | findstr :8000
netstat -ano | findstr :8001

# Linux/Mac
lsof -i :8000
lsof -i :8001
```

### Q: 如何修改端口？

A: 修改对应的配置文件：
- 评估平台后端：`.env` 中的 `PORT`
- 评估平台前端：`vite.config.ts` 中的 `port` 和 `proxy.target`
- webRAGChat：`.env` 中的 `PORT`

### Q: 前端无法连接后端？

A: 检查：
1. 后端是否启动
2. 端口是否正确（8001）
3. 代理配置是否正确
