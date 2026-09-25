# LeadChat API 文档

Base URL：`http://your-server:11999`

交互式文档：启动后访问 `/docs`（Swagger UI）。

## 鉴权

管理端接口需在请求头携带令牌：

```
X-Admin-Token: <token>
```

令牌通过登录接口获取（由管理密码派生，无需存储会话）。

---

## 认证

### POST /api/auth/login

管理后台登录。

```json
// 请求
{ "password": "your-admin-password" }

// 响应 200
{ "token": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" }
```

失败返回 `401 {"detail": "密码错误"}`。

---

## 对话

### POST /api/chat/message

访客发送消息（挂件使用，公开）。

```json
// 请求
{
  "conversation_id": "a1b2c3…",
  "message": "我买的设备开不了机，订单号 O-009",
  "visitor_id": "v-8f2e…",
  "assistant_id": "support",                  // 可选：指定助手，缺省=默认助手
  "context": { "page": "ticket", "order_id": "O-009" }  // 可选：宿主业务上下文（扁平标量）
}

// 响应 200
{
  "conversation_id": "a1b2c3…",
  "reply": "已为您记录售后信息，工程师会尽快联系…",
  "sources": [
    { "content": "售后政策…", "doc_id": "3", "filename": "售后手册.md", "score": 0.87 }
  ],
  "assistant_id": "support",
  "data_captured": true,
  "data_type": "ticket"
}
```

说明：

- `assistant_id` 缺省、不存在或被停用时，服务端回退默认助手（`default`）。
- `context` 仅接受 ≤20 个键的扁平对象，键 ≤50 字符、值为字符串/数字/布尔（单值 ≤500 字符），嵌套对象/数组会被拒绝；服务端再按助手的上下文白名单过滤后注入 Prompt。
- `data_captured=true` 表示本轮把一条结构化业务数据写入了 `collected_data`；`data_type` 为其业务类型（lead/ticket/requirement/appointment/custom）。销售线索（lead）只是其中一种数据类型，不再有独立接口或表。

### POST /api/chat/message/stream（SSE 流式）

请求体与 `/api/chat/message` 完全相同（公开，无需鉴权），响应为 `text/event-stream`，按以下顺序推送 SSE 事件：

```
event: meta
data: {"conversation_id": "a1b2c3…", "assistant_id": "default"}

event: delta
data: {"content": "您好"}

event: delta
data: {"content": "，请问"}

…（逐 token 推送，次数不定）…

event: done
data: {"conversation_id":"a1b2c3…","assistant_id":"default","reply":"您好，请问…",
       "sources":[],"data_captured":false,"data_type":null}
```

说明：

- 建议用 `fetch` + `ReadableStream` 接收（EventSource 不支持 POST 请求体）；以空行分隔事件块，先解析 `event:` 名称再解析一行或多行 `data:`。
- `meta` 为首个事件，新会话可凭它立即拿到 `conversation_id`；`done` 为最后一个事件，载荷结构与非流式响应一致。
- LLM 流式调用失败时连接不中断：服务端改为推送降级文案的 `delta`，最后仍以 `done` 收尾；调用方也可在任何阶段自行回退到非流式 `/api/chat/message`。
- 客户端中途断开时，已生成的部分回复会尽力落库。
- Nginx 等反向代理需关闭响应缓冲（服务端已下发 `X-Accel-Buffering: no`）。

### POST /api/chat/conversation

创建新对话（公开）。

```json
// 请求（assistant_id / context 均为可选字段）
{
  "website_id": "main", "visitor_id": "v-8f2e…",
  "assistant_id": "support",
  "context": { "page": "ticket" }
}

// 响应 200
{ "conversation_id": "a1b2c3…", "assistant_id": "support" }
```

### GET /api/chat/conversations

对话列表（管理端）。查询参数：`page`（默认1）、`page_size`（默认20，最大100）、`status`（`active`/`closed`，可选）。

```json
// 响应 200
{
  "conversations": [
    {
      "id": "a1b2c3…", "website_id": null, "visitor_id": "v-8f2e…",
      "assistant_id": "support",
      "status": "active", "created_at": "2026-08-27T10:00:00", "updated_at": "2026-08-27T10:05:00"
    }
  ],
  "total": 1
}
```

### GET /api/chat/conversations/{id}/messages

