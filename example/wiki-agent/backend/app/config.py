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
    DB_PATH: str = str(Path(__file__).parent.parent / "data" / "chat.db")
    BM25_INDEX_PATH: str = str(Path(__file__).parent.parent / "data" / "bm25_index.pkl")

    # Git
    GIT_ENABLED: bool = True

    # Runtime evaluation platform
    EVAL_ENABLED: bool = True
    EVAL_API_BASE_URL: str = "http://127.0.0.1:8000"
    EVAL_AUTO_RUN: bool = False
    EVAL_BATCH_SIZE: int = 8

    class Config:
        env_file = str(Path(__file__).parent.parent / ".env")
        env_file_encoding = "utf-8"


settings: Settings = Settings()
