# 贡献指南

感谢你对 Wiki Agent 的关注！

## 开发环境

```bash
# 克隆项目
git clone <repo-url>
cd Agent-Runtime-Evaluation-Platform

# 安装 Python 依赖
pip install -r requirements.txt

# 配置环境变量
cp app/wiki_agent/.env.example app/wiki_agent/.env
# 编辑 .env 填入 API Key

# 启动后端
python -m uvicorn app.main:app --reload --port 8000

# 启动前端（另一个终端）
cd app/wiki_agent/frontend
npm install && npm run dev
```

## 代码规范

- Python: 遵循 PEP 8，使用 type hints
- Vue: 遵循 Vue 3 Composition API 风格
- 提交信息: 使用 Conventional Commits 格式

```
feat(wiki-agent): 新增 xxx 功能
fix(wiki-agent): 修复 xxx 问题
refactor(wiki-agent): 重构 xxx
docs(wiki-agent): 更新文档
```

## 提交流程

1. Fork 本仓库
2. 创建特性分支: `git checkout -b feat/your-feature`
3. 提交变更: `git commit -m "feat(wiki-agent): your feature"`
4. 推送分支: `git push origin feat/your-feature`
5. 创建 Pull Request

## 报告问题

使用 GitHub Issues 报告 Bug 或提出功能建议，请包含：

- 问题描述
- 复现步骤
- 预期行为 vs 实际行为
- 环境信息（Python 版本、OS 等）
