"""API 路由聚合"""
from app.routers import assistants, auth, chat, collected_data, config, knowledge

__all__ = ["assistants", "auth", "chat", "collected_data", "config", "knowledge"]
