"""SSE 流式对话接口测试（LLM/RAG 全部打桩，不发网络请求）

覆盖：
- POST /api/chat/message/stream 返回 text/event-stream，事件顺序 meta → delta* → done
- delta 拼接结果与 done.reply 一致，回复正常落库（历史接口可读回）
- 默认助手纯问答：data_captured=False、data_type=None
- LLM 流式调用失败时降级为提示文案，仍以 done 正常收尾（不中断流）
- 非流式 /api/chat/message 行为不受影响
"""
import json

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

STREAM_CHUNKS = ["你好", "，", "我是", "AI", "助手"]


def parse_sse(raw: str) -> list[tuple[str, dict]]:
    events = []
    for block in raw.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event = "message"
        data_lines = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        if data_lines:
            events.append((event, json.loads("\n".join(data_lines))))
    return events


@pytest.fixture(autouse=True)
def _patch_rag(monkeypatch):
    async def fake_rag_search(*args, **kwargs):
        return []

    monkeypatch.setattr("app.services.rag.search", fake_rag_search)


async def test_stream_chat_sse_events_and_persistence(client, monkeypatch):
    async def fake_stream(messages, **kwargs):
        for piece in STREAM_CHUNKS:
            yield piece

    monkeypatch.setattr("app.services.llm.chat_completion_stream", fake_stream)

    async with client.stream(
        "POST", "/api/chat/message/stream", json={"message": "你好"}
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        raw = await resp.aread()

    events = parse_sse(raw.decode("utf-8"))
    names = [name for name, _ in events]
    assert names[0] == "meta"
    assert names[-1] == "done"
    assert names.count("delta") == len(STREAM_CHUNKS)

    meta = events[0][1]
    assert meta["conversation_id"]
    assert meta["assistant_id"] == "default"

    deltas = [data["content"] for name, data in events if name == "delta"]
    done = events[-1][1]
    assert "".join(deltas) == "".join(STREAM_CHUNKS)
    assert done["reply"] == "".join(STREAM_CHUNKS)
    assert done["conversation_id"] == meta["conversation_id"]
    assert done["assistant_id"] == "default"
    assert done["sources"] == []
    # 默认助手：纯问答，不触发采集
    assert done["data_captured"] is False
    assert done["data_type"] is None

    # 流式回复已落库（用户消息 + AI 消息各一条）
    hist = await client.get(
        "/api/chat/conversations/%s/messages" % meta["conversation_id"]
    )
    msgs = hist.json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["content"] == "".join(STREAM_CHUNKS)


async def test_stream_chat_llm_failure_degrades_gracefully(client, monkeypatch):
    async def broken_stream(messages, **kwargs):
        raise RuntimeError("llm down")
        yield  # pragma: no cover  # 声明为 async generator

    monkeypatch.setattr("app.services.llm.chat_completion_stream", broken_stream)

    async with client.stream(
        "POST", "/api/chat/message/stream", json={"message": "在吗"}
    ) as resp:
        assert resp.status_code == 200
        raw = (await resp.aread()).decode("utf-8")

    events = parse_sse(raw)
    assert events[0][0] == "meta"
    assert events[-1][0] == "done"
    done = events[-1][1]
    assert "暂时不可用" in done["reply"]
    # 降级文案同样通过 delta 下发，前端可正常渲染
    assert any(name == "delta" for name, _ in events)


async def test_non_stream_endpoint_unchanged(client, monkeypatch):
    async def fake_chat(messages, **kwargs):
        return "非流式回复"

    monkeypatch.setattr("app.services.llm.chat_completion", fake_chat)

    resp = await client.post("/api/chat/message", json={"message": "测试"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "非流式回复"
    assert data["conversation_id"]
    assert data["data_captured"] is False
