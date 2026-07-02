"""数据库初始化和连接管理"""

from pathlib import Path

import aiosqlite

from app.wiki_agent.config import settings

DB_PATH = Path(settings.DB_PATH)

# 确保数据目录存在
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# SQL 建表语句
CREATE_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '新对话',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    wiki_results TEXT,
    extraction TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
)
"""

CREATE_MESSAGES_INDEX = """
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)
"""

CREATE_USER_MEMORY_TABLE = """
CREATE TABLE IF NOT EXISTS user_memory (
    id TEXT PRIMARY KEY DEFAULT 'default',
    facts TEXT DEFAULT '[]',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


async def init_db():
    """初始化数据库，创建表"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(CREATE_SESSIONS_TABLE)
        await db.execute(CREATE_MESSAGES_TABLE)
        await db.execute(CREATE_MESSAGES_INDEX)
        await db.execute(CREATE_USER_MEMORY_TABLE)
        # 迁移：sessions 表增加 key_facts 列
        try:
            await db.execute("ALTER TABLE sessions ADD COLUMN key_facts TEXT DEFAULT '[]'")
        except Exception:
            pass  # 列已存在
        # 迁移：sessions 表增加 active_eval_task_id 列
        try:
            await db.execute("ALTER TABLE sessions ADD COLUMN active_eval_task_id TEXT")
        except Exception:
            pass  # 列已存在
        await db.commit()
    print(f"[数据库] 初始化完成: {DB_PATH}")


async def get_db():
    """获取数据库连接"""
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    return db
