# Agent Evaluation Platform 使用指南

## 快速开始

### 方式一：通过前端界面使用

1. 访问 http://localhost:3000
2. 点击"任务管理" → "创建任务"
3. 填写任务目标和上下文
4. 添加执行轨迹
5. 运行评估
6. 查看评估结果

### 方式二：通过 API 调用

```python
import httpx

BASE_URL = "http://localhost:8000/api/v1"
```

---

## 完整评估流程

### 步骤 1：创建任务

```python
import httpx

# 创建任务
response = httpx.post("http://localhost:8000/api/v1/tasks/", json={
    "goal": "修复登录页面的JWT认证漏洞",
    "context": {
        "project": "电商平台",
        "language": "Python",
        "framework": "FastAPI",
        "key_facts": [
            "项目使用JWT进行用户认证",
            "数据库使用PostgreSQL",
            "前端使用React"
        ]
    }
})

task = response.json()
task_id = task["id"]
print(f"任务创建成功: {task_id}")
```

### 步骤 2：添加执行轨迹

执行轨迹记录了 Agent 的每一步操作：

```python
# 添加执行轨迹
trajectory = [
    # 步骤1: 制定计划
    {
        "step_number": 1,
        "action_type": "plan",
        "action_detail": {
            "goal": "修复JWT认证漏洞",
            "steps": [
                {"description": "搜索认证相关代码"},
                {"description": "分析JWT实现"},
                {"description": "识别安全漏洞"},
                {"description": "实现修复方案"},
                {"description": "运行测试验证"}
            ]
        }
    },
    
    # 步骤2: 搜索代码
    {
        "step_number": 2,
        "action_type": "tool_call",
        "action_detail": {
            "tool_name": "search_code",
            "input": {"query": "JWT authentication"}
        },
        "observation": "Found: auth/jwt_handler.py, auth/middleware.py, auth/utils.py"
    },
    
    # 步骤3: 读取文件
    {
        "step_number": 3,
        "action_type": "tool_call",
        "action_detail": {
            "tool_name": "read_file",
            "input": {"file_path": "auth/jwt_handler.py"}
        },
        "observation": "def create_token(data): ... def verify_token(token): ..."
    },
    
    # 步骤4: 思考分析
    {
        "step_number": 4,
        "action_type": "think",
        "action_detail": {
            "thought": "发现JWT token没有过期时间设置，这是一个安全漏洞"
        }
    },
    
    # 步骤5: 实现修复
    {
        "step_number": 5,
        "action_type": "tool_call",
        "action_detail": {
            "tool_name": "edit_file",
            "input": {
                "file_path": "auth/jwt_handler.py",
                "changes": "添加token过期时间参数"
            }
        },
        "observation": "File updated successfully"
    },
    
    # 步骤6: 运行测试
    {
        "step_number": 6,
        "action_type": "tool_call",
        "action_detail": {
            "tool_name": "run_tests",
            "input": {"test_path": "tests/test_auth.py"}
        },
        "observation": "All 15 tests passed"
    }
]

# 提交轨迹
response = httpx.post(
    f"http://localhost:8000/api/v1/tasks/{task_id}/trajectory",
    json=trajectory
)
print(f"轨迹添加成功: {response.json()}")
```

### 步骤 3：运行评估

```python
# 运行评估
response = httpx.post("http://localhost:8000/api/v1/evaluations/", json={
    "task_id": task_id,
    "include_details": True
})

evaluation = response.json()
print(f"评估完成: {evaluation['id']}")
```

### 步骤 4：查看评估结果

```python
# 获取评估详情
response = httpx.get(f"http://localhost:8000/api/v1/evaluations/{evaluation['id']}")
result = response.json()

# 打印评估结果
eval_data = result["evaluation"]
print("\n" + "="*50)
print("评估结果")
print("="*50)
print(f"综合得分: {eval_data['overall_score']:.1f}/100")
print(f"\n各维度得分:")
print(f"  - 规划质量: {eval_data['planning']['overall']:.1f}/100")
print(f"  - 战术决策: {eval_data['tactical']['overall']:.1f}/100")
print(f"  - 工具使用: {eval_data['tool_use']['overall']:.1f}/100")
print(f"  - 记忆保持: {eval_data['memory']['overall']:.1f}/100")
print(f"  - 重规划:   {eval_data['replan']['overall']:.1f}/100")
print(f"\n总结: {eval_data['summary']}")
print(f"\n改进建议:")
for rec in eval_data['recommendations']:
    print(f"  - {rec}")
```

---

## 完整示例脚本

创建 `example_evaluation.py`：

