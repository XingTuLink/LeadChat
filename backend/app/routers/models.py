"""模型管理接口（管理端）：多模型配置、在线激活切换、连通性测试"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.auth import verify_admin
from app.schemas.llm_model import (
    ModelCreate,
    ModelListResponse,
    ModelOut,
    ModelUpdate,
    ProviderListResponse,
)
from app.services import llm, model_store

router = APIRouter(
    prefix="/api/models",
    tags=["models"],
    dependencies=[Depends(verify_admin)],
)


@router.get("/providers", response_model=ProviderListResponse)
async def list_providers():
    """支持的厂商与默认端点（后台表单单一数据源）"""
    return {"providers": model_store.provider_meta()}


@router.get("", response_model=ModelListResponse)
async def list_models(db: AsyncSession = Depends(get_db)):
    rows = await model_store.list_models(db)
    items = [model_store.to_dict(r) for r in rows]
    return {"models": items, "total": len(items)}


@router.post("", response_model=ModelOut, status_code=201)
async def create_model(body: ModelCreate, db: AsyncSession = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    try:
        row = await model_store.create_model(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return model_store.to_dict(row)


@router.put("/{model_id}", response_model=ModelOut)
async def update_model(
    model_id: str, body: ModelUpdate, db: AsyncSession = Depends(get_db)
):
    data = body.model_dump(exclude_unset=True)
    try:
        row = await model_store.update_model(db, model_id, data)
    except KeyError:
        raise HTTPException(status_code=404, detail="模型不存在")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return model_store.to_dict(row)


@router.post("/{model_id}/activate", response_model=ModelOut)
async def activate_model(model_id: str, db: AsyncSession = Depends(get_db)):
    try:
        row = await model_store.activate(db, model_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="模型不存在")
    return model_store.to_dict(row)


@router.post("/{model_id}/test")
async def test_model(model_id: str, db: AsyncSession = Depends(get_db)):
    """连通性测试：用该模型发起一次最小对话，不改变激活状态"""
    from app.models.llm_model import LLMModel

    model_row = await db.get(LLMModel, model_id)
    if not model_row:
        raise HTTPException(status_code=404, detail="模型不存在")

    cfg = model_store.to_dict(model_row, masked=False)
    try:
        reply = await llm.chat_completion(
            [{"role": "user", "content": "ping"}],
            temperature=0,
            model_cfg=cfg,
        )
    except Exception as e:  # noqa: BLE001  测试接口需要把失败原因回传
        raise HTTPException(status_code=400, detail=f"连接失败：{e}")
    return {"success": True, "reply": (reply or "")[:200]}


@router.delete("/{model_id}")
async def delete_model(model_id: str, db: AsyncSession = Depends(get_db)):
    try:
        await model_store.delete_model(db, model_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="模型不存在")
    return {"success": True}
