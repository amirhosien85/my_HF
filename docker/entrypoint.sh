#!/usr/bin/env bash
set -euo pipefail

: "${N8N_PORT:=7860}"
: "${FASTAPI_PORT:=8500}"

if [[ "${DB_TYPE:-}" == "postgresdb" && -z "${DB_POSTGRESDB_HOST:-}" ]]; then
  echo "[entrypoint] DB_TYPE=postgresdb but DB_POSTGRESDB_HOST is empty." >&2
  echo "[entrypoint] Set the Supabase connection variables, or state will be lost on restart." >&2
fi

if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "[entrypoint] WARNING: HF_TOKEN is not set; the cognitive engine will return 500s." >&2
fi

mkdir -p "${CHROMA_PATH:-/data/chroma}"

exec supervisord -c /etc/supervisor/conf.d/orchestrator.conf
