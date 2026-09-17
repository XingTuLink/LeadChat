"""pytest 公共夹具

关键点：
- 必须在导入任何 app.* 模块之前设置 DATA_DIR / DATABASE_URL / ADMIN_PASSWORD，
  因为 settings 与 async engine 在模块导入时即创建；
- ASGITransport 不会触发 FastAPI lifespan，需要手动 await init_db()；
- 全部测试共享一个 session 级事件循环，避免 aiosqlite 连接跨事件循环复用报错。
"""
import os
import tempfile
from pathlib import Path

_TMP_DATA = Path(tempfile.mkdtemp(prefix="leadchat-pytest-"))
os.environ["DATA_DIR"] = _TMP_DATA.as_posix()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(_TMP_DATA / 'test.db').as_posix()}"
os.environ["ADMIN_PASSWORD"] = "test-admin-password"
os.environ["CHROMA_TELEMETRY_IMPL"] = "off"

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.database import AsyncSessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402


# 全套测试共用 session 级事件循环，避免 aiosqlite 连接跨事件循环复用报错
pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _init_database():
    await init_db()
    yield


@pytest_asyncio.fixture(loop_scope="session")
async def db(_init_database):
    """直连数据库的会话（断言服务层/落库结果用）"""
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(loop_scope="session")
async def client(_init_database):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture(loop_scope="session")
async def admin_headers(client):
    resp = await client.post("/api/auth/login", json={"password": "test-admin-password"})
    assert resp.status_code == 200, resp.text
    return {"X-Admin-Token": resp.json()["token"]}
