"""管理后台认证：密码登录 + 静态 Token 校验"""
import hashlib

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


def admin_token() -> str:
    """由管理密码派生的静态访问令牌"""
    return hashlib.sha256(f"leadchat-admin:{settings.admin_password}".encode()).hexdigest()


async def verify_admin(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
    """FastAPI 依赖：校验管理端请求的令牌"""
    if not x_admin_token or x_admin_token != admin_token():
        raise HTTPException(status_code=401, detail="未授权：请先登录管理后台")
    return True


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    if not settings.admin_password or body.password != settings.admin_password:
        raise HTTPException(status_code=401, detail="密码错误")
    return {"token": admin_token()}
