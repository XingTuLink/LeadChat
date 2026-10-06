# LeadChat 部署指南

## 前置要求

- Docker 20.10+ 与 Docker Compose v2
- 一个大模型 API Key（DeepSeek / 通义 / 智谱 / OpenAI 任一），或本地 Ollama

## Docker Compose 部署（推荐）

```bash
git clone https://github.com/XingTuLink/LeadChat.git
cd LeadChat
docker compose up -d --build
```

零配置即可启动：默认使用 SQLite、内置本地 Embedding 模型、后台默认密码 `admin123`。
如需修改密码等默认值，再复制 `cp .env.example .env` 并按需调整（文件内所有项均可选）。

启动后：

1. 打开 `http://your-server:11999/admin`，用管理员密码登录（默认 `admin123`，建议正式部署时通过 `ADMIN_PASSWORD` 修改）；
2. 在「模型管理」中选择公有或私有模型服务，填写凭证后保存并激活；
3. 需要知识库时在「知识库」上传文档；
4. 把挂件嵌入代码放到你的网站，开始使用。

未激活任何模型时对话功能不可用。

| 地址 | 用途 |
|------|------|
| `http://your-server:11999/admin` | 管理后台 |
| `http://your-server:11999/widget/leadchat.min.js` | 挂件脚本 |
| `http://your-server:11999/health` | 健康检查 |

### 更新版本

```bash
git pull
docker compose up -d --build
```

### 查看日志

```bash
docker compose logs -f
```

## 本地开发运行

```bash
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload --port 11999
```

修改挂件源码（widget/src/）后重新构建：

```bash
node widget/build.js
```

## HTTPS 反向代理

挂件通过 HTTPS 网站嵌入时，后端必须也是 HTTPS（否则浏览器会拦截混合内容）。

### Nginx 示例

```nginx
server {
    listen 443 ssl;
    server_name chat.example.com;
    ssl_certificate     /etc/ssl/chat.example.com.pem;
    ssl_certificate_key /etc/ssl/chat.example.com.key;

    client_max_body_size 25m;   # 知识库上传文件

    location / {
        proxy_pass http://127.0.0.1:11999;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Caddy 示例（自动 HTTPS）

```caddy
chat.example.com {
    reverse_proxy 127.0.0.1:11999
}
```

对应嵌入代码：

```html
<script src="https://chat.example.com/widget/leadchat.min.js"
        data-api="https://chat.example.com"></script>
```

## 数据备份

所有运行时数据都在 `data/` 目录（默认挂载到宿主机 `./data`）：

```
data/
├── db/        # SQLite 数据库（对话、消息、采集数据、配置）
├── chroma/    # 向量库
└── uploads/   # 上传的原始文档
```

备份整站只需：

```bash
tar czf leadchat-backup-$(date +%F).tar.gz data/
```

如使用 PostgreSQL，请使用 `pg_dump` 备份数据库。

## 常见问题

### 1. Ollama 在 Docker 中连不上

容器内 `localhost` 指向容器自身。在后台「模型管理」编辑该模型时，把 API 端点填为：

```
http://host.docker.internal:11434
```

Linux 宿主机需在 `docker-compose.yml` 中追加：

```yaml
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

### 2. 首次上传文档报 embedding 下载失败

Embedding 使用内置本地模型（all-MiniLM-L6-v2，约 87MB，已打入镜像），正常情况下离线可用、无需下载。
如自行精简过镜像或缓存卷异常，可检查容器内 `/root/.cache/chroma/onnx_models` 是否存在，或重新使用官方镜像构建。

### 3. 挂件显示了但发消息报"网络异常"

- 检查 `data-api` 地址是否可从访客浏览器访问（不能用 localhost）
- 在后台「模型管理」点「测试」，检查模型配置与 API Key
- `docker compose logs` 查看后端报错
- HTTPS 网站必须使用 HTTPS 的 `data-api`（见上文反向代理）

### 4. 如何切换到 PostgreSQL

```env
DATABASE_URL=postgresql+asyncpg://user:password@db-host:5432/leadchat
```

数据表会在启动时自动创建。