对话消息列表（公开，供挂件恢复历史）。

```json
// 响应 200
{
  "messages": [
    { "id": 1, "role": "user", "content": "你好", "sources": null, "created_at": "…" },
    { "id": 2, "role": "assistant", "content": "您好！", "sources": [], "created_at": "…" }
  ]
}
```

### GET /api/chat/stats

仪表盘统计（管理端）。

```json
// 响应 200
{
  "today_conversations": 5, "today_collected": 2,
  "total_conversations": 120, "total_collected": 30,
  "total_messages": 890, "total_documents": 12
}
```

---

## 多助手管理（管理端）

助手 ID 为 1-32 字符的小写字母/数字/`-`/`_` slug，直接写进嵌入代码（如 `default`、`support`）。

### GET /api/assistants/templates

场景模板列表（含完整默认话术/字段/采集配置/上下文白名单，供新建表单预填）。

```json
// 响应 200
{
  "scenarios": [
    {
      "key": "support", "label": "售后客服助手",
      "description": "售后/工单场景：解答使用问题，收集订单与故障信息协助处理",
      "system_prompt": "你是{company_name}的AI售后客服助手…",
      "collect": { "mode": "collect", "data_type": "ticket", "intent_hint": "…" },
      "fields": [
        { "key": "order_id", "label": "订单号", "type": "string", "required": true },
        { "key": "issue_type", "label": "问题类型", "type": "enum",
          "options": ["使用咨询", "故障报修", "退换货", "账单问题"], "required": true }
      ],
      "context": { "allowed_fields": ["page", "user_id", "order_id"], "max_keys": 20 },
      "ui": {}
    }
  ]
}
```

内置 5 个场景，按通用 → 行业的顺序排列：`general`（通用问答，ASK 模式，默认）、`support`（售后工单）、`internal`（内部 Copilot，仅 ask）、`requirement`（需求收集）、`sales`（销售线索，仅为众多场景之一，置末）。

### GET /api/assistants

```json
// 响应 200
{
  "assistants": [
    {
      "id": "default", "name": "网站助手", "description": "…", "scenario": "general",
      "system_prompt": "",
      "model_config": {}, "knowledge_config": { "scope": "global" },
      "context_config": { "allowed_fields": [], "max_keys": 20 },
      "collect_config": { "mode": "ask", "data_type": "custom", "intent_hint": "" },
      "ui_config": {},
      "business_fields": [],
      "is_default": true, "status": "active",
      "created_at": "…", "updated_at": "…"
    }
  ],
  "total": 1
}
```

`system_prompt` / `ui_config` 留空表示继承「系统设置」全局配置；默认助手 `business_fields` 为空时运行时回退全局 `business_fields`（全局默认同样为空，即纯问答）。

### POST /api/assistants

创建助手。除 `id`/`name` 外均可省略——省略时按 `scenario` 模板填充。

```json
// 请求
{
  "id": "support",                 // 省略则自动生成 assistant-xxxxxxxx
  "name": "官网售后助手",
  "description": "售后页挂载",
  "scenario": "support",
  "system_prompt": "",             // 留空=使用场景模板话术；默认助手语义下表示继承全局
  "collect_config": { "mode": "collect", "data_type": "ticket" },
  "context_config": { "allowed_fields": ["page", "order_id"], "max_keys": 20 },
  "ui_config": { "title": "售后小助手", "theme": "#10b981" },
  "business_fields": [
    { "key": "order_id", "label": "订单号", "type": "string", "required": true },
    { "key": "issue_type", "label": "问题类型", "type": "enum",
      "options": ["报修", "退换货"], "required": true },
    { "key": "phone", "label": "联系电话", "type": "phone", "required": false }
  ]
}
```

字段类型 `type`：`string` / `text` / `number` / `enum` / `phone` / `email`；`enum` 需给 `options`。ID 非法/重复返回 `400`。

### GET /api/assistants/{id} · PUT /api/assistants/{id} · DELETE /api/assistants/{id}

- PUT 为字段级更新，仅传需要修改的键；`status` 取 `active` / `disabled`（停用后嵌入流量回退默认助手）。
- 默认助手（`id=default`）不可删除，删除返回 `400`；不存在返回 `404`。
- 删除助手不影响历史会话与已采集数据（`collected_data.assistant_id` 仅作记录）。

