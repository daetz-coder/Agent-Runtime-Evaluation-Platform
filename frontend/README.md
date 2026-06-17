# Agent Evaluation Platform - Frontend

基于 Vue 3 + Element Plus + ECharts 的 Agent 评估平台前端。

## 技术栈

- **Vue 3** - 渐进式 JavaScript 框架
- **Element Plus** - Vue 3 UI 组件库
- **ECharts** - 数据可视化图表库
- **Vue Router** - 官方路由管理器
- **Pinia** - Vue 状态管理库
- **Axios** - HTTP 客户端
- **Vite** - 下一代前端构建工具

## 功能特性

### 1. 仪表板 (Dashboard)
- 综合统计卡片
- 雷达图展示综合能力
- 趋势分析折线图
- 维度对比柱状图
- 仪表盘详细得分
- 最近任务列表
- 主要问题展示

### 2. 任务管理 (Tasks)
- 任务列表展示
- 创建新任务
- 添加执行轨迹
- 运行评估
- 任务详情查看

### 3. 评估记录 (Evaluations)
- 评估列表展示
- 状态筛选
- 得分范围筛选
- 评估详情查看

### 4. 评估详情 (Evaluation Detail)
- 综合得分展示
- 五维度详细评分
- 雷达图分析
- 详细反馈展示
- 执行轨迹时间线

### 5. 数据分析 (Analytics)
- 得分分布图
- 维度趋势对比
- 相关性分析热力图
- 性能热力图
- 智能洞察
- 改进建议

### 6. 系统设置 (Settings)
- 基本设置
- 评估配置
- 通知设置
- 关于页面

## 快速开始

### 安装依赖

```bash
cd frontend
npm install
```

### 开发模式

```bash
npm run dev
```

访问 http://localhost:3000

### 构建生产版本

```bash
npm run build
```

### 预览生产版本

```bash
npm run preview
```

## 项目结构

```
frontend/
├── public/              # 静态资源
├── src/
│   ├── api/             # API 接口
│   ├── assets/          # 资源文件
│   ├── components/      # 公共组件
│   ├── layouts/         # 布局组件
│   ├── router/          # 路由配置
│   ├── stores/          # 状态管理
│   ├── views/           # 页面组件
│   │   ├── Dashboard.vue        # 仪表板
│   │   ├── Tasks.vue            # 任务管理
│   │   ├── TaskDetail.vue       # 任务详情
│   │   ├── Evaluations.vue      # 评估记录
│   │   ├── EvaluationDetail.vue # 评估详情
│   │   ├── Analytics.vue        # 数据分析
│   │   └── Settings.vue         # 系统设置
│   ├── App.vue          # 根组件
│   └── main.ts          # 入口文件
├── index.html           # HTML 模板
├── package.json         # 项目配置
├── vite.config.ts       # Vite 配置
└── tsconfig.json        # TypeScript 配置
```

## 配置说明

### API 代理配置

在 `vite.config.ts` 中配置 API 代理：

```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',  # 后端地址
      changeOrigin: true,
    },
  },
}
```

### 环境变量

创建 `.env` 文件：

```env
VITE_API_BASE_URL=/api/v1
```

## 图表说明

### 雷达图 (Radar Chart)
展示五个评估维度的综合表现：
- 规划质量
- 战术决策
- 工具使用
- 记忆保持
- 重规划

### 仪表盘 (Gauge Chart)
展示各维度的详细得分，使用颜色区分：
- 绿色 (80-100): 优秀
- 黄色 (60-79): 良好
- 红色 (0-59): 需要改进

### 热力图 (Heatmap)
展示维度间的相关性或时间维度的性能变化。

## 自定义主题

在 `App.vue` 中修改 CSS 变量：

```css
:root {
  --primary-color: #409eff;
  --success-color: #67c23a;
  --warning-color: #e6a23c;
  --danger-color: #f56c6c;
  --info-color: #909399;
}
```

## 开发指南

### 添加新页面

1. 在 `src/views/` 创建新组件
2. 在 `src/router/index.ts` 添加路由
3. 在 `src/layouts/MainLayout.vue` 添加菜单项

### 添加新图表

1. 在组件中引入 ECharts
2. 创建图表容器 `<div ref="chartRef"></div>`
3. 初始化图表并设置选项
4. 监听窗口变化自动调整大小

### API 接口对接

在 `src/api/index.ts` 中添加新的接口方法：

```typescript
export const newApi = {
  getData(params: any) {
    return api.get('/new-endpoint', { params })
  },
}
```

## 常见问题

### Q: 图表不显示？
A: 检查 DOM 元素是否已挂载，确保在 `onMounted` 后初始化图表。

### Q: API 请求失败？
A: 检查后端服务是否启动，确认代理配置正确。

### Q: 样式不生效？
A: 检查是否使用了 `scoped` 样式，确认选择器优先级。

## 相关链接

- [Vue 3 文档](https://vuejs.org/)
- [Element Plus 文档](https://element-plus.org/)
- [ECharts 文档](https://echarts.apache.org/)
- [Vite 文档](https://vitejs.dev/)
