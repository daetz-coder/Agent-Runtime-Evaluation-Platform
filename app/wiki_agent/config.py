from pathlib import Path

from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WIKI_AGENT_ROOT = PROJECT_ROOT / "example" / "wiki-agent"
WIKI_DATA_DIR = PROJECT_ROOT / "data" / "wiki_agent"


class WikiAgentSettings(BaseSettings):
    # ZhipuAI (GLM)
    ZHIPUAI_API_KEY: str = ""
    ZHIPUAI_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    ZHIPUAI_CHAT_MODEL: str = "glm-4"

    # Paths
    KNOWLEDGE_DIR: str = str(WIKI_AGENT_ROOT / "knowledge")
    CHROMA_DIR: str = str(WIKI_AGENT_ROOT / "chroma_db")
    EMBEDDING_MODEL_PATH: str = str(WIKI_AGENT_ROOT / "models" / "bge-small-zh-v1.5")
    DB_PATH: str = str(WIKI_DATA_DIR / "chat.db")
    BM25_INDEX_PATH: str = str(WIKI_DATA_DIR / "bm25_index.pkl")

    # Git
    GIT_ENABLED: bool = True

    # Runtime evaluation platform (same process after integration)
    EVAL_ENABLED: bool = True
    EVAL_API_BASE_URL: str = "http://127.0.0.1:8000"
    EVAL_AUTO_RUN: bool = False
    EVAL_BATCH_SIZE: int = 8

    class Config:
        env_file = str(PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = WikiAgentSettings()