### PUT /api/assistants/{id}/default

将指定助手设为默认（同时自动启用），响应为更新后的助手对象。

---

## 采集数据（管理端）

对话中采集到的通用结构化数据，统一落 `collected_data` 一张表。销售线索只是 `data_type=lead` 的筛选视图（`/api/collected-data?data_type=lead`）。

### GET /api/collected-data

查询参数：`page`（默认1）、`page_size`（默认20，最大100）、`data_type`（可选）、`assistant_id`（可选）。

```json
// 响应 200
{
  "items": [
    {
      "id": 12, "conversation_id": "a1b2c3…", "assistant_id": "support",
      "data_type": "ticket",
      "payload": { "order_id": "O-009", "issue_type": "故障报修", "phone": "138…" },
      "status": "new", "created_at": "2026-09-17T10:00:00"
    }
  ],
  "total": 1
}
```

### PUT /api/collected-data/{id}

```json
// 请求：status ∈ new / processed / closed
{ "status": "processed" }
```

### DELETE /api/collected-data/{id}

删除单条采集数据记录（关联对话仅解绑、不级联删除）。

---

## 知识库（管理端）

### POST /api/knowledge/upload

上传文档。`multipart/form-data`，字段名 `file`，支持 PDF / DOCX / TXT / MD，≤20MB。

```json
// 响应 200
{ "id": 3, "filename": "产品介绍.md", "file_type": "md", "chunk_count": 18, "created_at": "…" }
```

错误返回 `400`（类型不支持 / 解析失败 / 内容为空）或 `500`（向量索引失败）。

### GET /api/knowledge/documents

```json
// 响应 200
{ "documents": [ { "id": 3, "filename": "产品介绍.md", "file_type": "md", "chunk_count": 18, "created_at": "…" } ] }
```

### DELETE /api/knowledge/documents/{id}

删除文档及其向量索引。

```json
// 响应 200
{ "success": true }
```

### GET /api/knowledge/search

语义检索调试。查询参数：`query`（必填）、`top_k`（默认3，1-20）。

```json
// 响应 200
{ "results": [ { "content": "…", "doc_id": "3", "filename": "产品介绍.md", "score": 0.87 } ] }
```

---

## 系统配置

### GET /api/config

读取全部配置（管理端）。

```json
// 响应 200
{
  "config": {
    "system_prompt": "你是{company_name}的AI助手，嵌入在用户正在使用的 Web 系统中…",
    "welcome_message": "你好，我是这个系统的 AI 助手…",
    "collect_guide_message": "方便的话，请把关键信息告诉我…",
    "business_fields": [],
    "widget_theme": "#4F46E5",
    "widget_position": "right",
    "company_name": "LeadChat",
    "business_description": "我们的产品与服务"
  }
}
```

### PUT /api/config

更新单个配置项（管理端）。

```json
// 请求
{ "key": "welcome_message", "value": "Hi，需要帮忙吗？" }

// 响应 200
{ "success": true }
```

### GET /api/widget/config

挂件公开配置（无需鉴权）。查询参数 `assistant`（可选）：指定助手 ID；缺省、不存在或被停用时返回默认助手的配置。

`GET /api/widget/config?assistant=support`

```json
// 响应 200
{
  "assistant_id": "support",
  "collect_mode": "collect",
  "company_name": "售后小助手",
  "welcome_message": "您好！…",
  "widget_theme": "#10B981",
  "widget_position": "right",
  "widget_icon": "chat",
  "auto_popup_delay": 0,
  "business_fields": [{ "key": "order_id", "label": "订单号", "type": "string", "required": true }]
}
```

说明：默认助手的外观来自系统全局配置；其他助手若在 `ui_config` 中配置了 title/theme/position/icon/welcome/popup，则逐项覆盖全局值，未配置的项继续继承。默认助手的 `business_fields` 为空数组（纯问答），`collect_mode` 为 `ask`。

---

## 其他

### GET /health

```json
{ "status": "ok", "version": "0.6.0" }
```

### 静态资源

| 路径 | 说明 |
|------|------|
| `/admin/` | 管理后台 |
| `/widget/leadchat.min.js` | 挂件脚本 |
| `/uploads/…` | 上传的原始文档 |
