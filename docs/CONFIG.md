# LeadChat 配置说明

## 一、环境变量（.env）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_PROVIDER` | `openai` | 模型提供商：`openai` / `deepseek` / `qwen` / `glm` / `ollama` / `custom` |
| `LLM_API_KEY` | 空 | API 密钥 |
| `LLM_API_BASE` | 空 | 自定义 API 地址；留空用默认；`custom` 时必填；Docker 内用 Ollama 填 `http://host.docker.internal:11434` |
| `LLM_MODEL` | `gpt-4o-mini` | 模型名称 |
| `EMBEDDING_MODEL` | 空 | Embedding 模型；留空用 ChromaDB 内置本地模型 |
| `ADMIN_PASSWORD` | `change_this_before_running` | 管理后台密码，**首次启动前务必修改** |
| `DATABASE_URL` | SQLite | 数据库连接串；PostgreSQL 示例 `postgresql+asyncpg://user:pass@host:5432/leadchat` |
| `CORS_ORIGINS` | `*` | 允许跨域来源，逗号分隔 |
| `BRANDING_FOOTER_ENABLED` | `true` | 页面底部品牌页脚开关，设为 `false` 关闭 |
| `CONVERSATION_TIMEOUT_MINUTES` | `30` | 对话闲置自动结束阈值（分钟），`0` 关闭 |
| `CHUNK_SIZE` | `500` | 文档切片最大字符数 |
| `CHUNK_OVERLAP` | `50` | 相邻切片重叠字符数 |
| `RAG_TOP_K` | `3` | 每次检索返回的相关片段数 |
| `HISTORY_ROUNDS` | `10` | 携带的历史对话轮数 |

### 各提供商默认端点

| 提供商 | 默认 API Base | 推荐 Embedding 模型 |
|--------|--------------|--------------------|
| openai | OpenAI 官方 | `text-embedding-3-small` |
| deepseek | DeepSeek 官方 | 不提供，建议配 `qwen` 或 `glm` 的 Embedding |
| qwen | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `text-embedding-v3` |
| glm | `https://open.bigmodel.cn/api/paas/v4` | `embedding-3` |
| ollama | `http://localhost:11434` | `nomic-embed-text` |
| custom | 必填 `LLM_API_BASE` | 按提供商要求 |

> 注：DeepSeek 目前没有 Embedding API。若用 DeepSeek 对话，可另配 Embedding（`EMBEDDING_MODEL` 走同一 `LLM_API_KEY`/`LLM_API_BASE`），或留空使用本地内置模型。
>
> ⚠️ **中文场景重要提示**：内置本地 embedding 模型（all-MiniLM-L6-v2）为英文模型，中文语义检索效果较差。**中文知识库强烈建议配置中文效果好的 Embedding 模型**，例如通义 `text-embedding-v3` 或智谱 `embedding-3`，或 Ollama 本地模型 `bge-m3`（`ollama/bge-m3`）。

## 二、挂件参数（script 标签 data-* 属性）

```html
<script src="https://chat.example.com/widget/leadchat.min.js"
        data-api="https://chat.example.com"
        data-theme="#4F46E5"
        data-position="right"
        data-welcome="您好！有什么可以帮您？"
        data-title="XX科技"></script>
```

| 属性 | 必填 | 说明 |
|------|------|------|
| `data-api` | 否 | 后端地址，结尾不带 `/`；同源部署（含 `/leadchat/` 等反代子路径）可省略，挂件自动从脚本 URL 推导 |
| `data-assistant` | 否 | 助手 ID（v0.4），缺省使用默认助手 |
| `data-theme` | 否 | 主题色，覆盖后台配置 |
| `data-position` | 否 | `right` / `left`，覆盖后台配置 |
| `data-icon` | 否 | 按钮图标：`chat` / `message` / `headset` / `sparkle` / `smile` |
| `data-welcome` | 否 | 欢迎语，覆盖后台配置 |
| `data-title` | 否 | 窗口标题（公司名），覆盖后台配置 |

优先级：`LeadChat.init` 参数 > `data-*` 属性（二者均为页面端覆盖，仅传入项生效）> 服务端助手 `ui_config` > 后台「系统设置」> 内置默认值。

需要向对话传入宿主业务上下文（页面、订单号、登录用户等）时，使用 v0.4 的 Embed API：

```html
<script>
  window.LeadChat = window.LeadChat || [];
  window.LeadChat.push(["init", {
    assistant: "support",
    context: { page: location.pathname, order_id: "O-009" }
  }]);
</script>
<script src="https://chat.example.com/widget/leadchat.min.js?v=0.5.2"></script>
```

运行期可随时调用 `LeadChat.setContext({...})` 更新（如 SPA 路由切换），详见 README「嵌入任意 Web 系统」。

挂件其他行为：

- 对话记录保存在浏览器 `localStorage`，刷新页面不丢失
- 欢迎气泡每会话弹一次，关闭后本会话不再出现
- 移动端（<480px）聊天窗口自动全屏

## 三、后台配置项（系统设置页）

