from pathlib import Path

from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WIKI_AGENT_ROOT = PROJECT_ROOT / "example" / "wiki-agent"
WIKI_DATA_DIR = PROJECT_ROOT / "data" / "wiki_agent"


class WikiAgentSettings(BaseSettings):
    # LLM (DeepSeek, OpenAI-compatible API)
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # Paths — runtime data under data/wiki_agent/, seed content under app/wiki_agent/seed/
    KNOWLEDGE_DIR: str = str(WIKI_DATA_DIR / "knowledge")
    MILVUS_URI: str = str(WIKI_DATA_DIR / "milvus.db")
    MILVUS_COLLECTION: str = "wiki_knowledge"
    EMBEDDING_DIM: int = 512
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
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