```python
"""
完整评估示例脚本
"""

import httpx
import json
import time

BASE_URL = "http://localhost:8000/api/v1"


def create_task(goal: str, context: dict = None) -> str:
    """创建评估任务"""
    response = httpx.post(f"{BASE_URL}/tasks/", json={
        "goal": goal,
        "context": context or {}
    })
    response.raise_for_status()
    return response.json()["id"]


def add_trajectory(task_id: str, steps: list):
    """添加执行轨迹"""
    response = httpx.post(
        f"{BASE_URL}/tasks/{task_id}/trajectory",
        json=steps
    )
    response.raise_for_status()
    return response.json()


def run_evaluation(task_id: str) -> dict:
    """运行评估"""
    response = httpx.post(f"{BASE_URL}/evaluations/", json={
        "task_id": task_id,
        "include_details": True
    })
    response.raise_for_status()
    return response.json()


def get_evaluation(eval_id: str) -> dict:
    """获取评估结果"""
    response = httpx.get(f"{BASE_URL}/evaluations/{eval_id}")
    response.raise_for_status()
    return response.json()


def print_results(evaluation: dict):
    """打印评估结果"""
    eval_data = evaluation.get("evaluation", {})
    
    print("\n" + "="*60)
    print("📊 评估结果")
    print("="*60)
    
    overall = eval_data.get("overall_score", 0)
    print(f"\n🎯 综合得分: {overall:.1f}/100")
    
    print(f"\n📈 各维度得分:")
    dimensions = [
        ("规划质量", "planning"),
        ("战术决策", "tactical"),
        ("工具使用", "tool_use"),
        ("记忆保持", "memory"),
        ("重规划", "replan")
    ]
    
    for name, key in dimensions:
        score = eval_data.get(key, {}).get("overall", 0)
        bar = "█" * int(score / 5) + "░" * (20 - int(score / 5))
        print(f"  {name}: {bar} {score:.1f}/100")
    
    summary = eval_data.get("summary", "")
    if summary:
        print(f"\n📝 总结: {summary}")
    
    recommendations = eval_data.get("recommendations", [])
    if recommendations:
        print(f"\n💡 改进建议:")
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")
    
    print("\n" + "="*60)


def main():
    """主函数 - 演示完整评估流程"""
    
    print("🚀 Agent Evaluation Platform - 评估示例")
    print("="*60)
    
    # 1. 创建任务
    print("\n📋 步骤1: 创建评估任务...")
    task_id = create_task(
        goal="实现用户注册功能，包括邮箱验证",
        context={
            "project": "Web应用",
            "language": "Python",
            "framework": "FastAPI",
            "requirements": [
                "邮箱格式验证",
                "密码强度检查",
                "发送验证邮件",
                "防止重复注册"
            ]
        }
    )
    print(f"✅ 任务创建成功: {task_id}")
    
    # 2. 添加执行轨迹
    print("\n📝 步骤2: 添加执行轨迹...")
    trajectory = [
        {
            "step_number": 1,
            "action_type": "plan",
            "action_detail": {
                "goal": "实现用户注册功能",
                "steps": [
                    {"description": "设计数据库模型"},
                    {"description": "实现邮箱验证逻辑"},
                    {"description": "创建注册API端点"},
                    {"description": "添加密码强度检查"},
                    {"description": "编写测试用例"}
                ]
            }
        },
        {
            "step_number": 2,
            "action_type": "tool_call",
            "action_detail": {
                "tool_name": "search_code",
                "input": {"query": "user model"}
            },
            "observation": "Found: models/user.py, models/base.py"
        },
        {
            "step_number": 3,
            "action_type": "tool_call",
            "action_detail": {
                "tool_name": "read_file",
                "input": {"file_path": "models/user.py"}
            },
            "observation": "class User(Base): id, email, password_hash, is_verified"
        },
        {
            "step_number": 4,
            "action_type": "think",
            "action_detail": {
                "thought": "用户模型已存在，需要添加邮箱验证字段和验证逻辑"
            }
        },
        {
            "step_number": 5,
            "action_type": "tool_call",
            "action_detail": {
                "tool_name": "create_file",
                "input": {
                    "file_path": "services/email_verification.py",
                    "content": "实现邮箱验证服务"
                }
            },
            "observation": "File created successfully"
        },
        {
            "step_number": 6,
            "action_type": "tool_call",
            "action_detail": {
                "tool_name": "run_tests",
                "input": {"test_path": "tests/test_registration.py"}
            },
            "observation": "12 passed, 2 failed"
        },
        {
            "step_number": 7,
            "action_type": "replan",
            "action_detail": {
                "reason": "测试失败，需要修复邮箱验证逻辑",
                "new_plan": [
                    {"description": "分析失败的测试用例"},
                    {"description": "修复邮箱验证逻辑"},
                    {"description": "重新运行测试"}
                ]
            }
        },
        {
            "step_number": 8,
            "action_type": "tool_call",
            "action_detail": {
                "tool_name": "edit_file",
                "input": {
                    "file_path": "services/email_verification.py",
                    "changes": "修复验证链接生成逻辑"
                }
            },
            "observation": "File updated successfully"
        },
        {
            "step_number": 9,
            "action_type": "tool_call",
            "action_detail": {
                "tool_name": "run_tests",
                "input": {"test_path": "tests/test_registration.py"}
            },
            "observation": "All 14 tests passed"
        }
    ]
    
    add_trajectory(task_id, trajectory)
    print("✅ 轨迹添加成功")
    
    # 3. 运行评估
    print("\n🔍 步骤3: 运行评估...")
    evaluation = run_evaluation(task_id)
    eval_id = evaluation["id"]
    print(f"✅ 评估完成: {eval_id}")
    
    # 4. 获取结果
    print("\n📊 步骤4: 获取评估结果...")
    time.sleep(1)  # 等待评估完成
    result = get_evaluation(eval_id)
    
    # 5. 打印结果
    print_results(result)
    
    return result


if __name__ == "__main__":
    try:
        main()
    except httpx.ConnectError:
        print("\n❌ 连接失败！请确保后端服务正在运行:")
        print("   python -m app.main")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
```

