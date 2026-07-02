from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WIKI_AGENT_ROOT = PROJECT_ROOT / "example" / "wiki-agent"
WIKI_DATA_DIR = PROJECT_ROOT / "data" / "wiki_agent"


class WikiAgentSettings(BaseSettings):
    # LLM (DeepSeek, OpenAI-compatible API)
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # LLM (ZhipuAI / GLM, OpenAI-compatible API) — optional override
    ZHIPUAI_API_KEY: str = ""
    ZHIPUAI_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    ZHIPUAI_CHAT_MODEL: str = "glm-4-flash"

    # Paths — runtime data under data/wiki_agent/, seed content under app/wiki_agent/seed/
    KNOWLEDGE_DIR: str = str(WIKI_DATA_DIR / "knowledge")
    MILVUS_URI: str = str(WIKI_DATA_DIR / "milvus.db")
    MILVUS_COLLECTION: str = "wiki_knowledge"
    EMBEDDING_DIM: int = 512
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
    EMBEDDING_MODEL_PATH: str = str(WIKI_AGENT_ROOT / "models" / "bge-small-zh-v1.5")
    DB_PATH: str = str(WIKI_DATA_DIR / "chat.db")
    BM25_INDEX_PATH: str = str(WIKI_DATA_DIR / "bm25_index.pkl")

    # Query Rewrite (pre-retrieval pipeline)
    QUERY_REWRITE_ENABLED: bool = True
    QUERY_REWRITE_SIMILARITY_THRESHOLD: float = 0.7
    QUERY_REWRITE_MAX_QUERIES: int = 5

    # Rerank (cross-encoder after RRF)
    RERANK_ENABLED: bool = True
    RERANK_MODEL: str = "BAAI/bge-reranker-base"
    RERANK_MODEL_PATH: str = str(WIKI_AGENT_ROOT / "models" / "bge-reranker-base")
    RERANK_CANDIDATE_MULTIPLIER: int = 3
    RERANK_MAX_LENGTH: int = 512

    # Cache
    CACHE_SESSION_TTL: int = 3600

    # Git
    GIT_ENABLED: bool = True

    # Runtime evaluation platform (same process after integration)
    EVAL_ENABLED: bool = True
    EVAL_API_BASE_URL: str = "http://127.0.0.1:8000"
    EVAL_INPROCESS: bool = True
    EVAL_AUTO_RUN: bool = False
    EVAL_BATCH_SIZE: int = 8

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = WikiAgentSettings()
