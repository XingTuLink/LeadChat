# LeadChat

[中文文档](README.md) | **English**

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPL%20v3-blue.svg" alt="License: AGPL v3"/></a>
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python"/>
  <img src="https://img.shields.io/badge/FastAPI-0.110+-green.svg" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/docker-ready-green.svg" alt="Docker"/>
  <img src="https://img.shields.io/badge/version-0.5.2-orange.svg" alt="Version"/>
</p>

**Embed an AI assistant into any web system with one line of code — conversational AI that connects users with your business.**

LeadChat is an open-source Web AI Assistant (Web AI Interaction Layer): marketing sites, SaaS consoles, internal tools, e-commerce pages — any web application gets an AI that answers from your documents and, optionally, structures information gathered in conversation. The default assistant is pure Q&A out of the box and captures nothing. Support tickets, requirement intake and appointment booking are scenario configurations; lead generation is likewise just one optional scenario. The product itself is not bound to any particular business.

## Use Cases

The default General Assistant does exactly one thing: users ask, the AI answers. Enable field capture per assistant only when you need it:

1. **Website AI Assistant** — product Q&A and information lookup on marketing sites (default scenario, pure Q&A)
2. **Customer Support** — after-sales questions; capture order ID and issue type to create tickets
3. **Internal Copilot** — employees querying business knowledge and process documentation
4. **Customer Portal Assistant** — an AI assistant inside customer portals and self-service systems
5. **Requirement Collection** — structure user requirements during pre-sales conversations
6. **Lead Generation** — capture contact details in conversation on marketing pages (`data_type=lead`; one optional use case, disabled by default)

