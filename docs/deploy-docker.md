# Docker 部署指南

> **适用版本**: v0.1.0 · **环境要求**: Docker 24+ · Docker Compose 2.20+

---

## 目录

- [快速开始（5 分钟）](#快速开始5-分钟)
- [部署模式说明](#部署模式说明)
- [详细配置](#详细配置)
- [生产环境部署](#生产环境部署)
- [常见问题](#常见问题)

---

## 快速开始（5 分钟）

### 前提条件

- 安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)（Windows/Mac）或 Docker Engine（Linux）
- 至少一个 LLM API Key（推荐 [DeepSeek](https://platform.deepseek.com/)）

### 步骤

```bash
# 1. 克隆项目
git clone git@github.com:daetz-coder/Agent-Runtime-Evaluation-Platform.git
cd Agent-Runtime-Evaluation-Platform

# 2. 切换到 dev 分支
git checkout dev

# 3. 配置环境变量
cp .env.docker .env
```

编辑 `.env`，填入你的 API Key：

```bash
# 至少配一个
DEEPSEEK_API_KEY=sk-your-key-here
# ZHIPUAI_API_KEY=your-key    # 可选（GLM 多模型共识）
# QWEN_API_KEY=your-key       # 可选（Qwen 多模型共识）

# 生产环境必须修改
SECRET_KEY=<运行 python -c "import secrets; print(secrets.token_hex(32))" 生成>
```

```bash
# 4. 启动（最小部署）
docker compose up backend
```

首次启动需要下载模型（约 1.1GB），耗时 1-3 分钟。之后启动秒级。

### 验证

打开浏览器访问 `http://localhost:8000`：

| 页面 | 地址 | 说明 |
|------|------|------|
| 仪表盘 | `http://localhost:8000` | 评估数据总览 |
| API 文档 | `http://localhost:8000/docs` | Swagger UI |
| 健康检查 | `http://localhost:8000/health` | 系统状态 |

看到仪表盘即部署成功。

---

## 部署模式说明

项目支持三种部署模式，按需选择：

### 模式一：最小部署（单容器）

**一句话：一个容器跑全部，零外部依赖。**

```bash
docker compose up backend
```

适合：个人试用、本地开发、演示环境。

包含：FastAPI + 6 个评估器 + Wiki Agent + Milvus Lite（文件向量库）+ SQLite + 前端。

特点：
- 不需要 Redis，所有缓存功能自动降级
- 不需要 Celery，评估任务使用 BackgroundTasks 同步执行
- 不需要 PostgreSQL，默认 SQLite 单文件存储
- 所有数据存储在 Docker 卷中，容器删除不丢

### 模式二：带 Redis 缓存

**一句话：在模式一基础上增加 LLM 缓存和限流。**

```bash
docker compose up backend redis
```

适合：频繁使用评估、需要控制 API 费用的场景。

Redis 提供：
- **LLM 相同轨迹缓存**（24h）：相同轨迹+目标再次评估时，直接返回缓存结果
- **报表聚合缓存**：仪表盘响应时间从秒级降至 10ms 以下
- **接口限流**：防止 LLM API 费用失控，默认每分钟 10 次评估
- **Wiki 会话缓存**：对话加载速度提升

Redis 不可用时**静默降级**，核心功能不受影响。

### 模式三：全量部署（Redis + Celery）

**一句话：在模式二基础上增加异步评估队列。**

```bash
docker compose --profile full up -d
```

适合：生产环境、多用户并发使用的场景。

Celery Worker 将评估任务异步执行，主进程不阻塞：
- 评估请求提交后立即返回，后台完成评分
- 指数退避重试（最多 3 次）
- Worker 崩溃后自动重入队列

---

## 详细配置

### 目录结构（容器内）

```
/app/
├── app/                     # 后端代码
│   ├── main.py             # FastAPI 入口（含前端 SPA fallback）
│   ├── evaluators/         # 6 个 LLM-as-Judge 评估器
│   ├── wiki_agent/
│   │   ├── data/           # ← VOLUME wiki_data
│   │   │   ├── chat.db           # 会话记录
│   │   │   ├── milvus.db         # Milvus Lite 向量库
│   │   │   ├── bm25_index.pkl    # BM25 关键词索引
│   │   │   ├── checkpoints.db    # LangGraph checkpoint
│   │   │   └── knowledge/        # Markdown 知识条目
│   │   └── ...
│   └── ...
├── frontend/dist/           # 前端构建产物（Dockerfile 中编译）
├── data/                    # ← VOLUME app_data
│   └── agent_eval.db       # 评估结果主数据库
└── ...
```

### 环境变量速查

| 变量 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `DEEPSEEK_API_KEY` | **是\*** | — | DeepSeek LLM |
| `ZHIPUAI_API_KEY` | 否 | — | GLM 多模型共识 |
| `QWEN_API_KEY` | 否 | — | Qwen 多模型共识 |
| `SECRET_KEY` | **是** | — | 生产必需，`python -c "import secrets; print(secrets.token_hex(32))"` |
| `AUTH_ENABLED` | 否 | `false` | 生产建议开启 |
| `API_KEY` | 否 | — | AUTH_ENABLED=true 时必须设置 |
| `DATABASE_URL` | 否 | `sqlite:///./data/agent_eval.db` | 生产建议换 PostgreSQL |
| `REDIS_URL` | 否 | `redis://redis:6379/0` | 不配置则自动降级 |
| `CORS_ORIGINS` | 否 | `["http://localhost:8000"]` | 前端的来源域名 |
| `EVAL_PARALLEL` | 否 | `true` | 6 评估器并行 |
| `RATE_LIMIT_ENABLED` | 否 | `true` | 接口限流 |
| `RATE_LIMIT_EVAL_PER_MINUTE` | 否 | `10` | 每分钟最多评估次数 |

\* `DEEPSEEK_API_KEY` / `ZHIPUAI_API_KEY` / `QWEN_API_KEY` 三选一。

---

## 生产环境部署

### 使用 PostgreSQL

默认 SQLite 适合单用户场景。多用户并发建议换 PostgreSQL：

```yaml
# docker-compose.yml 中增加 postgres 服务
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: agent_eval
      POSTGRES_USER: agent_eval
      POSTGRES_PASSWORD: <your-password>
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "agent_eval"]

volumes:
  postgres_data:
```

修改 `.env`：

```bash
DATABASE_URL=postgresql+asyncpg://agent_eval:<your-password>@postgres:5432/agent_eval
```

### 使用外部 Milvus（可选）

Milvus Lite 以文件形式存储，适合单机。大规模场景可换独立 Milvus 服务：

```bash
# .env 中
MILVUS_URI=http://milvus:19530
# 而非默认的 /app/app/wiki_agent/data/milvus.db
```

### HTTPS（Nginx 反代）

`nginx/nginx.conf` 已提供完整反代配置，包含：

- HTTP→HTTPS 跳转
- SSL 证书挂载
- SSE 流式端点的非缓冲代理
- Gzip 压缩
- 静态资源缓存

使用（需提供 SSL 证书）：

```bash
# 1. 将证书放入 nginx/certs/
# 2. 修改 nginx/nginx.conf 中的 server_name
# 3. 启动
docker compose --profile full up -d nginx
```

### 资源估算

| 组件 | CPU | 内存 | 存储 |
|------|-----|------|------|
| 后端 | 1 核 | 512MB-1GB | — |
| Redis | — | 100MB | — |
| Celery Worker | 1 核 | 512MB | — |
| Milvus Lite | — | — | 随文档量增长（每万条约 50MB） |
| PostgreSQL | — | — | 随评估量增长 |

最小部署合计：约 **1 核 / 1GB 内存**即可运行。

---

## 常见问题

### Q：首次启动报错 "No module named 'app'"

检查启动命令是否正确：

```bash
# 正确（python -m）：
docker compose up backend

# 不要直接在容器内：
python app/main.py   # 错误！
```

### Q：启动后访问 localhost:8000 看到的是 JSON 而不是前端

前端未正确构建。在项目根目录手动构建并检查：

```bash
cd frontend && npm install && npm run build
ls frontend/dist/       # 应该有 index.html 和 assets/
```

然后重新构建镜像：

```bash
docker compose build --no-cache backend
docker compose up backend
```

### Q：评估一直卡住或报 API 错

检查 API Key 配置：

```bash
# 确认 .env 文件存在且 Key 正确
docker compose exec backend env | grep API_KEY

# 确认 Key 未被空格或引号包裹（.env 中不要加引号）
# 正确：DEEPSEEK_API_KEY=sk-abc123
# 错误：DEEPSEEK_API_KEY="sk-abc123"
```

### Q：容器重启后数据会丢吗？

不会。所有运行时数据挂载在 Docker 卷中：

```bash
# 查看卷列表
docker volume ls | grep agent-eval

# 具体位置
docker volume inspect agent-eval-platform_wiki_data
```

只有执行 `docker compose down -v` 才会清除数据。

### Q：想从头清理所有数据

```bash
# 停止并删除容器 + 卷
docker compose down -v

# 重新构建（不使用缓存）
docker compose build --no-cache backend

# 重新启动
docker compose up backend
```

### Q：如何更新到最新版本？

```bash
git checkout dev
git pull origin dev

# 重新构建并启动
docker compose build backend
docker compose up backend
```

### Q：如何查看日志？

```bash
# 跟随日志
docker compose logs -f backend

# 最后 100 行
docker compose logs --tail=100 backend
```
