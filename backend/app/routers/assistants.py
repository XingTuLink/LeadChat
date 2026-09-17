"""Assistant 管理接口（管理端）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.auth import verify_admin
from app.schemas.assistant import (
    AssistantCreate,
    AssistantListResponse,
    AssistantOut,
    AssistantUpdate,
    ScenarioListResponse,
)
from app.services import assistant_store

router = APIRouter(
    prefix="/api/assistants",
    tags=["assistants"],
    dependencies=[Depends(verify_admin)],
)


@router.get("/templates", response_model=ScenarioListResponse)
async def list_templates():
    """场景模板：Default Prompt + Default Fields + Default Context + Default UI"""
    return {"scenarios": assistant_store.template_meta()}


@router.get("", response_model=AssistantListResponse)
async def list_assistants(db: AsyncSession = Depends(get_db)):
    rows = await assistant_store.list_assistants(db)
    items = [await assistant_store.assistant_to_dict(db, r) for r in rows]
    return {"assistants": items, "total": len(items)}


@router.post("", response_model=AssistantOut, status_code=201)
async def create_assistant(body: AssistantCreate, db: AsyncSession = Depends(get_db)):
    data = body.model_dump(by_alias=True)
    try:
        row = await assistant_store.create_assistant(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await assistant_store.assistant_to_dict(db, row)


@router.get("/{assistant_id}", response_model=AssistantOut)
async def get_assistant(assistant_id: str, db: AsyncSession = Depends(get_db)):
    return await _get_or_404(db, assistant_id)


@router.put("/{assistant_id}", response_model=AssistantOut)
async def update_assistant(
    assistant_id: str, body: AssistantUpdate, db: AsyncSession = Depends(get_db)
):
    data = body.model_dump(exclude_unset=True, by_alias=True)
    try:
        row = await assistant_store.update_assistant(db, assistant_id, data)
    except KeyError:
        raise HTTPException(status_code=404, detail="助手不存在")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await assistant_store.assistant_to_dict(db, row)


@router.put("/{assistant_id}/default", response_model=AssistantOut)
async def set_default(assistant_id: str, db: AsyncSession = Depends(get_db)):
    try:
        row = await assistant_store.set_default(db, assistant_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="助手不存在")
    return await assistant_store.assistant_to_dict(db, row)


@router.delete("/{assistant_id}")
async def delete_assistant(assistant_id: str, db: AsyncSession = Depends(get_db)):
    try:
        await assistant_store.delete_assistant(db, assistant_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="助手不存在")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True}


async def _get_or_404(db: AsyncSession, assistant_id: str):
    from app.models.assistant import Assistant

    row = await db.get(Assistant, assistant_id)
    if not row:
        raise HTTPException(status_code=404, detail="助手不存在")
    return await assistant_store.assistant_to_dict(db, row)
