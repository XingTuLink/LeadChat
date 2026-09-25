# LeadChat

**中文** | [English Documentation](README_EN.md)

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPL%20v3-blue.svg" alt="License: AGPL v3"/></a>
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python"/>
  <img src="https://img.shields.io/badge/FastAPI-0.110+-green.svg" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/docker-ready-green.svg" alt="Docker"/>
  <img src="https://img.shields.io/badge/version-0.6.0-orange.svg" alt="Version"/>
</p>

**一行代码嵌入任何 Web 系统，用对话连接用户与业务。**

LeadChat 是一个开源的 Web AI 助手（Web AI Interaction Layer）：官网、SaaS 控制台、内部系统、电商页面，任何 Web 应用加一行脚本，就有一个能基于你的资料回答问题、并（可选地）把对话中的业务信息结构化保存下来的 AI 助手。默认助手开箱即纯问答，不采集任何信息；售后工单、需求收集、预约报名等都是场景配置，销售线索（Lead Generation）也只是可选场景之一，产品本身不绑定具体业务。

## 使用场景

默认的 General Assistant 只做一件事：用户提问，AI 回答。有需要时，再按场景为助手开启字段采集：

1. **Website AI Assistant** — 官网产品问答、资料查询（默认场景，纯问答）
2. **Customer Support** — 售后咨询，收集订单号、问题类型生成工单
3. **Internal Copilot** — 员工查询业务知识、流程制度
4. **Customer Portal Assistant** — 客户门户/自助系统里的业务助手
5. **Requirement Collection** — 售前咨询中结构化收集用户需求
6. **Lead Generation** — 营销页面在对话中收集联系方式（`data_type=lead`，可选场景，默认关闭）

