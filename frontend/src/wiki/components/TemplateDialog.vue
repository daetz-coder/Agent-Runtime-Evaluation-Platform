<template>
  <div class="template-overlay" @click.self="$emit('close')">
    <div class="template-dialog">
      <div class="template-header">
        <h3>选择词条模板</h3>
        <button class="btn-close" @click="$emit('close')">×</button>
      </div>

      <div class="template-list">
        <div
          v-for="tpl in templates"
          :key="tpl.name"
          class="template-card"
          @click="selectTemplate(tpl)"
        >
          <div class="template-icon">{{ tpl.icon }}</div>
          <div class="template-info">
            <div class="template-name">{{ tpl.name }}</div>
            <div class="template-desc">{{ tpl.desc }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const emit = defineEmits(["close", "select"]);

const templates = [
  {
    name: "百科词条",
    icon: "📚",
    desc: "标准百科词条：定义、详细说明、示例、参考资料、相关词条",
    summary: "对词条的一句话定义",
    category: "未分类",
    title: "词条名称",
    content: `# 词条名称

## 定义

对这个词条的一句话简洁定义。

## 详细说明

对词条的详细解释，包括：
- 概念的起源和背景
- 核心特征和属性
- 与其他概念的关系

## 示例

具体的使用示例或实例说明。

\`\`\`
示例代码或具体场景
\`\`\`

## 参考资料

- [参考来源1](https://example.com)
- [参考来源2](https://example.com)

## 相关词条

- [[相关词条1]]
- [[相关词条2]]
`,
  },
  {
    name: "技术概念",
    icon: "⚙️",
    desc: "技术术语词条：定义、原理、应用场景、代码示例",
    summary: "技术概念的简要定义",
    category: "技术",
    title: "技术概念名称",
    content: `# 技术概念名称

## 定义

技术概念的简洁定义。

## 原理

### 工作原理

详细解释技术原理。

### 核心组件

- 组件1：说明
- 组件2：说明

## 应用场景

1. 场景1：说明
2. 场景2：说明

## 代码示例

\`\`\`python
# 示例代码
\`\`\`

## 优缺点

| 优点 | 缺点 |
|------|------|
| 优点1 | 缺点1 |

## 参考资料

- [参考链接](https://example.com)

## 相关词条

- [[相关技术1]]
- [[相关技术2]]
`,
  },
  {
    name: "工具/框架",
    icon: "🔧",
    desc: "软件工具或框架词条：简介、功能、使用方法、对比",
    summary: "工具/框架的简要介绍",
    category: "工具",
    title: "工具名称",
    content: `# 工具名称

## 定义

工具的简要介绍和定位。

## 核心功能

- 功能1：说明
- 功能2：说明
- 功能3：说明

## 快速开始

### 安装

\`\`\`bash
# 安装命令
\`\`\`

### 基本使用

\`\`\`python
# 使用示例
\`\`\`

## 使用场景

适用场景和最佳实践。

## 与其他工具对比

| 特性 | 本工具 | 替代方案A | 替代方案B |
|------|--------|----------|----------|
| 特性1 | | | |

## 参考资料

- [官方文档](https://example.com)
- [GitHub](https://github.com)

## 相关词条

- [[相关工具1]]
- [[相关工具2]]
`,
  },
  {
    name: "人物/团队",
    icon: "👤",
    desc: "人物或团队词条：简介、成就、贡献、相关项目",
    summary: "人物或团队的简要介绍",
    category: "人物",
    title: "人物/团队名称",
    content: `# 人物/团队名称

## 简介

一句话介绍。

## 背景

- 职位/角色：
- 所属组织：
- 领域：

## 主要贡献

1. 贡献1：说明
2. 贡献2：说明

## 代表作品/项目

- 作品1：简要说明
- 作品2：简要说明

## 名言/观点

> 代表性名言或观点

## 参考资料

- [参考链接](https://example.com)

## 相关词条

- [[相关人物1]]
- [[相关项目1]]
`,
  },
];

function selectTemplate(tpl) {
  emit("select", {
    title: tpl.title,
    summary: tpl.summary || "",
    category: tpl.category || "",
    content: tpl.content,
  });
  emit("close");
}
</script>

<style scoped>
.template-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.template-dialog {
  width: 520px;
  max-height: 80vh;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.template-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #e8e8e8;
}

.template-header h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.btn-close {
  width: 32px;
  height: 32px;
  background: transparent;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: #666;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-close:hover {
  background: #f0f0f0;
}

.template-list {
  padding: 12px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.template-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.template-card:hover {
  border-color: #4a90d9;
  background: #f8fbff;
}

.template-icon {
  font-size: 28px;
  flex-shrink: 0;
}

.template-info {
  flex: 1;
  min-width: 0;
}

.template-name {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 4px;
}

.template-desc {
  font-size: 12px;
  color: #888;
}
</style>
