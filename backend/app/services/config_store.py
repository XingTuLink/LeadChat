"""系统配置读写：默认值 + 数据库覆盖

全部配置语义中立，不预设任何具体业务（销售/客服…）；
是否采集、采集什么字段由各 Assistant 的 collect_config / business_fields 决定。
"""
import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import SystemConfig

DEFAULT_CONFIG: dict[str, Any] = {
    "system_prompt": (
        "你是{company_name}的AI助手，嵌入在用户正在使用的 Web 系统中。\n\n"
        "你的职责：\n"
        "1. 专业、友好地回答用户关于{business_description}的问题\n"
        "2. 优先依据知识库资料作答；资料不足时诚实告知，不编造信息\n"
        "3. 在需要时协助用户查询信息、提交需求或完成相关操作\n\n"
        "回答规则：\n"
        "- 优先基于【参考资料】回答，不要编造信息\n"
        "- 如果参考资料中没有相关信息，诚实告知用户\n"
        "- 回答要简洁、有条理，每次不超过200字\n"
        "- 使用与用户相同的语言回答"
    ),
    "welcome_message": "你好，我是这个系统的 AI 助手，可以帮你查询信息、回答问题或协助完成相关操作。",
    "popup_message": "您好，请问有什么可以帮您吗？",
    "auto_popup_delay": 3,
    # 采集引导话术：仅在助手切换到 COLLECT 模式时生效
    "collect_guide_message": "方便的话，请把关键信息告诉我，我会帮你记录并跟进处理。",
    # v0.5.1：全局业务字段默认空数组——默认助手开箱即纯问答，不预设任何采集字段；
    # 需要采集的助手在自身配置中声明字段（工单/需求/销售线索…），或在此为默认助手显式开启。
    "business_fields": [],
    "widget_theme": "#4F46E5",
    "widget_position": "right",
    "widget_icon": "chat",
    "company_name": "LeadChat",
    "business_description": "我们的产品与服务",
}

ALLOWED_CONFIG_KEYS = set(DEFAULT_CONFIG.keys())

# 挂件公开配置白名单（无需管理密码即可读取）
WIDGET_CONFIG_KEYS = [
    "company_name", "welcome_message", "popup_message", "auto_popup_delay",
    "widget_theme", "widget_position",
    "widget_icon", "business_fields",
]


async def get_all_config(session: AsyncSession) -> dict[str, Any]:
    """返回合并后的全部配置（数据库值覆盖默认值）"""
    cfg = json.loads(json.dumps(DEFAULT_CONFIG, ensure_ascii=False))
    rows = (await session.execute(select(SystemConfig))).scalars().all()
    for row in rows:
        try:
            cfg[row.key] = json.loads(row.value)
        except (json.JSONDecodeError, TypeError):
            cfg[row.key] = row.value
    return cfg


async def set_config(session: AsyncSession, key: str, value: Any) -> None:
    """写入单个配置项"""
    if key not in ALLOWED_CONFIG_KEYS:
        raise ValueError(f"未知配置项: {key}")
    stored = json.dumps(value, ensure_ascii=False)
    row = await session.get(SystemConfig, key)
    if row:
        row.value = stored
        row.updated_at = datetime.now()
    else:
        session.add(SystemConfig(key=key, value=stored))
    await session.commit()
