"""LeadChat FastAPI 入口"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import PROJECT_ROOT, settings
from app.database import init_db
from app.routers import (
    assistants,
    auth,
    chat,
    collected_data,
    config as config_router,
    knowledge,
    models,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("leadchat")

def _read_version() -> str:
    """版本号单一来源为仓库根目录 VERSION 文件；读取失败时回退到内置值。"""
    try:
        return (Path(__file__).resolve().parents[2] / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0.6.0"


VERSION = _read_version()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("LeadChat v%s 启动完成", VERSION)
    yield


app = FastAPI(title="LeadChat", version=VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_cache_for_app_assets(request, call_next):
    """挂件与后台静态资源每次校验（ETag 命中返回 304，变更自动拉新），
    避免浏览器缓存旧版挂件/后台导致更新不生效。"""
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/widget/") or path.startswith("/admin/"):
        response.headers["Cache-Control"] = "no-cache"
    elif path == "/api/widget/config":
        # 挂件配置必须每次校验，避免浏览器缓存旧配置导致后台改主题/图标不生效
        response.headers["Cache-Control"] = "no-cache"
    return response

# API 路由
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(knowledge.router)
app.include_router(collected_data.router)
app.include_router(assistants.router)
app.include_router(config_router.router)
app.include_router(models.router)

# 静态资源
ADMIN_DIR = PROJECT_ROOT / "admin"
WIDGET_DIR = PROJECT_ROOT / "widget" / "dist"
UPLOADS_DIR = settings.uploads_dir
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

if ADMIN_DIR.exists():
    app.mount("/admin", StaticFiles(directory=str(ADMIN_DIR), html=True), name="admin")
if WIDGET_DIR.exists():
    app.mount("/widget", StaticFiles(directory=str(WIDGET_DIR)), name="widget")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.get("/", include_in_schema=False)
async def root():
    # 相对重定向：根路径部署 → /admin/；子路径部署（/leadchat/ 经代理剥前缀）→ /leadchat/admin/
    return RedirectResponse(url="admin/")


@app.get("/health")
async def health():
    return {"status": "ok", "version": VERSION}