由 [西安栈上月明软件科技有限公司](https://zsoftym.com) 开源维护。

---

## 为什么是 LeadChat

把 AI 接进一个已有 Web 系统，通常要自己写聊天窗、对话接口、RAG、提示词、数据落库和模型对接。LeadChat 把这些收敛成一个可嵌入层：

- **一行代码嵌入**：单文件挂件，无运行时依赖，Shadow DOM 样式隔离，后端地址自动推导；
- **可配置 AI Assistant**：通用问答、售后客服、内部 Copilot、需求收集、销售线索等场景各是一个 Assistant，独立配置话术、采集字段、上下文白名单与外观，各自有独立嵌入代码；
- **RAG 知识库**：上传产品文档，AI 基于真实资料回答并附引用来源；
- **业务数据交互（Business Data）**：Assistant 可以根据场景，选择性理解和沉淀对话中的结构化业务信息——姓名、电话、订单号、问题类型、预算等，字段类型与必填规则由你定义；LLM 在对话中自然抽取，缺什么追问什么，收齐后静默落库，全程不需要表单；
- **宿主业务上下文（Web Context）**：嵌入方可把当前页面、记录 ID、用户套餐等扁平上下文传给助手，让回答贴合当下场景；服务端白名单加类型清洗，不额外暴露 Prompt 注入面；
- **两种交互模式**：ASK（纯问答，默认）与 COLLECT（按配置采集结构化业务数据）。

## 特性

### 助手与业务连接

- **可配置 AI Assistant** — 内置通用问答 / 售后客服 / 内部 Copilot / 需求收集 / 销售线索 5 个场景模板（销售线索置末，仅为场景之一）。一个后端可以为不同页面、不同业务系统挂载不同助手，话术、采集字段、上下文白名单、外观各自独立配置；默认 General Assistant 不带任何采集字段
- **业务字段（Business Fields）** — string / text / number / enum / phone / email 六种字段类型，必填规则自定义；LLM 每轮对话自动抽取，带质量门禁（电话位数、邮箱格式、占位词/否定词过滤），不编造信息；字段不齐时自然追问
- **采集数据统一落库（Collected Data）** — lead / ticket / requirement / appointment / custom 五种数据类型统一存入 collected_data 一张表
- **Web Context 注入** — 通过 `LeadChat.init({ context: {...} })` 传入宿主系统上下文，白名单过滤后以业务上下文段落注入 Prompt；仅接受扁平标量值，嵌套或超长自动拒绝
- **对话生命周期** — 闲置自动结束（阈值可配）、手动结束、删除时自动解绑采集数据

### 对话与知识

- **流式对话（SSE）** — 回复逐 token 呈现；代理不支持时自动降级普通请求，非流式接口保留
- **Markdown 渲染** — AI 回复中的标题、加粗、列表、引用、表格、行内/代码块在挂件与后台对话记录中直接排版（先转义后格式化，防注入）
- **RAG 知识库** — 支持 PDF / DOCX / TXT / MD，自动解析、切片、向量化（ChromaDB），回答附带引用来源；内置本地 Embedding 模型，零配置、零额外 API 成本
- **主动触达** — 欢迎语加定时自动弹出的引导气泡，文案与延迟均可配置

### 挂件

- **一行代码嵌入** — 单文件原生 JS（约 37KB），无运行时依赖；内置安全 Markdown 渲染器
- **Embed API** — `LeadChat.init({ assistant, context, theme, ... })` 程序化接入，支持脚本加载前队列调用；旧 `data-*` 属性写法继续兼容
- **可配置外观** — 主题色、按钮图标（5 个预设加自定义上传）、位置、标题、欢迎语；每个助手可独立覆盖
- **悬浮色自动计算** — 悬浮色由主题色经 HSL 算法生成（亮色加深、深色提亮）
- **Shadow DOM 隔离** — 与宿主页面样式互不污染

### 后台与部署

- **Vue3 + Ant Design Vue 管理后台** — 仪表盘、助手管理、对话记录、知识库、采集数据、系统设置；前端依赖全部本地化，内网/离线可用
- **嵌入兼容** — 旧 `data-*` 属性与无 assistant_id 的挂件请求继续支持
- **多模型支持** — OpenAI / DeepSeek / 通义千问 / 智谱 / Ollama 本地模型 / 任意 OpenAI 兼容接口（基于 LiteLLM 统一接入）
- **Docker 部署** — 数据卷加模型缓存卷持久化，重建容器不丢数据、不重复下载模型
- **双数据库** — SQLite 零配置开箱，PostgreSQL 通过环境变量切换

## 架构

### 总体架构

LeadChat 在宿主系统与 AI/数据能力之间充当一个 Web AI 交互层：

```
┌────────────────────────────────────────────────────────────────┐
│  官网 · SaaS 控制台 · 内部系统 · H5 · 电商页面（任何 Web 应用）      │
│                                                                  │
│  <script src="…/leadchat.min.js"></script>                       │
│  LeadChat.init({ assistant: "support", context: { order_id } })  │
└──────────────────────────────────┬───────────────────────────────┘
                                   │ HTTP / JSON（CORS 可配）
┌──────────────────────────────────▼───────────────────────────────┐
│            Web AI Embed（原生 JS · 单文件 · Shadow DOM）           │
│   浮动按钮 / 欢迎气泡 / 聊天窗 / 主题算法 / Embed API / Context     │
└──────────────────────────────────┬───────────────────────────────┘
                                   │
┌──────────────────────────────────▼───────────────────────────────┐
│                    FastAPI 后端（async）                          │
│                                                                   │
│   ┌──────────────────────── Assistant 层 ─────────────────────┐  │
│   │ Instructions（话术） · Business Fields · Context 白名单    │  │
│   │ Collect 配置(ask/collect · data_type) · UI 覆盖            │  │
│   │ 通用 / 售后 / 内部 / 需求 / 销售线索 —— 默认助手纯问答继承全局 │  │
│   └───────┬───────────────────────────┬───────────────────────┘  │
│           │                           │                          │
│   ┌───────▼────────┐         ┌────────▼─────────┐  ┌───────────┐  │
│   │ 对话引擎        │         │ 业务数据交互层     │  │ Admin API │  │
│   │ RAG 检索        │         │ 字段抽取/质量门禁  │  │ 助手 CRUD │  │
│   │ Context 注入    │         │ 缺字段自然追问     │  │ 采集数据  │  │
│   └───────┬─────────┘         └────────┬─────────┘  └───────────┘  │
│           │                            │                           │
│   ┌───────▼──────┐ ┌───────────────────▼──────────────────────┐    │
│   │  ChromaDB    │ │  SQLAlchemy (async)                      │    │
│   │  向量检索     │ │  assistants / business_fields /          │    │
│   │              │ │  collected_data / conversations / msgs   │    │
│   └──────────────┘ │  SQLite / PostgreSQL                    │    │
│                    └──────────────────────────────────────────┘    │
└──────────────────────────────────┬─────────────────────────────────┘
                                   │ LiteLLM 统一接入
                ┌──────────────────┼──────────────────┐
                ▼                  ▼                  ▼
       OpenAI/DeepSeek        通义/智谱/GLM        Ollama 本地模型
```

### 一次对话的流程

```mermaid
sequenceDiagram
    participant V as 访客（挂件）
    participant B as FastAPI 后端
    participant K as ChromaDB 知识库
    participant L as LLM（DeepSeek/OpenAI/…）

    V->>B: POST /api/chat/message（assistant_id + context + 消息）
    B->>B: 解析 Assistant（缺省回退默认助手）+ Context 白名单清洗
    B->>K: 语义检索 top-k 知识片段
    B->>B: 组装 Instructions + 业务上下文 + RAG + 采集引导
    B->>L: 补全请求（RAG 上下文 + 字段抽取指令）
    L-->>B: 回答正文 + 抽取到的字段
    B->>B: 按字段类型做质量门禁 → 更新会话草稿
    alt 必填字段收齐（collect 模式）
        B->>B: 写入 CollectedData（lead/ticket/requirement/… 统一表）
        B-->>V: 回答 + 自然确认（"已为您记录…"）
    else 仍有缺失（仅 collect 模式）
        B-->>V: 回答 + 一次只问一个字段（"方便告诉我您的订单号吗？"）
    end
```

### 技术栈

| 层 | 技术 |
|---|---|
| 后端框架 | Python 3.11 · FastAPI · SQLAlchemy 2.0 (async) |
| 数据库 | SQLite（aiosqlite，默认）/ PostgreSQL（asyncpg） |
| 向量库 | ChromaDB（内置 ONNX MiniLM 本地 Embedding） |
| 模型接入 | LiteLLM（OpenAI / DeepSeek / Qwen / GLM / Ollama / 自定义） |
| 聊天挂件 | 原生 JavaScript · Shadow DOM · 无构建依赖 |
| 管理后台 | Vue 3 · Ant Design Vue 4 · Axios（全部本地化，无 CDN） |
| 部署 | Docker · Docker Compose |

## 快速开始

代码仓库（三个平台内容同步，国内网络可用 Gitee / AtomGit）：

| 平台 | 地址 |
|---|---|
| GitHub | https://github.com/XingTuLink/LeadChat |
| Gitee | https://gitee.com/XingTuLink/lead-chat |
| AtomGit | https://atomgit.com/XingTuLink/LeadChat |

### Docker 部署（推荐）

```bash
git clone https://github.com/XingTuLink/LeadChat.git
cd LeadChat
cp .env.example .env
# 编辑 .env：至少修改 ADMIN_PASSWORD
docker compose up -d --build
```

启动后打开管理后台，在「模型管理」中添加对话模型并激活（可先点「测试」验证），挂件才能正常对话。

| 入口 | 地址 |
|---|---|
| 管理后台 | `http://your-server:11999/admin/`（密码为 .env 中设置的 ADMIN_PASSWORD） |
| 挂件演示页 | `http://your-server:11999/widget/demo.html` |

### 嵌入任何 Web 系统

**方式一：一行 script（最简，默认助手）**

```html
<script src="http://your-server:11999/widget/leadchat.min.js?v=0.6.0"></script>
```

**方式二：Embed API（指定助手 + 宿主业务上下文，适合 SPA / 业务系统）**

```html
<script>
  // 队列必须在挂件脚本加载前声明；脚本加载后同样的 API 可直接调用
  window.LeadChat = window.LeadChat || [];
  window.LeadChat.push(["init", {
    assistant: "support",                    // 助手 ID（后台创建），省略则用默认助手
    context: {                               // 宿主业务上下文（扁平键值，受白名单约束）
      page: location.pathname,
      order_id: "O-20260917-001",
      plan: "enterprise"
    }
  }]);
</script>
<script src="http://your-server:11999/widget/leadchat.min.js?v=0.6.0"></script>
<script>
  // 运行时也可更新上下文（如 SPA 路由切换后）
  LeadChat.setContext({ page: "/orders/O-002", order_id: "O-002" });
  LeadChat.open();
</script>
```

不同页面挂不同助手：售后页用 `assistant: "support"`，内部系统用 `"internal"`，营销页也可以挂销售线索助手，一个后端同时服务多个场景；不指定时默认助手始终是纯问答。

**LeadChat API**

| 方法 | 说明 |
|---|---|
| `LeadChat.init(options)` | 初始化；脚本加载前用队列调用，加载后直接调用 |
| `LeadChat.setContext(ctx)` | 更新业务上下文（每轮消息上送，服务端按白名单过滤） |
| `LeadChat.getContext()` | 读取当前上下文 |
| `LeadChat.open()` / `LeadChat.close()` | 打开 / 收起聊天窗 |

`init` 参数：`assistant`（ID 字符串或 `{ id }`）、`context`、`api`、`theme`、`position`、`title`、`welcome`、`icon`。

**旧版 data-* 属性（继续支持）**

挂件会从自身脚本地址自动推导后端根地址，同域部署（含 `/leadchat/` 等子路径反代）可省略 `data-api`；新增 `data-assistant` 指定助手：

| 属性 | 说明 | 默认 |
|---|---|---|
| `data-api` | 后端地址；同域（含子路径）部署可省略 | 自动推导 |
| `data-assistant` | 助手 ID | `default`（纯问答） |
| `data-theme` | 主题色（强制指定，优先于后台配置） | 后台配置 |
| `data-position` | 按钮位置：`right` / `left` | 后台配置 |
| `data-icon` | 按钮图标：`chat` / `message` / `headset` / `spark` / `smile` | 后台配置 |
| `data-title` | 窗口标题 | 公司名 |
| `data-welcome` | 欢迎语 | 后台配置 |

> 挂件 URL 上的 `?v=x.y.z` 用于缓存治理：服务端升级后，客户网站自动拿到新版挂件。

### 本地开发（不用 Docker）

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # macOS / Linux
pip install -r backend/requirements.txt
cp .env.example .env              # 填好配置
cd backend
uvicorn app.main:app --reload --port 11999
```

启动时自动建表、初始化默认配置；知识库首次上传时自动下载本地 Embedding 模型（约 80MB，也可提前放到 `~/.cache/chroma/onnx_models/`）。

## 支持的大模型

在后台「模型管理」中添加，支持多个模型在线切换：

| 厂商 | 模型示例 | 说明 |
|--------|---------|------|
| DeepSeek | `deepseek-chat` | 性价比高 |
| OpenAI | `gpt-4o-mini` | |
| 通义千问 | `qwen-plus` / `qwen-turbo` | 阿里云 DashScope |
| 智谱 | `glm-4-flash` / `glm-4-air` | 有免费模型 |
| Ollama | `llama3.1` / `qwen2.5` | 完全本地；容器内端点填 `http://host.docker.internal:11434` |
| 自定义 | 任意 OpenAI 兼容模型 | 需自行填写 API 端点 |

Embedding 通过 `EMBEDDING_MODEL` 配置云端模型（建议带厂商前缀，如 `qwen/text-embedding-v3`）；留空则使用 ChromaDB 内置本地模型，零配置、零 API 成本、数据不出服务器。

## 管理后台

- **仪表盘** — 今日/累计对话、采集数据、消息、文档统计
- **模型管理** — 添加多个对话模型（厂商/模型标识/密钥/端点），连通性测试，在线切换立即生效
- **助手管理** — 按场景模板新建助手、Instructions 编辑、采集模式（ask/collect）与数据类型、业务字段编排、上下文白名单、外观覆盖；一键生成两种嵌入代码
- **对话记录** — 完整聊天过程、AI 引用的知识来源、对话详情抽屉；支持结束/删除
- **知识库** — 拖拽上传（两阶段进度：传输百分比 → 解析向量化中），自动切片向量化
- **采集数据** — 各助手采集的结构化数据（工单/需求/预约/自定义/线索），按类型与助手筛选、状态流转
- **系统设置** — 默认助手的全局回退：公司信息、系统提示词、通用业务字段（默认为空）与采集引导、挂件主题色/图标/欢迎语/自动弹出、品牌页脚开关

## 核心配置

完整说明见 [docs/CONFIG.md](docs/CONFIG.md)。对话模型在后台「模型管理」配置，环境变量中不再包含模型密钥。

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `ADMIN_PASSWORD` | `change_this_before_running` | 后台管理密码，首次启动前务必修改 |
| `DATABASE_URL` | SQLite | 换 PostgreSQL：`postgresql+asyncpg://user:pass@host:5432/leadchat` |
| `CORS_ORIGINS` | `*` | 允许跨域来源 |
| `CONVERSATION_TIMEOUT_MINUTES` | `30` | 对话闲置自动结束阈值，`0` 关闭 |
| `BRANDING_FOOTER_ENABLED` | `true` | 品牌页脚，设 `false` 关闭 |

## 构建与二次开发

```
LeadChat/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI 入口（静态资源挂载、缓存策略）
│   │   ├── config.py        # 环境变量配置
│   │   ├── database.py      # async 数据库
│   │   ├── models/          # assistant / conversation / message / knowledge / config
│   │   ├── schemas/         # Pydantic 模型
│   │   ├── routers/         # auth / chat / assistants / collected_data / knowledge / config
│   │   └── services/        # assistant_store / business_fields / context / chat_engine
│   │                        # data_collector / llm / rag / document / config_store
│   └── requirements.txt
├── widget/
│   ├── src/                 # api / md / ui / chat / embed / styles
│   ├── build.js             # 构建脚本（无 npm 依赖）
│   └── dist/leadchat.min.js # 产出的单文件挂件
├── admin/index.html         # 管理后台（Vue3 + antd，单文件）
├── docs/                    # 部署 / 配置 / API 文档
├── Dockerfile / docker-compose.yml
├── VERSION                  # 版本号唯一来源
└── .env.example
```

### 后端开发

```bash
cd backend && uvicorn app.main:app --reload --port 11999
# 交互式 API 文档：http://127.0.0.1:11999/docs
```

### 挂件开发与构建

修改 `widget/src/` 后重新拼接为单文件（无需 npm install）：

```bash
cd widget
node build.js        # 产出 dist/leadchat.min.js
node --check dist/leadchat.min.js
```

> 修改挂件后记得同步升级 demo 页和后台嵌入代码里的 `?v=x.y.z`，避免浏览器缓存旧版。

### 管理后台开发

`admin/index.html` 为单文件应用（Vue 3 + Ant Design Vue 通过本地 vendor 目录加载）。Docker 部署方式下，改动后重新构建镜像：

```bash
docker compose up -d --build
```

数据与模型缓存分别在 `./data` 与 `chroma_cache` 卷中，重建不受影响。

### 常用运维命令

```bash
docker compose logs -f          # 实时日志
docker compose restart          # 重启
docker compose down             # 停止（数据保留）
docker compose down -v          # 停止并清除模型缓存卷（数据卷 ./data 保留）
```

## FAQ

**Q：不填 API Key 能用吗？**
能。服务正常启动，AI 回复返回兜底话术；填入 Key 后立即使用真实模型。

**Q：知识库上传"卡住"？**
首次上传需下载本地 Embedding 模型（约 80MB），Docker 部署已通过 `chroma_cache` 卷持久化，重建容器不重复下载；上传过程有两阶段进度提示。

**Q：内网/离线环境能部署吗？**
能。后台前端依赖已全部本地化；Ollama 加本地 Embedding 的组合可以完全离线运行。

**Q：后台改了主题色/图标，挂件没变？**
确认挂件标签没有用 `data-theme`/`data-icon` 强制覆盖（脚本属性优先于后台配置）；正常刷新即可拿到新配置。

## Roadmap

关于版本号：LeadChat 最早是我们自己业务系统里用的内部工具，在内部迭代了多个版本之后才决定开源。所以第一个公开版本直接从 0.5.x 开始，而不是 0.0.1；下面 0.5 之前的条目是内部迭代的记录。

LeadChat 专注于 Web AI Interaction Layer，目标不是做 AI 中台或 Agent 平台，而是让 AI 能低成本、相对安全地进入现有 Web 应用，与用户、知识和业务系统交互。

### 已发布

- [x] v0.1 基础对话 + Web Widget + Docker
- [x] v0.2 RAG 知识库 + 管理后台
- [x] v0.3 在我们自己的官网上线试用了一段时间，根据暴露的问题持续修改优化
- [x] v0.4 可配置助手、业务字段、Collected Data、Web Context、Embed API
- [x] v0.5.x Assistant-first 重构、SSE 流式对话、Markdown 排版等开源前打磨

### v0.6 — Interaction Experience

- [x] 多模型在线切换
- [ ] 快捷问题（Suggested Questions）
- [ ] Webhook / Event Webhook
- [ ] 助手独立模型与知识库配置
- [ ] Embed API 增强
- [ ] 挂件交互体验优化
- [ ] Conversation 事件完善

### v0.7 — Retrieval & Context

- [ ] BM25 + 向量混合检索
- [ ] Reranking
- [ ] 按元数据过滤检索
- [ ] 助手级知识库
- [ ] Web Context 增强
- [ ] 上下文生命周期与安全策略
- [ ] 检索链路与引用展示增强

### v0.8 — Actions & MCP

- [ ] Action / Tool 抽象
- [ ] HTTP / Webhook Action
- [ ] MCP Client，调用 MCP 工具
- [ ] 工具 Schema 与参数校验
- [ ] 工具调用确认与安全策略
- [ ] 助手直接触发业务系统动作

> LeadChat 只作为 MCP / 工具的使用方，不做 MCP Server 平台，也不做工具市场。

### v0.9 — Production Readiness

- [ ] Rate Limit
- [ ] Webhook 签名
- [ ] Prompt Injection 防护增强
- [ ] 工具 / 上下文安全控制
- [ ] Conversation Trace
- [ ] LLM / 检索 / 工具的指标观测
- [ ] Health Check / Metrics
- [ ] 备份 / 迁移 / 恢复
- [ ] 生产部署文档

### v1.0 — Web AI Assistant Foundation

v1.0 不做收费和商业版，目标是形成完整、稳定的开源 Web AI 交互层，覆盖 Assistant、Conversation、Knowledge、混合检索、Web Context、Business Data、Actions、MCP、Webhook、可观测性与安全。

### v1.x — 持续演进

- [ ] 更多 LLM / Embedding 提供方
- [ ] 更多知识来源 Connector
- [ ] 更多 Action / Tool 适配器
- [ ] Workspace 资源隔离
- [ ] 社区贡献的助手模板
- [ ] 更多 Web 框架 / CMS 集成

### 产品边界

LeadChat 不计划成为：

- Agent Runtime / 多 Agent 编排平台
- MCP Server 平台
- A2A 平台
- SaaS 计费 / 支付平台

这些能力留给其他项目或未来的 AI Platform。LeadChat 的边界是：

> Connect AI with users and business systems through the Web.

## 参与贡献

欢迎提交 Issue 与 Pull Request：Fork → 分支 → 提交 → PR。后端改动请确保 uvicorn 能正常启动、核心接口跑通。

- 发现 Bug：[Bug 反馈](https://github.com/XingTuLink/LeadChat/issues/new?template=bug_report.yml)
- 新想法：[功能建议](https://github.com/XingTuLink/LeadChat/issues/new?template=feature_request.yml)

## License

本项目基于 [GNU Affero General Public License v3.0（AGPL-3.0）](LICENSE) 开源，© 西安栈上月明软件科技有限公司。

请注意 AGPL 的关键约束：如果你修改了本项目并通过网络向用户提供服务（包括 SaaS / 托管形式），必须以相同协议向网络使用者公开修改后的完整源代码。不受 AGPL 条款约束的商业授权可联系作者洽谈。
