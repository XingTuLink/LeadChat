"""数据库连接与会话管理（SQLAlchemy 2.0 async，支持 SQLite / PostgreSQL）"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """FastAPI 依赖：提供一个异步会话"""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """启动时创建运行时目录和数据表，并幂等播种默认 Assistant"""
    for d in (settings.db_dir, settings.chroma_dir, settings.uploads_dir):
        d.mkdir(parents=True, exist_ok=True)
    from app import models  # noqa: F401  确保模型注册到 metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.services.assistant_store import ensure_default_assistant

    async with AsyncSessionLocal() as session:
        await ensure_default_assistant(session)
