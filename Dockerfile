FROM python:3.11-slim

ARG APP_VERSION=0.6.0
LABEL org.opencontainers.image.title="LeadChat" \
      org.opencontainers.image.description="Open-source Web AI Assistant：一行代码嵌入任何 Web 系统，可配置多助手 + 知识库 RAG + 业务数据采集" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.licenses="AGPL-3.0-only"

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 先安装依赖，充分利用 Docker 缓存
# 国内构建可加速：docker compose build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_INDEX_URL=https://pypi.org/simple
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} -r /app/backend/requirements.txt

# 复制应用代码（VERSION 为后端版本号单一来源）
COPY VERSION /app/VERSION
COPY backend /app/backend
COPY widget/dist /app/widget/dist
COPY admin /app/admin

# 内置本地 Embedding 模型（约 87MB）：离线可用，首次上传知识库无需联网下载
# 挂载的 chroma_cache 命名卷在首次创建时会自动继承此目录内容
COPY docker/chroma-cache/onnx_models /root/.cache/chroma/onnx_models

# 创建运行时数据目录（也可通过 volume 挂载）
RUN mkdir -p /app/backend/data/db /app/backend/data/chroma /app/backend/data/uploads

WORKDIR /app/backend

EXPOSE 11999

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "11999"]
