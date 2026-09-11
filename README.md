---
title: Cyber Orchestrator
emoji: 🕶️
colorFrom: gray
colorTo: red
sdk: docker
app_port: 7860
pinned: false
---

# Autonomous Cyber Assistant — n8n + FastAPI (Hugging Face native)

An autonomous cyber/AI news orchestrator: n8n runs the workflows and Telegram I/O, a small
FastAPI service owns the ChromaDB vector memory, and all reasoning goes through the Hugging Face
Inference router. Designed to run locally with Docker Compose and to deploy unchanged to a free
Hugging Face Docker Space on port `7860`.

```
Telegram  ──getUpdates polling──►  n8n (port 7860)  ──HTTP──►  HF Inference router (LLM)
   ▲                                  │  │                      
   └────sendMessage / buttons─────────┘  └──HTTP──►  FastAPI cognitive engine (ChromaDB)
                                          │
                                          └──SQL──►  PostgreSQL (Supabase free tier)
```

## Layout

| Path | Purpose |
| --- | --- |
| `Dockerfile` | Single-container image for HF Spaces (supervisord: n8n on 7860 + FastAPI on 127.0.0.1:8500) |
| `docker-compose.yml` | Local stack: Postgres + FastAPI + n8n |
| `docker/` | `Dockerfile.fastapi`, `supervisord.conf`, `entrypoint.sh` |
| `fastapi_app/` | Cognitive engine: Idea Collider, Butterfly Effect, Red Pill RAG, voice transcription |
| `n8n_workflows/` | Importable workflow JSONs (01–06) |
| `db/schema.sql` | Postgres schema (news, telegram offset/updates, reactions, prefs, ideas) |
| `docs/` | [Local testing](docs/LOCAL_TESTING.md) · [HF Spaces deploy](docs/HF_SPACES_DEPLOY.md) |

## Workflows

| File | What it does |
| --- | --- |
| `01_ingestion_radar.json` | Schedule Trigger → RSS/GitHub Atom feeds → normalize → **Upsert** into `news_items` (dedup by `url`) |
| `02_telegram_polling.json` | Schedule Trigger → `getUpdates` via HTTP Request (**no webhooks**) → **Item Lists / Split Out Items** → Upsert by `update_id` → route text / voice / callback, with flood-wait delays and a persisted offset |
| `03_editorial_agent.json` | Persona prompt → HF chat completions → Butterfly Effect → Idea Collider → assembled Persian article |
| `04_telegram_publisher.json` | Routes to forum topics, splits >4096-char messages, attaches inline buttons |
| `05_redpill_rag.json` | Button sink: records reactions/ignore streaks, and on 💊 runs the deep-dive RAG report into the Red Pill Vault |
| `06_ghosting_algorithm.json` | After 3 consecutive ignores of a category, offers to reduce its frequency |

## Persona contract

The persona lives in two places that must stay in sync: `fastapi_app/persona.py` and the
`Build persona prompt` Code node in `03_editorial_agent.json`. Rules: Persian only; energetic
best-friend × paranoid white-hat tone; uses «پشمام» naturally; heavy emoji; **never** «حاجی» or
«داداش» (also stripped post-generation in `sanitize()` and in the `Assemble article` node).

## Quick start (local)

```bash
cp .env.example .env          # fill HF_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_SUPERGROUP_ID, TOPIC_*
docker compose up -d --build
open http://localhost:7860    # n8n editor
```

Then follow [docs/LOCAL_TESTING.md](docs/LOCAL_TESTING.md) to import the workflows, create the
Postgres credential, and exercise the end-to-end flow. Deployment steps are in
[docs/HF_SPACES_DEPLOY.md](docs/HF_SPACES_DEPLOY.md).

## Cognitive engine API

| Endpoint | Body | Result |
| --- | --- | --- |
| `GET /health` | — | service status + stored idea count |
| `POST /ideas` | `{text, user_id, chat_id, source}` | stores a vectorized idea |
| `POST /ideas/search` | `{title, summary, top_k}` | nearest stored ideas |
| `POST /collide` | `{title, summary, url, category}` | Persian «برخورد ایده‌ها» section when a stored idea is within `COLLISION_THRESHOLD` |
| `POST /butterfly` | `{title, summary, url}` | 6–24 month dystopian ripple projection |
| `POST /redpill` | `{title, summary, url}` | long technical dark report |
| `POST /voice` | `{file_id, user_id, chat_id}` | downloads the Telegram voice note, transcribes it, stores it as an idea |

All endpoints except `/health` require the `X-Service-Token` header when `SERVICE_TOKEN` is set.

## Notes / limits

- HF Spaces storage is ephemeral: durable state must live in Postgres. ChromaDB under
  `CHROMA_PATH` is a cache — `db/schema.sql` keeps an `ideas` mirror so it can be rebuilt.
- n8n Code/HTTP nodes read `$env.*`; keep `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` (the default).
- Telegram limits: 4096 chars/message (handled in the chunking Code nodes) and ~1 msg/s per chat
  (handled by the Wait nodes).
- Free Spaces sleep when idle, which pauses the schedule triggers; the offset in
  `telegram_offset` means polling resumes without losing updates (Telegram retains ~24h).
