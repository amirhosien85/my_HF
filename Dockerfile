# Hugging Face Spaces (Docker SDK) image: n8n + FastAPI/ChromaDB in one container on port 7860.
FROM node:20-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv supervisor curl ca-certificates tini \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g n8n@1.72.1 && npm cache clean --force

# Hugging Face Spaces runs the container as uid 1000 with $HOME=/home/user.
RUN useradd -m -u 1000 user || true
ENV HOME=/home/user

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY fastapi_app/requirements.txt /app/fastapi_app/requirements.txt
RUN pip install --no-cache-dir -r /app/fastapi_app/requirements.txt

COPY fastapi_app /app/fastapi_app
COPY n8n_workflows /app/n8n_workflows
COPY db /app/db
COPY docker/supervisord.conf /etc/supervisor/conf.d/orchestrator.conf
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Writable, ephemeral state (Chroma cache + n8n runtime dir). Durable state lives in Postgres.
RUN mkdir -p /data/chroma /home/user/.n8n /var/log/orchestrator \
    && chown -R user:user /data /home/user /var/log/orchestrator /app

ENV N8N_PORT=7860 \
    N8N_LISTEN_ADDRESS=0.0.0.0 \
    N8N_PROTOCOL=https \
    N8N_USER_FOLDER=/home/user \
    N8N_DIAGNOSTICS_ENABLED=false \
    N8N_HIRING_BANNER_ENABLED=false \
    N8N_RUNNERS_ENABLED=true \
    DB_TYPE=postgresdb \
    FASTAPI_PORT=8500 \
    CHROMA_PATH=/data/chroma \
    GENERIC_TIMEZONE=Asia/Tehran \
    TZ=Asia/Tehran

USER user
WORKDIR /app
EXPOSE 7860

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/entrypoint.sh"]
