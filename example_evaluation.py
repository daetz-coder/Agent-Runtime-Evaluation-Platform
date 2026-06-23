"""
Agent Evaluation Platform - 完整评估示例

运行方式:
    python example_evaluation.py
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

    print("\n" + "=" * 60)
    print("📊 评估结果")
    print("=" * 60)

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

    print("\n" + "=" * 60)


def main():
    """主函数 - 演示完整评估流程"""

    print("🚀 Agent Evaluation Platform - 评估示例")
    print("=" * 60)

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

    # 4. 获取结果（轮询等待评估完成）
    print("\n📊 步骤4: 等待评估结果...")
    max_wait = 90  # 最多等待 90 秒
    for _ in range(max_wait):
        result = get_evaluation(eval_id)
        eval_data = result.get("evaluation", {})
        if eval_data and eval_data.get("overall_score") is not None:
            break
        time.sleep(2)
    else:
        print("⚠ 评估超时，可能仍在处理中")

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
