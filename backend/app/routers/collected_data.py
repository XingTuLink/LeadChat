"""Collected Data 接口：管理端查看各 Assistant 采集到的通用结构化数据

所有采集产物统一落本接口，可按 data_type 过滤查看：
lead（线索）/ ticket（工单）/ requirement（需求）/ appointment（预约）/ custom（自定义）。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.assistant import CollectedData
from app.routers.auth import verify_admin
from app.schemas.collected_data import (
    CollectedDataListResponse,
    CollectedDataOut,
    CollectedDataUpdate,
)

router = APIRouter(
    prefix="/api/collected-data",
    tags=["collected-data"],
    dependencies=[Depends(verify_admin)],
)


@router.get("", response_model=CollectedDataListResponse)
async def list_collected(
    page: int = 1,
    page_size: int = 20,
    data_type: str | None = None,
    assistant_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """采集数据列表（管理端）"""
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    stmt = select(CollectedData).order_by(CollectedData.id.desc())
    count_stmt = select(func.count()).select_from(CollectedData)
    if data_type:
        stmt = stmt.where(CollectedData.data_type == data_type)
        count_stmt = count_stmt.where(CollectedData.data_type == data_type)
    if assistant_id:
        stmt = stmt.where(CollectedData.assistant_id == assistant_id)
        count_stmt = count_stmt.where(CollectedData.assistant_id == assistant_id)
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (
        await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return {"items": [CollectedDataOut.model_validate(r) for r in rows], "total": total}


@router.put("/{item_id}")
async def update_collected(
    item_id: int,
    body: CollectedDataUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新采集数据处理状态（new / processed / closed）"""
    row = await db.get(CollectedData, item_id)
    if not row:
        raise HTTPException(status_code=404, detail="采集数据不存在")
    row.status = body.status
    await db.commit()
    return {"success": True}


@router.delete("/{item_id}")
async def delete_collected(item_id: int, db: AsyncSession = Depends(get_db)):
    """删除采集数据记录"""
    row = await db.get(CollectedData, item_id)
    if not row:
        raise HTTPException(status_code=404, detail="采集数据不存在")
    await db.delete(row)
    await db.commit()
    return {"success": True}
