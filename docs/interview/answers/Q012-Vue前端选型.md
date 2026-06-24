# Q12: 前端为什么用 Vue 3 而不是 React？对 Agent 开发工程师这个岗位，前端能力是否必须？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q012 |
| 分类 | 项目理解与动机 |
| 难度 | ★ |

## 问题

前端为什么用 Vue 3 而不是 React？对 Agent 开发工程师这个岗位，前端能力是否必须？

## 参考答案

前端 Vue3 + Vite + Element Plus + ECharts，views 含 Dashboard/Tasks/Evaluations/Analytics/Benchmark/WikiAgent/Settings。选型因团队熟悉度与 Element Plus 后台组件成熟；Agent 岗不必须深前端，但需理解 API 契约（202 异步评估、SSE progress）与 trajectory 展示。vite.config 代理 /api 到 8000。评估工程师应能读 Evaluation 详情页与 Benchmark 页源码。

## 代码依据

- `frontend/src/views/Evaluations.vue`
- `frontend/vite.config.ts`
- `frontend/package.json`

## 回答要点

- Vue3 Composition API + Pinia
- ECharts 展示六维雷达与趋势
- Agent 岗重点 API/数据流非 CSS
- proxy 解决 dev CORS

## 常见追问

**Q: 必须会 Vue 吗？**

A: 能读组件与调 API 即可，不要求写复杂 UI。

**Q: 为何不用 React？**

A: 项目历史与 Element Plus 生态，非技术优劣绝对判断。

## 相关题目

- [Q011](../answers/Q011-Milvus选型.md)
- [Q013](../answers/Q013-轨迹驱动评估.md)