---

## 前端使用说明

### 1. 访问仪表板

打开 http://localhost:3000，查看：
- 综合统计
- 雷达图
- 趋势分析

### 2. 创建任务

1. 点击左侧菜单"任务管理"
2. 点击"创建任务"按钮
3. 填写：
   - 任务目标：描述 Agent 需要完成的任务
   - 上下文：项目相关信息（可选）
4. 点击"创建"

### 3. 添加执行轨迹

1. 在任务列表中，点击"添加轨迹"
2. 添加步骤：
   - **计划 (plan)**: Agent 的计划
   - **工具调用 (tool_call)**: 调用的工具和结果
   - **思考 (think)**: Agent 的思考过程
   - **重规划 (replan)**: 重新规划
3. 点击"提交"

### 4. 运行评估

1. 点击任务的"评估"按钮
2. 等待评估完成
3. 自动跳转到评估详情页

### 5. 查看结果

评估详情页显示：
- 综合得分（仪表盘）
- 五个维度详细得分
- 雷达图分析
- 详细反馈和建议
- 执行轨迹时间线

---

## 评估维度说明

| 维度 | 评估内容 | 评分标准 |
|------|----------|----------|
| **规划质量** | 计划的完整性、顺序、粒度 | 0-100分 |
| **战术决策** | 每一步行动的合理性 | 0-100分 |
| **工具使用** | 工具选择和参数准确性 | 0-100分 |
| **记忆保持** | 关键信息的记忆和使用 | 0-100分 |
| **重规划** | 何时重新规划、规划质量 | 0-100分 |

---

## API 参考

### 任务管理

```bash
# 创建任务
POST /api/v1/tasks/
{
  "goal": "任务目标",
  "context": {"key": "value"}
}

# 获取任务
GET /api/v1/tasks/{task_id}

# 列出任务
GET /api/v1/tasks/?skip=0&limit=100

# 添加轨迹
POST /api/v1/tasks/{task_id}/trajectory
[
  {
    "step_number": 1,
    "action_type": "plan",
    "action_detail": {...}
  }
]
```

### 评估执行

```bash
# 运行评估
POST /api/v1/evaluations/
{
  "task_id": "任务ID",
  "include_details": true
}

# 获取评估
GET /api/v1/evaluations/{evaluation_id}
```

### 报告分析

```bash
# 获取摘要
GET /api/v1/reports/summary

# 维度统计
GET /api/v1/reports/dimensions/{dimension}
```

---

## 常见问题

### Q: 评估需要多长时间？
A: 通常 10-30 秒，取决于轨迹长度和 LLM 响应速度。

### Q: 如何提高评估得分？
A: 
1. 制定清晰的计划
2. 选择合适的工具
3. 记录关键信息
4. 在失败时及时重新规划

### Q: 可以评估哪些类型的 Agent？
A: 任何产生执行轨迹的 Agent，包括：
- 代码生成 Agent
- 问题解决 Agent
- 数据分析 Agent
- 自动化工作流
