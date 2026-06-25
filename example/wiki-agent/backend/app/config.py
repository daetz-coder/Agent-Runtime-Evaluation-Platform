from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ZhipuAI (GLM)
    ZHIPUAI_API_KEY: str = ""
    ZHIPUAI_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    ZHIPUAI_CHAT_MODEL: str = "glm-4"

    # Paths
    KNOWLEDGE_DIR: str = str(Path(__file__).parent.parent.parent / "knowledge")
    CHROMA_DIR: str = str(Path(__file__).parent.parent.parent / "chroma_db")
    EMBEDDING_MODEL_PATH: str = str(
        Path(__file__).parent.parent.parent / "models" / "bge-small-zh-v1.5"
    )
    RERANKER_MODEL_PATH: str = str(
        Path(__file__).parent.parent.parent / "models" / "bge-reranker-base"
    )
    DB_PATH: str = str(Path(__file__).parent.parent / "data" / "chat.db")
    BM25_INDEX_PATH: str = str(Path(__file__).parent.parent / "data" / "bm25_index.pkl")

    # Git
    GIT_ENABLED: bool = True

    # Note: Evaluation settings (EVAL_ENABLED, EVAL_API_BASE_URL, EVAL_BATCH_SIZE)
    # are now managed by the SDK via environment variables.

    class Config:
        env_file = str(Path(__file__).parent.parent / ".env")
        env_file_encoding = "utf-8"


settings: Settings = Settings()