> 本页配置即**默认助手（`default`，通用问答场景）**的全局回退：默认助手未单独配置的话术、外观、业务字段都继承这里。v0.5 起默认助手为 ASK 模式的通用助手，不预设任何销售语义；v0.5.1 起全局业务字段默认为空数组——新部署开箱即纯问答，不索取姓名/电话/邮箱等任何信息。

| 配置项 | 说明 |
|--------|------|
| 公司名称 | 填入系统提示词的 `{company_name}` 变量，同时作为挂件默认标题 |
| 业务描述 | 填入 `{business_description}` 变量，告诉 AI 你的业务与系统是做什么的 |
| 系统提示词 | AI 的人设与回答规则，支持变量占位 |
| 采集引导话术 | collect 模式下引导用户提供业务信息时附加的通用话术 |
| 业务字段 | 默认助手的通用采集字段（key / 标签 / 类型 / 是否必填）；**默认为空**（纯问答），仅在默认助手切到主动采集模式、或其他助手未配字段时才作为回退生效 |
| 欢迎语 | 挂件欢迎气泡与首条消息 |
| 主题色 | 挂件主色调 |
| 位置 | 挂件在页面右下角或左下角 |

### 系统提示词写作建议

```
你是{company_name}的AI助手，嵌入在用户正在使用的 Web 系统中。

你的职责：
1. 准确、专业地回答用户关于{business_description}的问题
2. 需要用户提供信息才能继续处理时，一次只自然地追问一项关键信息
3. 始终保持友好、有帮助的态度

回答规则：
- 优先基于【参考资料】回答，不要编造信息
- 如果参考资料中没有相关信息，诚实告知用户
- 回答要简洁、有条理，每次不超过200字
```

> RAG 检索结果会自动以【参考资料】段落注入，无需在提示词中重复说明。

## 四、多助手与业务数据采集（v0.4）

一个 LeadChat 实例可托管多个助手（可配置 AI Assistant），分别嵌入不同页面/系统。在后台「多助手」页管理，接口详见 [API.md](API.md)。

### 1. 场景模板

新建助手时按场景模板预填全部配置，可再手工调整：

| 场景 | 用途 | 默认采集 |
|------|------|----------|
| `general` 通用问答 | 兜底场景，默认助手 | 仅答疑（ask / custom），不配字段 |
| `support` 售后客服 | 售后/工单页面 | 收集订单号、问题类型等工单信息（ticket） |
| `internal` 内部 Copilot | 内部系统嵌入 | 仅答疑，不主动收集（ask 模式） |
| `requirement` 需求收集 | 需求/报名类页面 | 必填需求描述，姓名/电话为可选（requirement） |
| `sales` 销售线索 | 营销/售前页面（仅为场景之一，置末；默认不启用） | 收集姓名、电话等销售线索（lead），统一落 collected_data |

### 2. 采集模式与数据类型

- `collect`（主动收集）：助手在对话中自然收集业务字段，必填项齐全后自动落库到「采集数据」，对话继续不打断；落库后同一会话默认不重复采集。
- `ask`（仅答疑）：不主动收集任何数据，纯问答场景。
- 数据类型：`lead`（线索）/ `ticket`（工单）/ `requirement`（需求）/ `appointment`（预约）/ `custom`（自定义）。

### 3. 业务字段

驱动采集器与质量校验的字段定义，支持六种类型：

| 类型 | 说明 | 校验 |
|------|------|------|
| `string` | 短文本 | 非空 |
| `text` | 长文本 | 非空 |
| `number` | 数字 | 数字格式 |
| `phone` | 电话 | 手机号/区号电话格式 |
| `email` | 邮箱 | 邮箱格式 |
| `enum` | 枚举 | 值必须在 `options` 列表内 |

字段 key 仅接受小写字母/数字/下划线，会自动规范化（大写转小写、`-` 转 `_`、重名去重）。默认助手不单独配字段时，运行时回退「系统设置」里的全局业务字段（v0.5.1 起默认为空，即不采集；管理员显式配置后才生效）。

### 4. 业务上下文（Web Context）

嵌入方通过 Embed API（`LeadChat.init({ context })` 或运行期 `LeadChat.setContext()`）传入宿主上下文（如 `order_id`、`plan`、登录用户 ID）。安全规则：

- 仅接受扁平的标量键值（字符串/数字/布尔），嵌套对象、数组一律拒绝；
- 最多 20 个键，键 ≤50 字符，单个值 ≤500 字符；
- 仅当助手配置了上下文白名单（`allowed_fields`）时按白名单过滤；白名单为空数组表示不限制；
- 清洗后的上下文以独立段落注入 Prompt，供模型参考，不会写入采集数据。

### 5. UI 覆盖与默认助手继承

- 默认助手（`default`）的话术/欢迎语/主题/标题继承「系统设置」，不复制配置；v0.5 全新部署即为通用问答助手；v0.5.1 起默认零采集字段；
- 其他助手可在 `ui_config` 逐项覆盖：标题、欢迎语、主题色、图标、气泡、位置；未覆盖项继承全局；
- 停用的助手不会服务请求，挂件与消息接口会自动回退到当前默认助手。
