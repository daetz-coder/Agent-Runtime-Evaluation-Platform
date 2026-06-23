"""Synthetic trajectories for monotonicity benchmark."""

from datetime import datetime, timezone


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


TRAJ_EXCELLENT = [
    {"step_number": 1, "action_type": "plan", "action_detail": {
        "goal": "实现用户 OAuth2.0 登录",
        "steps": [
            {"description": "调研 OAuth2.0 规范，确定授权码模式"},
            {"description": "设计 User/OAuthToken 数据库模型"},
            {"description": "实现 /auth/login、/auth/callback、/auth/refresh 三个端点"},
            {"description": "集成 Google/GitHub 第三方登录"},
            {"description": "编写单元测试覆盖授权流程"},
            {"description": "添加 rate limiting 防暴力破解"},
            {"description": "编写集成测试 + 安全审计"},
        ],
    }, "timestamp": _ts()},
    {"step_number": 2, "action_type": "tool_call", "action_detail": {"tool_name": "search_code", "input": {"query": "OAuth"}}, "observation": "Found: auth module skeleton", "timestamp": _ts()},
    {"step_number": 3, "action_type": "memory_write", "action_detail": {"key": "oauth_flow", "value": "授权码模式: 1)请求code 2)换取token 3)刷新token", "source": "research"}, "timestamp": _ts()},
    {"step_number": 4, "action_type": "tool_call", "action_detail": {"tool_name": "create_file", "input": {"file_path": "models/oauth.py"}}, "observation": "Created", "timestamp": _ts()},
    {"step_number": 5, "action_type": "tool_call", "action_detail": {"tool_name": "create_file", "input": {"file_path": "api/auth.py"}}, "observation": "Created", "timestamp": _ts()},
    {"step_number": 6, "action_type": "think", "action_detail": {"thought": "OAuth 基础框架已完成，接下来实现 Google OAuth 集成"}, "timestamp": _ts()},
    {"step_number": 7, "action_type": "memory_read", "action_detail": {"key": "oauth_flow", "context": "implementing Google OAuth"}, "timestamp": _ts()},
    {"step_number": 8, "action_type": "tool_call", "action_detail": {"tool_name": "create_file", "input": {"file_path": "services/oauth_google.py"}}, "observation": "Created with Google OAuth2 client", "timestamp": _ts()},
    {"step_number": 9, "action_type": "tool_call", "action_detail": {"tool_name": "run_tests", "input": {"test_path": "tests/test_auth.py"}}, "observation": "22/22 passed", "timestamp": _ts()},
    {"step_number": 10, "action_type": "tool_call", "action_detail": {"tool_name": "run_tests", "input": {"test_path": "tests/test_integration.py"}}, "observation": "8/8 passed", "timestamp": _ts()},
]

TRAJ_GOOD = [
    {"step_number": 1, "action_type": "plan", "action_detail": {
        "goal": "添加邮件通知功能",
        "steps": [
            {"description": "集成 SMTP 邮件服务"},
            {"description": "创建邮件模板（注册确认、密码重置）"},
            {"description": "添加异步邮件队列"},
            {"description": "编写测试"},
        ],
    }, "timestamp": _ts()},
    {"step_number": 2, "action_type": "tool_call", "action_detail": {"tool_name": "search_code", "input": {"query": "email"}}, "observation": "No existing email code", "timestamp": _ts()},
    {"step_number": 3, "action_type": "tool_call", "action_detail": {"tool_name": "read_file", "input": {"file_path": "config/settings.py"}}, "observation": "SMTP_HOST not configured", "timestamp": _ts()},
    {"step_number": 4, "action_type": "tool_call", "action_detail": {"tool_name": "edit_file", "input": {"file_path": "config/settings.py", "changes": "add SMTP config"}}, "observation": "Updated", "timestamp": _ts()},
    {"step_number": 5, "action_type": "tool_call", "action_detail": {"tool_name": "create_file", "input": {"file_path": "services/email.py"}}, "observation": "Created", "timestamp": _ts()},
    {"step_number": 6, "action_type": "tool_call", "action_detail": {"tool_name": "create_file", "input": {"file_path": "templates/email/"}}, "observation": "Created templates", "timestamp": _ts()},
    {"step_number": 7, "action_type": "tool_call", "action_detail": {"tool_name": "run_tests", "input": {"test_path": "tests/test_email.py"}}, "observation": "3/5 passed, 2 failed: template rendering error", "timestamp": _ts()},
    {"step_number": 8, "action_type": "tool_call", "action_detail": {"tool_name": "edit_file", "input": {"file_path": "templates/email/confirm.html", "changes": "fix template"}}, "observation": "Fixed", "timestamp": _ts()},
    {"step_number": 9, "action_type": "tool_call", "action_detail": {"tool_name": "run_tests", "input": {"test_path": "tests/test_email.py"}}, "observation": "5/5 passed", "timestamp": _ts()},
]

TRAJ_MODERATE = [
    {"step_number": 1, "action_type": "plan", "action_detail": {
        "goal": "数据库迁移",
        "steps": [
            {"description": "备份数据库"},
            {"description": "执行迁移"},
            {"description": "验证"},
        ],
    }, "timestamp": _ts()},
    {"step_number": 2, "action_type": "tool_call", "action_detail": {"tool_name": "run_command", "input": {"cmd": "pg_dump"}}, "observation": "Backup complete", "timestamp": _ts()},
    {"step_number": 3, "action_type": "tool_call", "action_detail": {"tool_name": "run_command", "input": {"cmd": "alembic upgrade head"}}, "observation": "Migration applied", "timestamp": _ts()},
    {"step_number": 4, "action_type": "tool_call", "action_detail": {"tool_name": "run_command", "input": {"cmd": "python check_db.py"}}, "observation": "All tables present", "timestamp": _ts()},
]

TRAJ_POOR = [
    {"step_number": 1, "action_type": "tool_call", "action_detail": {"tool_name": "edit_file", "input": {"file_path": "prod_config.py", "changes": "DB_HOST=..."}}, "observation": "File changed", "timestamp": _ts()},
    {"step_number": 2, "action_type": "tool_call", "action_detail": {"tool_name": "run_command", "input": {"cmd": "restart service"}}, "observation": "Service down", "timestamp": _ts()},
    {"step_number": 3, "action_type": "failure", "action_detail": {"error_type": "RuntimeError", "error_message": "DB connection refused, wrong host"}, "timestamp": _ts()},
]

TRAJ_EMPTY: list = []

TRAJ_ADVERSARIAL = [
    {"step_number": i, "action_type": "tool_call",
     "action_detail": {"tool_name": f"tool_{i}", "input": {}},
     "observation": f"Output {i}", "timestamp": _ts()}
    for i in range(1, 16)
]

ALL_TRAJECTORIES = {
    "优秀": TRAJ_EXCELLENT,
    "良好": TRAJ_GOOD,
    "中等": TRAJ_MODERATE,
    "差": TRAJ_POOR,
    "空": TRAJ_EMPTY,
    "对抗": TRAJ_ADVERSARIAL,
}

GOAL_BY_LEVEL = {
    "优秀": "实现用户 OAuth2.0 登录",
    "良好": "添加邮件通知功能",
    "中等": "数据库迁移",
    "差": "修改生产配置",
    "空": "未知任务",
    "对抗": "未知任务",
}

QUALITY_ORDER = ["优秀", "良好", "中等", "差", "对抗", "空"]

REFERENCE_SCORES = {
    "优秀": 93.1,
    "良好": 92.0,
    "中等": 81.0,
    "差": 54.4,
    "对抗": 27.8,
    "空": 20.0,
}
