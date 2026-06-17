# Agent Runtime Evaluation Platform

一个专业的 AI Agent 运行时质量评估平台，用于评估 Agent 的规划、战术决策、工具使用、记忆保持和重规划能力。

## 🎯 项目亮点

### 为什么选择这个方向？

```
❌ 不要做：Prompt Evaluation Platform（市场已饱和）
✅ 要做：Agent Runtime Evaluation Platform（蓝海市场）
```

### 核心创新点

1. **Planning Quality Score** - 几乎没人做的评估维度
2. **Memory Retention Score** - Long-running Agent 的核心问题
3. **Replan Evaluation** - 最有意思的评估维度

### 💰 成本优势

使用 **DeepSeek API**，成本仅为 OpenAI 的 1/30：
- DeepSeek: ¥1/百万tokens
- OpenAI GPT-4: $30/百万tokens (约 ¥210)

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Vue 3 + ECharts)                │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │  Dashboard  │  │   Tasks    │  │ Analytics  │           │
│  └────────────┘  └────────────┘  └────────────┘           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │    API     │  │  Service   │  │   Graph    │           │
│  └────────────┘  └────────────┘  └────────────┘           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              LangGraph Evaluation Workflow                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Planning → Tactical → Tool Use → Memory → Replan    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 Database (PostgreSQL)                        │
└─────────────────────────────────────────────────────────────┘
```

## 📁 项目结构

```
Agent Runtime Evaluation Platform/
├── app/                          # 后端代码
│   ├── api/v1/endpoints/         # API 端点
│   ├── core/                     # 配置管理
│   ├── db/                       # 数据库层
│   ├── evaluators/               # 5 个评估器 ⭐
│   ├── graphs/                   # LangGraph 工作流
│   ├── models/                   # 数据模型
│   ├── services/                 # 业务逻辑
│   └── main.py                   # FastAPI 入口
├── frontend/                     # 前端代码
│   ├── src/
│   │   ├── api/                  # API 接口
│   │   ├── components/           # 公共组件
│   │   ├── layouts/              # 布局组件
│   │   ├── router/               # 路由配置
│   │   ├── views/                # 页面组件
│   │   └── main.ts               # 入口文件
│   └── package.json              # 前端依赖
├── tests/                        # 测试代码
├── docs/                         # 项目文档
├── pyproject.toml                # Python 配置
└── README.md                     # 项目说明
```

## 🚀 快速开始

### 方式一：一键启动 (Windows)

```bash
# 双击运行 start.bat
start.bat
```

### 方式二：手动启动

#### 1. 配置 DeepSeek API

```bash
# 复制环境变量配置
cp .env.example .env

# 编辑 .env 文件，添加 DeepSeek API Key
DEEPSEEK_API_KEY="sk-your-api-key-here"
DEFAULT_LLM_PROVIDER="deepseek"
```

> 📖 详细配置指南：[DEEPSEEK_SETUP.md](DEEPSEEK_SETUP.md)

#### 2. 启动后端

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境 (Windows)
venv\Scripts\Activate.ps1

# 安装依赖
pip install -e .

# 启动后端
python -m app.main
```

后端运行在 http://localhost:8000

#### 3. 启动前端

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端运行在 http://localhost:3000

## 🎨 前端功能

### 1. 仪表板
- 综合统计卡片
- 雷达图展示综合能力
- 趋势分析折线图
- 维度对比柱状图
- 仪表盘详细得分

![Dashboard](docs/images/dashboard.png)

### 2. 任务管理
- 任务列表展示
- 创建新任务
- 添加执行轨迹
- 运行评估

### 3. 评估详情
- 综合得分展示
- 五维度详细评分
- 雷达图分析
- 执行轨迹时间线

### 4. 数据分析
- 得分分布图
- 维度趋势对比
- 相关性分析热力图
- 智能洞察
- 改进建议

## 📊 5 个评估维度

