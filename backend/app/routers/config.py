"""系统配置接口：管理端读写 + 挂件公开配置"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.routers.auth import verify_admin
from app.schemas.config import ConfigResponse, ConfigUpdateRequest, WidgetConfigResponse
from app.services import assistant_store
from app.services.config_store import (
    ALLOWED_CONFIG_KEYS,
    WIDGET_CONFIG_KEYS,
    get_all_config,
    set_config,
)

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config", response_model=ConfigResponse)
async def get_config(_: bool = Depends(verify_admin), db: AsyncSession = Depends(get_db)):
    """读取全部系统配置（管理端）"""
    return {"config": await get_all_config(db)}


@router.put("/config")
async def update_config(
    body: ConfigUpdateRequest, _: bool = Depends(verify_admin), db: AsyncSession = Depends(get_db)
):
    """更新单个配置项（管理端）"""
    if body.key not in ALLOWED_CONFIG_KEYS:
        raise HTTPException(status_code=400, detail=f"未知配置项：{body.key}")
    try:
        await set_config(db, body.key, body.value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True}


@router.get("/widget/config", response_model=WidgetConfigResponse)
async def get_widget_config(
    assistant: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """挂件公开配置（无需鉴权）

    可通过 ?assistant=<id> 指定助手：其 UI 配置（主题/图标/欢迎语…）覆盖全局配置，
    未自定义项继续回退「系统设置」；不传时返回默认助手配置，行为同旧版。
    """
    global_cfg = await get_all_config(db)
    assistant_row = await assistant_store.resolve_assistant(db, assistant)
    cfg = await assistant_store.runtime_config(db, assistant_row, global_cfg)

    payload = {k: cfg.get(k) for k in WIDGET_CONFIG_KEYS}
    # Assistant 自定义外观逐项覆盖
    ui_cfg = assistant_store.get_ui_config(assistant_row)
    for ui_key, cfg_key in (
        ("theme", "widget_theme"),
        ("icon", "widget_icon"),
        ("position", "widget_position"),
        ("title", "company_name"),
        ("welcome_message", "welcome_message"),
        ("popup_message", "popup_message"),
        ("auto_popup_delay", "auto_popup_delay"),
    ):
        if ui_key in ui_cfg and ui_cfg[ui_key] not in (None, ""):
            payload[cfg_key] = ui_cfg[ui_key]

    resp = WidgetConfigResponse(**payload)
    resp.footer_enabled = settings.branding_footer_enabled
    resp.assistant_id = assistant_row.id
    resp.collect_mode = cfg.get("collect_mode", "ask")
    return resp
