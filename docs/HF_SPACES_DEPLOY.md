# Deploying to a free Hugging Face Docker Space

The root `Dockerfile` runs n8n (port `7860`) and the FastAPI cognitive engine
(`127.0.0.1:8500`) under supervisord in one container — Spaces expose exactly one port.

## 1. Provision Postgres (Supabase free tier)

Spaces filesystems are ephemeral, so SQLite would be wiped on every restart/rebuild.

1. Create a Supabase project → **Project Settings → Database → Connection pooling**.
2. Run `db/schema.sql` in the SQL editor.
3. Note host (`aws-0-<region>.pooler.supabase.com`), port `6543`, user `postgres.<ref>`, password.

## 2. Create the Space

```bash
pip install -U huggingface_hub
huggingface-cli login
huggingface-cli repo create cyber-orchestrator --type space --space_sdk docker

git remote add space https://huggingface.co/spaces/<user>/cyber-orchestrator
git push space HEAD:main
```

Prepend the Space README front matter (or create `README.md` in the Space) with:

```yaml
---
title: Cyber Orchestrator
sdk: docker
app_port: 7860
---
```

## 3. Space secrets and variables

**Settings → Variables and secrets** (secrets for tokens, variables for the rest):

| Key | Type | Value |
| --- | --- | --- |
| `HF_TOKEN` | secret | HF token with Inference permission |
| `TELEGRAM_BOT_TOKEN` | secret | BotFather token |
| `N8N_ENCRYPTION_KEY` | secret | any ≥32-char random string (keep it stable, credentials are encrypted with it) |
| `SERVICE_TOKEN` | secret | shared token between n8n and FastAPI |
| `DB_POSTGRESDB_PASSWORD` | secret | Supabase password |
| `DB_TYPE` | variable | `postgresdb` |
| `DB_POSTGRESDB_HOST` | variable | Supabase pooler host |
| `DB_POSTGRESDB_PORT` | variable | `6543` |
| `DB_POSTGRESDB_USER` | variable | `postgres.<project-ref>` |
| `DB_POSTGRESDB_DATABASE` | variable | `postgres` |
| `DB_POSTGRESDB_SSL_ENABLED` | variable | `true` |
| `DB_POSTGRESDB_SSL_REJECT_UNAUTHORIZED` | variable | `false` |
| `COGNITIVE_BASE_URL` | variable | `http://127.0.0.1:8500` |
| `TELEGRAM_SUPERGROUP_ID`, `TOPIC_AI`, `TOPIC_HACK`, `TOPIC_REDPILL` | variables | from local testing |
| `N8N_HOST` | variable | `<user>-cyber-orchestrator.hf.space` |
| `WEBHOOK_URL` | variable | `https://<user>-cyber-orchestrator.hf.space/` |
| `N8N_EDITOR_BASE_URL` | variable | same as `WEBHOOK_URL` |
| `N8N_SECURE_COOKIE` | variable | `true` |
| `GENERIC_TIMEZONE` | variable | e.g. `Asia/Tehran` |

## 4. First boot

1. Watch the build logs until `n8n ready on 0.0.0.0, port 7860`.
2. Open the Space URL, create the n8n owner account (persisted in Postgres).
3. Re-create the Postgres credential and re-import the workflows from `n8n_workflows/`
   (or copy them from your local instance), then activate 01–04 and 06.

## 5. Free-tier realities

- **Sleep:** free Spaces pause after ~48h without traffic; schedule triggers stop while paused.
  Pinging the Space URL every few minutes (e.g. UptimeRobot) keeps it awake.
- **Ephemeral disk:** only `/data/chroma` and `/home/user/.n8n` runtime files are local; anything
  you care about must be in Postgres. Re-seed the vector store from the `ideas` table if needed.
- **2 vCPU / 16 GB:** n8n + uvicorn fit comfortably because all inference is remote.
- **Rate limits:** HF serverless inference is credit-limited per account; the editorial workflow
  batches 5 items per run — lower it if you hit 429s.
- **Secrets:** never bake tokens into the image; they are injected as env vars at runtime.