Open-sourced and maintained by [Xi'an Zhanshang Yueming Software Technology Co., Ltd.](https://zsoftym.com) (栈上月明).

---

## Why LeadChat

Wiring AI into an existing web system usually means building a chat UI, conversation API, RAG pipeline, prompts, data persistence and model integrations yourself. LeadChat collapses all of that into one embeddable layer:

- **One-line embed**: a single vanilla-JS file, no runtime dependencies, Shadow DOM isolation, automatic API-origin inference;
- **Configurable AI assistants**: general Q&A, customer support, internal Copilot, requirement intake and sales-lead capture are separate Assistants, each with its own instructions, collection fields, context whitelist, look & feel and embed snippet;
- **RAG knowledge base**: upload documents and the AI answers from real materials with cited sources;
- **Business data interaction (Business Data)**: depending on the scenario, an Assistant can understand and persist structured business information from the conversation — names, phone numbers, order IDs, issue types, budgets, etc. Field types and required rules are yours to define; the LLM extracts values naturally, asks for missing ones, and stores complete records silently. No forms needed;
- **Host business context (Web Context)**: pass the current page, record ID or user plan as flat context so answers fit the situation; server-side whitelisting and type sanitization keep the prompt-injection surface small;
- **Two interaction modes**: ASK (pure Q&A, the default) and COLLECT (structured data capture per configuration).

## Features

### Assistants & Business Connection

- **Configurable AI assistants** — five built-in scenario templates (general Q&A / support / internal Copilot / requirement intake / sales leads, with sales listed last as just one scenario). One backend can mount different assistants on different pages or systems, each with independent instructions, fields, context whitelist and look & feel; the default General Assistant has no capture fields
- **Business Fields** — six field types (string / text / number / enum / phone / email) with custom required rules; the LLM extracts values every turn with quality gates (phone length, email format, placeholder/negation filtering) and does not fabricate information, following up naturally for missing values
- **Unified Collected Data store** — lead / ticket / requirement / appointment / custom types all go into one `collected_data` table
- **Web Context injection** — pass host-system context through `LeadChat.init({ context: {...} })`; whitelisted keys are injected into the prompt as a business-context block; only flat scalar values are accepted (nested/oversized values rejected)
- **Conversation lifecycle** — auto-close after idle timeout (configurable), manual close, automatic unbinding of collected data on deletion

### Chat & Knowledge

- **Streaming chat (SSE)** — replies render token by token; the widget automatically falls back to plain requests when a proxy blocks SSE, and the non-streaming API stays available
- **Markdown rendering** — headings, bold text, lists, quotes, tables and inline/fenced code in AI replies are formatted in both the widget and the admin conversation viewer (HTML is escaped first — injection-safe)
- **RAG knowledge base** — PDF / DOCX / TXT / MD supported, with automatic parsing, chunking and vectorization (ChromaDB); answers come with cited sources. A built-in local embedding model means zero configuration and zero extra API cost
- **Proactive engagement** — welcome message plus a timed auto-popup greeting bubble (copy and delay both configurable)

### Widget

- **One-line embed** — a single vanilla JavaScript file (~37KB) with no runtime dependencies; built-in safe Markdown renderer
- **Embed API** — programmatic setup via `LeadChat.init({ assistant, context, theme, ... })` with a pre-load queue; legacy `data-*` attributes remain supported
- **Configurable appearance** — theme color, button icon (5 presets plus custom upload), position, title, welcome message; assistants can override the look independently
- **Automatic hover color** — derived from the theme color via an HSL algorithm (darken light colors, lighten dark ones)
- **Shadow DOM isolation** — no style leakage between the widget and the host page

### Admin & Deployment

- **Vue 3 + Ant Design Vue admin panel** — dashboard, assistants, conversations, knowledge base, collected data, system settings; front-end dependencies are all vendored locally, so it works on intranets / air-gapped networks
- **Embed compatibility** — legacy `data-*` attributes and assistant-less widget requests keep working
- **Multiple LLM providers** — OpenAI / DeepSeek / Qwen (通义千问) / Zhipu (智谱) / local Ollama / any OpenAI-compatible endpoint (unified through LiteLLM)
- **Docker deployment** — persistent data volume and model-cache volume; rebuilding the container loses no data and re-downloads no models
- **Dual databases** — SQLite works out of the box; switch to PostgreSQL via an environment variable

## Architecture

### Overview

LeadChat acts as a Web AI interaction layer between host systems and AI/data capabilities:

```
┌────────────────────────────────────────────────────────────────┐
│  Marketing site · SaaS console · Internal tools · H5 · Shop     │
│                     (any web application)                        │
│                                                                  │
│  <script src="…/leadchat.min.js"></script>                       │
│  LeadChat.init({ assistant: "support", context: { order_id } })  │
└──────────────────────────────────┬───────────────────────────────┘
                                   │ HTTP / JSON (CORS configurable)
┌──────────────────────────────────▼───────────────────────────────┐
│           Web AI Embed (vanilla JS · single file · Shadow DOM)   │
│  Floating button / welcome bubble / chat window / Embed API /    │
│  theme algorithm / Context                                        │
└──────────────────────────────────┬───────────────────────────────┘
                                   │
┌──────────────────────────────────▼───────────────────────────────┐
│                    FastAPI backend (async)                       │
│                                                                   │
│   ┌──────────────────── Assistant layer ─────────────────────┐  │
│   │ Instructions · Business Fields · Context whitelist       │  │
│   │ Collect config (ask/collect · data_type) · UI overrides   │  │
│   │ general / support / internal / requirement / sales        │  │
│   │ — the default assistant inherits global settings         │  │
│   └───────┬───────────────────────────┬──────────────────────┘  │
│           │                           │                          │
│   ┌───────▼────────┐         ┌────────▼─────────────┐ ┌────────┐ │
│   │ Conversation   │         │ Business data         │ │Admin   │ │
│   │ engine + RAG   │         │ interaction layer     │ │ API    │ │
│   │ Context inject │         │ extraction / gates    │ │CRUD    │ │
│   └───────┬────────┘         └────────┬─────────────┘ └────────┘ │
│           │                           │                           │
│   ┌───────▼──────┐ ┌──────────────────▼──────────────────────┐   │
│   │  ChromaDB    │ │  SQLAlchemy (async)                     │   │
│   │  vector      │ │  assistants / business_fields /         │   │
│   │              │ │  collected_data / conversations / msgs  │   │
│   └──────────────┘ │  SQLite / PostgreSQL                    │   │
│                    └──────────────────────────────────────────┘   │
└──────────────────────────────────┬─────────────────────────────────┘
                                   │ via LiteLLM
                ┌──────────────────┼──────────────────┐
                ▼                  ▼                  ▼
       OpenAI/DeepSeek        Qwen/Zhipu/GLM      Ollama local models
```

### End-to-end flow of one conversation

```mermaid
sequenceDiagram
    participant V as Visitor (widget)
    participant B as FastAPI backend
    participant K as ChromaDB knowledge base
    participant L as LLM (DeepSeek/OpenAI/…)

    V->>B: POST /api/chat/message (assistant_id + context + message)
    B->>B: Resolve Assistant (fall back to default) + sanitize context via whitelist
    B->>K: Semantic search for top-k chunks
    B->>B: Assemble Instructions + business context + RAG + collection guide
    B->>L: Completion request (RAG context + extraction instructions)
    L-->>B: Answer text + extracted fields
    B->>B: Per-type quality gates → update per-conversation draft
    alt All required fields collected (collect mode)
        B->>B: Write CollectedData (lead/ticket/requirement/… unified table)
        B-->>V: Answer + natural confirmation ("Got it, I've noted your…")
    else Fields still missing (collect-mode assistants only)
        B-->>V: Answer + ask for exactly one field ("Could you tell me your order number?")
    end
```

### Tech stack

| Layer | Technology |
|---|---|
| Backend framework | Python 3.11 · FastAPI · SQLAlchemy 2.0 (async) |
| Database | SQLite (aiosqlite, default) / PostgreSQL (asyncpg) |
| Vector store | ChromaDB (built-in ONNX MiniLM local embeddings) |
| Model access | LiteLLM (OpenAI / DeepSeek / Qwen / GLM / Ollama / custom) |
| Chat widget | Vanilla JavaScript · Shadow DOM · no build toolchain |
| Admin panel | Vue 3 · Ant Design Vue 4 · Axios (all vendored, no CDN) |
| Deployment | Docker · Docker Compose |

## Quick Start

Code repositories (all three are kept in sync; Gitee / AtomGit work better from mainland China):

| Platform | URL |
|---|---|
| GitHub | https://github.com/XingTuLink/LeadChat |
| Gitee | https://gitee.com/XingTuLink/lead-chat |
| AtomGit | https://atomgit.com/XingTuLink/LeadChat |

### Docker deployment (recommended)

```bash
git clone https://github.com/XingTuLink/LeadChat.git
cd LeadChat
cp .env.example .env
# Edit .env: fill in LLM_API_KEY and change ADMIN_PASSWORD
docker compose up -d --build
```

After startup:

| Entry point | URL |
|---|---|
| Admin panel | `http://your-server:11999/admin/` (password = the ADMIN_PASSWORD you set in .env) |
| Widget demo page | `http://your-server:11999/widget/demo.html` |

### Embedding into any web system

**Option 1: one-line script (simplest, default assistant)**

```html
<script src="http://your-server:11999/widget/leadchat.min.js?v=0.5.2"></script>
```

**Option 2: Embed API (specific assistant + host context; for SPAs / business systems)**

```html
<script>
  // Declare the queue BEFORE the widget script; the same API works directly after load
  window.LeadChat = window.LeadChat || [];
  window.LeadChat.push(["init", {
    assistant: "support",                    // Assistant ID (created in the admin panel); omit = default
    context: {                               // Host business context (flat key/values, whitelisted server-side)
      page: location.pathname,
      order_id: "O-20260917-001",
      plan: "enterprise"
    }
  }]);
</script>
<script src="http://your-server:11999/widget/leadchat.min.js?v=0.5.2"></script>
<script>
  // Context can be updated at runtime (e.g. after SPA route changes)
  LeadChat.setContext({ page: "/orders/O-002", order_id: "O-002" });
  LeadChat.open();
</script>
```

Mount different assistants on different pages: `support` on after-sales pages, `"internal"` on internal systems, and a sales-lead assistant on marketing pages if you need one — one backend serves every scenario; with no assistant specified, the default assistant always stays pure Q&A.

**LeadChat API**

| Method | Description |
|---|---|
| `LeadChat.init(options)` | Initialize; queue the call before the script loads, or call directly afterwards |
| `LeadChat.setContext(ctx)` | Update business context (sent on every message, filtered by the server whitelist) |
| `LeadChat.getContext()` | Read the current context |
| `LeadChat.open()` / `LeadChat.close()` | Open / close the chat window |

`init` options: `assistant` (ID string or `{ id }`), `context`, `api`, `theme`, `position`, `title`, `welcome`, `icon`.

**Legacy data-* attributes (still supported)**

The widget derives the backend root URL from its own script URL, so same-origin deployments — including reverse-proxied subpaths such as `/leadchat/` — need no `data-api`. The `data-assistant` attribute selects an assistant:

| Attribute | Description | Default |
|---|---|---|
| `data-api` | Backend URL; omit for same-origin (including subpath) deployments | Auto-derived |
| `data-assistant` | Assistant ID | `default` |
| `data-theme` | Theme color (forced; takes precedence over admin settings) | Admin setting |
| `data-position` | Button position: `right` / `left` | Admin setting |
| `data-icon` | Button icon: `chat` / `message` / `headset` / `sparkle` / `smile` | Admin setting |
| `data-title` | Window title | Company name |
| `data-welcome` | Welcome message | Admin setting |

> The `?v=x.y.z` query string is for cache busting: after a server upgrade, customer sites automatically fetch the new widget.

### Local development (without Docker)

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # macOS / Linux
pip install -r backend/requirements.txt
cp .env.example .env              # fill in your settings
cd backend
uvicorn app.main:app --reload --port 11999
```

Tables are created and default settings initialized automatically on startup. On the first knowledge-base upload the local embedding model (~80MB) is prepared automatically (you can also place it under `~/.cache/chroma/onnx_models/` in advance).

## Supported LLM providers

| Provider | `LLM_PROVIDER` | Example models | Notes |
|--------|----------------|---------|------|
| DeepSeek | `deepseek` | `deepseek-chat` | Good price/performance |
| OpenAI | `openai` | `gpt-4o-mini` | |
| Qwen | `qwen` | `qwen-plus` / `qwen-turbo` | Alibaba Cloud DashScope |
| Zhipu GLM | `glm` | `glm-4-flash` / `glm-4-air` | Free-tier models available |
| Ollama | `ollama` | `llama3.1` / `qwen2.5` | Fully local (set `LLM_API_BASE` to `http://host.docker.internal:11434`) |
| Custom | `custom` | Any OpenAI-compatible model | Requires `LLM_API_BASE` |

Embeddings can be switched to a cloud model via `EMBEDDING_MODEL`; leave it empty to use ChromaDB's built-in local model (zero config, zero API cost, data stays on your server).

## Admin panel

- **Dashboard** — today's / total conversations, collected data, messages and document stats
- **Assistants** — create from scenario templates, edit Instructions, collection mode (ask/collect) and data type, arrange business fields, context whitelist and UI overrides; generate both embed snippets with one click
- **Conversations** — full chat history, knowledge sources cited by the AI, detail drawer; close / delete supported
- **Knowledge base** — drag-and-drop upload with two-stage progress (transfer percentage → parsing & vectorizing), automatic chunking and vectorization
- **Collected data** — structured records captured by each assistant (tickets / requirements / appointments / custom / leads), filterable by type and assistant, with status workflow
- **System settings** — global fallback for the default assistant: company info, system prompt, business fields (empty by default) and collection guide, widget theme color / icon / welcome message / auto-popup, branding footer toggle

## Configuration

See [docs/CONFIG.md](docs/CONFIG.md) for the full reference.

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `deepseek` | LLM provider |
| `LLM_API_KEY` | — | API key |
| `LLM_MODEL` | `deepseek-chat` | Model name |
| `ADMIN_PASSWORD` | `change_this_before_running` | Admin password — change before first launch |
| `DATABASE_URL` | SQLite | Switch to PostgreSQL: `postgresql+asyncpg://user:pass@host:5432/leadchat` |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |
| `CONVERSATION_TIMEOUT_MINUTES` | `30` | Idle auto-close threshold; `0` disables it |
| `BRANDING_FOOTER_ENABLED` | `true` | Branding footer; set `false` to hide |

## Building & development

```
LeadChat/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI entry (static mounts, cache policy)
│   │   ├── config.py        # Environment settings
│   │   ├── database.py      # async DB
│   │   ├── models/          # assistant / conversation / message / knowledge / config
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── routers/         # auth / chat / assistants / collected_data / knowledge / config
│   │   └── services/        # assistant_store / business_fields / context / chat_engine
│   │                        # data_collector / llm / rag / document / config_store
│   └── requirements.txt
├── widget/
│   ├── src/                 # api / md / ui / chat / embed / styles
│   ├── build.js             # Build script (no npm dependencies)
│   └── dist/leadchat.min.js # Built single-file widget
├── admin/index.html         # Admin panel (Vue3 + antd, single file)
├── docs/                    # Deployment / configuration / API docs
├── Dockerfile / docker-compose.yml
├── VERSION                  # Single source of truth for the version number
└── .env.example
```

### Backend development

```bash
cd backend && uvicorn app.main:app --reload --port 11999
# Interactive API docs: http://127.0.0.1:11999/docs
```

### Widget development & build

After editing `widget/src/`, rebuild the single file (no npm install needed):

```bash
cd widget
node build.js        # outputs dist/leadchat.min.js
node --check dist/leadchat.min.js
```

> After changing the widget, bump the `?v=x.y.z` parameter on the demo page and in the admin embed snippet, so visitors don't get a cached old version.

### Admin panel development

`admin/index.html` is a single-file application (Vue 3 + Ant Design Vue loaded from the local vendor directory). With Docker, rebuild the image after changes:

```bash
docker compose up -d --build
```

Data and the model cache live in the `./data` bind mount and the `chroma_cache` volume respectively, so rebuilds don't affect them.

### Common operations

```bash
docker compose logs -f          # follow logs
docker compose restart          # restart
docker compose down             # stop (data retained)
docker compose down -v          # stop and remove the model-cache volume (./data is still retained)
```

## FAQ

**Q: Can I use it without an API key?**
Yes. The service starts normally and the AI returns a fallback message; once you fill in a key, the real model is used immediately.

**Q: Knowledge-base upload appears "stuck"?**
The first upload prepares the local embedding model (~80MB); with Docker it is persisted in the `chroma_cache` volume, so container rebuilds don't re-download it. Two-stage progress is shown during upload.

**Q: Can it run on an intranet / air-gapped environment?**
Yes. All admin-panel front-end dependencies are vendored locally; the Ollama + local embedding combination runs fully offline.

**Q: I changed the theme color/icon in the admin panel but the widget didn't change?**
Make sure the embed tag doesn't force `data-theme`/`data-icon` (script attributes take precedence over admin settings); a normal refresh picks up the new configuration.

## Roadmap

A note on version numbers: LeadChat started as an internal tool inside our own business systems and went through several internal iterations before we decided to open-source it. That is why the first public release starts at 0.5.x rather than 0.0.1; the entries below v0.5 are the internal iteration record.

LeadChat focuses on the Web AI Interaction Layer. It is not meant to become an AI platform or an agent platform; the goal is to let AI enter existing web applications at low cost and with reasonable safety, interacting with users, knowledge and business systems.

### Released

- [x] v0.1 Basic chat + Web Widget + Docker
- [x] v0.2 RAG knowledge base + admin panel
- [x] v0.3 Trial run on our own website; iterated and fixed the problems that came up
- [x] v0.4 Configurable assistants, Business Fields, Collected Data, Web Context, Embed API
- [x] v0.5.x Assistant-first refactor, SSE streaming, Markdown rendering and other pre-release polish

### v0.6 — Interaction Experience

- [ ] In-dashboard multi-model switching
- [ ] Suggested Questions
- [ ] Webhook / Event Webhook
- [ ] Per-assistant model and knowledge-base configuration
- [ ] Embed API enhancements
- [ ] Widget interaction improvements
- [ ] Conversation events

### v0.7 — Retrieval & Context

- [ ] BM25 + vector hybrid search
- [ ] Reranking
- [ ] Metadata-filtered retrieval
- [ ] Per-assistant knowledge bases
- [ ] Web Context enhancements
- [ ] Context lifecycle and security policies
- [ ] Retrieval trace and citation improvements

### v0.8 — Actions & MCP

- [ ] Action / Tool abstraction
- [ ] HTTP / Webhook Action
- [ ] MCP Client — call MCP tools
- [ ] Tool schemas and parameter validation
- [ ] Tool-call confirmation and security policies
- [ ] Assistants triggering business-system actions directly

> LeadChat only consumes MCP / tools. It will not run an MCP server platform or a tool marketplace.

### v0.9 — Production Readiness

- [ ] Rate limiting
- [ ] Webhook signatures
- [ ] Prompt injection hardening
- [ ] Tool / context access control
- [ ] Conversation trace
- [ ] LLM / retrieval / tool observability
- [ ] Health checks / metrics
- [ ] Backup / migration / recovery
- [ ] Production deployment documentation

### v1.0 — Web AI Assistant Foundation

v1.0 will include no billing or commercial edition. The goal is a complete, stable open-source Web AI interaction layer covering assistants, conversations, knowledge, hybrid retrieval, web context, business data, actions, MCP, webhooks, observability and security.

### v1.x — Ongoing evolution

- [ ] More LLM / embedding providers
- [ ] More knowledge connectors
- [ ] More Action / Tool adapters
- [ ] Workspace resource isolation
- [ ] Community-contributed assistant templates
- [ ] More web framework / CMS integrations

### Product boundary

LeadChat does not plan to become:

- An agent runtime / multi-agent orchestration platform
- An MCP server platform
- An A2A platform
- A SaaS billing / payment platform

These are left to other projects or a future AI platform. LeadChat's boundary is:

> Connect AI with users and business systems through the Web.

## Contributing

Issues and pull requests are welcome: fork → branch → commit → PR. For back-end changes, please make sure uvicorn starts cleanly and the core endpoints work.

- Found a bug? [Bug Report](https://github.com/XingTuLink/LeadChat/issues/new?template=bug_report.yml)
- Have an idea? [Feature Request](https://github.com/XingTuLink/LeadChat/issues/new?template=feature_request.yml)

## License

Licensed under the [GNU Affero General Public License v3.0 (AGPL-3.0)](LICENSE), © Xi'an Zhanshang Yueming Software Technology Co., Ltd.

Key obligation: if you modify the software and make it available to users over a network (including SaaS / hosted offerings), you must make your complete modified source code available to those users under the same license. A commercial license without the AGPL obligations is available from the copyright holder on request.