### 1. Planning Evaluator (规划评估器)
评估 Agent 的计划质量：
- **Coverage**: 是否覆盖关键里程碑
- **Ordering**: 步骤顺序是否合理
- **Granularity**: 细节层次是否合适
- **Completeness**: 计划是否完整

### 2. Tactical Evaluator (战术评估器)
评估下一步行动的质量：
- **Relevance**: 行动是否相关
- **Efficiency**: 行动是否高效
- **Correctness**: 行动是否正确

### 3. Tool Use Evaluator (工具使用评估器)
评估工具选择和使用：
- **Selection Quality**: 工具选择质量
- **Parameter Accuracy**: 参数准确性
- **Result Utilization**: 结果利用

### 4. Memory Evaluator (记忆评估器)
评估记忆质量（创新点）：
- **Retention**: 关键事实保持
- **Relevance**: 回忆信息相关性
- **Consistency**: 记忆一致性

### 5. Replan Evaluator (重规划评估器)
评估重规划决策（最有意思）：
- **Trigger Appropriateness**: 触发适当性
- **Adaptation Quality**: 适应质量
- **Learning from Failure**: 学习能力

## 🔧 API 接口

### 任务管理
```http
POST   /api/v1/tasks/                     # 创建任务
GET    /api/v1/tasks/{task_id}            # 获取任务
GET    /api/v1/tasks/                     # 列出任务
POST   /api/v1/tasks/{task_id}/trajectory # 添加轨迹
```

### 评估执行
```http
POST   /api/v1/evaluations/               # 运行评估
GET    /api/v1/evaluations/{id}           # 获取评估
```

### 报告分析
```http
GET    /api/v1/reports/summary            # 评估摘要
GET    /api/v1/reports/dimensions/{dim}   # 维度统计
```

## 💡 面试展示要点

### 1. 技术深度
- LangGraph 工作流编排
- 异步编程 (async/await)
- LLM 集成和提示工程
- Vue 3 + ECharts 数据可视化

### 2. 创新能力
- Planning Quality Score - 几乎没人做
- Memory Retention Score - Long-running Agent 核心问题
- Replan Evaluation - 最有意思的评估维度

### 3. 工程能力
- 清晰的项目结构
- 完整的测试覆盖
- 详细的 API 文档
- 专业的前端界面

### 4. 解决问题能力
- 理解真实痛点: "Agent Demo 很成功，上线以后不稳定"
- 提供解决方案: 运行时评估而非结果评估

## 📈 扩展方向

1. **添加更多评估维度**
   - 错误恢复能力
   - 资源使用效率
   - 安全性评估

2. **增强可视化**
   - 实时评估监控
   - 历史趋势分析
   - 对比分析

3. **集成更多 Agent 框架**
   - AutoGPT
   - BabyAGI
   - Custom Agents

4. **Benchmark 支持**
   - GAIA
   - SWE-bench
   - 自定义 Benchmark

## 📚 相关文档

- [架构设计文档](docs/architecture.md)
- [API 接口文档](docs/api.md)
- [快速开始指南](docs/getting_started.md)
- [前端开发文档](frontend/README.md)
- [项目总结文档](PROJECT_SUMMARY.md)
- [DeepSeek 配置指南](DEEPSEEK_SETUP.md)

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

## 🙏 致谢

- [LangGraph](https://langchain-ai.github.io/langgraph/) - 工作流编排
- [FastAPI](https://fastapi.tiangolo.com/) - Web 框架
- [Vue 3](https://vuejs.org/) - 前端框架
- [Element Plus](https://element-plus.org/) - UI 组件库
- [ECharts](https://echarts.apache.org/) - 数据可视化

---

**这个项目展示了你对 Agent Engineering 的深入理解，不仅仅是"如何让 Agent 做事"，更是"如何知道 Agent 做得好不好"。这正是未来 Agent 落地生产环境所需的核心能力。**
