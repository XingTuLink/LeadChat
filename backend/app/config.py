"""LeadChat 全局配置：从环境变量 / .env 文件读取"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]   # backend/
PROJECT_ROOT = BACKEND_DIR.parent                   # 项目根目录


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(BACKEND_DIR / ".env"), str(PROJECT_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- 对话模型 ----
    # 对话模型全部在后台「模型管理」中配置，支持多模型在线切换，不再读取环境变量

    # ---- Embedding（可选）----
    embedding_model: str = ""           # 留空则用 ChromaDB 内置本地 embedding（零配置）
    embedding_api_key: str = ""         # 远程 embedding 密钥（本地模型留空）
    embedding_api_base: str = ""        # 远程 embedding 端点；留空用默认

    # ---- 管理后台 ----
    admin_password: str = "change_this_before_running"

    # ---- 数据库 ----
    database_url: str = (
        f"sqlite+aiosqlite:///{(BACKEND_DIR / 'data' / 'db' / 'leadchat.db').as_posix()}"
    )

    # ---- 网络 ----
    cors_origins: str = "*"             # 逗号分隔的来源列表，或 *

    # ---- 品牌页脚（Powered by 栈上月明 + ICP 备案）----
    # 设为 false 可关闭所有页面底部的品牌页脚，默认开启
    branding_footer_enabled: bool = True

    # ---- 对话 ----
    # 对话闲置超过该分钟数后自动标记为「已结束」；0 表示不自动结束
    conversation_timeout_minutes: int = 30

    # ---- RAG ----
    chunk_size: int = 500
    chunk_overlap: int = 50
    rag_top_k: int = 3
    history_rounds: int = 10

    # ---- 运行时数据目录 ----
    data_dir: str = (BACKEND_DIR / "data").as_posix()

    @property
    def db_dir(self) -> Path:
        return Path(self.data_dir) / "db"

    @property
    def chroma_dir(self) -> Path:
        return Path(self.data_dir) / "chroma"

    @property
    def uploads_dir(self) -> Path:
        return Path(self.data_dir) / "uploads"

    @property
    def cors_origin_list(self) -> list[str]:
        if not self.cors_origins or self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
