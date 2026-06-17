# DeepSeek API 配置指南

## 获取 DeepSeek API Key

### 步骤 1: 注册 DeepSeek 账号

1. 访问 [DeepSeek 官网](https://platform.deepseek.com/)
2. 点击"注册"按钮
3. 使用手机号或邮箱注册

### 步骤 2: 获取 API Key

1. 登录后，进入"API Keys"页面
2. 点击"创建 API Key"
3. 复制生成的 API Key（格式：`sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`）

### 步骤 3: 配置环境变量

编辑项目根目录下的 `.env` 文件：

```env
# DeepSeek API Configuration
DEEPSEEK_API_KEY="sk-your-actual-api-key-here"
DEEPSEEK_BASE_URL="https://api.deepseek.com"
DEEPSEEK_MODEL="deepseek-chat"

# Set DeepSeek as default provider
DEFAULT_LLM_PROVIDER="deepseek"
DEFAULT_LLM_MODEL="deepseek-chat"
```

## DeepSeek 模型选择

| 模型 | 说明 | 价格 |
|------|------|------|
| `deepseek-v4-flash` | **最新快速模型** | 查看官网 |
| `deepseek-chat` | 通用对话模型 (V3) | ¥1/百万tokens |
| `deepseek-coder` | 代码专用模型 | ¥1/百万tokens |
| `deepseek-reasoner` | 推理增强模型 (R1) | ¥4/百万tokens |

**推荐**：使用 `deepseek-v4-flash`，响应速度快。

## 测试配置

配置完成后，运行测试脚本：

```bash
# 启动后端
python -m app.main

# 在另一个终端运行测试
python test_api.py
```

## 常见问题

### Q: API Key 无效？
A: 确保 API Key 以 `sk-` 开头，没有多余的空格或引号。

### Q: 连接超时？
A: 检查网络连接，或尝试使用代理。

### Q: 额度不足？
A: 登录 DeepSeek 平台查看余额，必要时充值。

## 价格对比

| 平台 | 输入价格 | 输出价格 |
|------|----------|----------|
| DeepSeek | ¥1/百万tokens | ¥2/百万tokens |
| OpenAI GPT-4 | $30/百万tokens | $60/百万tokens |
| Claude 3 | $15/百万tokens | $75/百万tokens |

**DeepSeek 价格优势明显，适合开发和测试！**

## 示例代码

```python
from langchain_openai import ChatOpenAI

# 使用 DeepSeek
llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key="sk-your-key",
    openai_api_base="https://api.deepseek.com",
    temperature=0,
)

response = llm.invoke("Hello!")
print(response.content)
```
