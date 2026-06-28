# 快速开始指南

## 环境要求

- Python 3.11+
- Node.js 18+
- Git
- Redis (可选 — 应用会自动降级，无需 Redis 也能正常运行)

## 安装

```bash
git clone https://github.com/daetz-coder/Agent-Runtime-Evaluation-Platform.git
cd Agent-Runtime-Evaluation-Platform

# 配置 API Key
cp .env.example .env
# 编辑 .env：填入 DEEPSEEK_API_KEY（必填），可选 ZHIPUAI_API_KEY / QWEN_API_KEY

# 安装后端依赖
pip install -e ".[dev]"

# 安装前端依赖
cd frontend && npm install && cd ..

# (可选) 启动 Redis — 用于缓存和限流，不启动则自动降级
# Docker 方式:
docker compose up redis -d
# 或本地安装:
redis-server
```

## 启动

### 方式一：命令行

```bash
# 终端 1：启动后端
python -m app.main
# → http://localhost:8000

# 终端 2：启动前端
cd frontend && npm run dev
# → http://localhost:3000
```

### 方式二：Docker Compose

```bash
cp .env.example .env  # 填入 DEEPSEEK_API_KEY
docker compose up --build
```

### 方式三：Windows 一键

```bash
start.bat
```

## 访问地址

| 地址 | 内容 |
|------|------|
| `http://localhost:3000` | 评估平台前端 |
| `http://localhost:3000/wiki-agent` | Wiki Agent |
| `http://localhost:8000/docs` | Swagger API 文档 |
| `http://localhost:8000/health` | 健康检查 |

## 验证

```bash
# 健康检查
curl http://localhost:8000/health

# 运行示例评估
python example_evaluation.py

# SDK 演示
python example/sdk_demo.py
```

## 运行基准测试

```bash
# 多轨迹评估分布（6 条 × 6 评估器）
python -m tests.benchmark_score_distribution

# 多模型成本对比
python -m tests.benchmark_multimodel

# 评估器准确性验证
python -m tests.eval_evaluator_accuracy

# Wiki-Agent 检索评估
python -m tests.eval_retrieval_standalone

# Adapter 集成测试
python -m tests.test_adapters
```

## 数据库迁移

```bash
alembic upgrade head     # 应用所有迁移
alembic revision --autogenerate -m "描述"  # 生成新迁移
```

## 配置参考

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key（必填） | - |
| `ZHIPUAI_API_KEY` | 智谱 GLM-4 API Key | - |
| `QWEN_API_KEY` | 阿里 DashScope API Key | - |
| `DEFAULT_LLM_PROVIDER` | 默认 LLM（deepseek/glm/qwen） | deepseek |
| `EVAL_PARALLEL` | 是否并行评估 | true |
| `AUTH_ENABLED` | 是否启用 API 认证 | false |
| `EVAL_WEBHOOK_URL` | 评估完成通知 URL | - |
| `REDIS_URL` | Redis 连接地址（可选，不可用时自动降级） | redis://localhost:6379/0 |
| `CACHE_LLM_RESPONSES` | 是否缓存 LLM 评估结果（节省 API 费用） | true |
| `CACHE_LLM_TTL` | LLM 缓存有效期（秒） | 86400 (24h) |
| `CACHE_REPORTS_TTL` | 报表聚合缓存有效期（秒） | 300 (5min) |
| `RATE_LIMIT_ENABLED` | 是否启用评估接口限流（需 Redis） | true |
| `RATE_LIMIT_EVAL_PER_MINUTE` | 每客户端每分钟最大评估请求数 | 10 |
