# Deploying to a free Hugging Face Docker Space

The root `Dockerfile` runs n8n (port `7860`) and the FastAPI cognitive engine
(`127.0.0.1:8500`) under supervisord in one container — a Space exposes exactly one port.

Order matters: **Postgres first, then secrets, then the git push.** The container crashes on
boot if `DB_POSTGRESDB_*` is missing, because `DB_TYPE=postgresdb` is baked into the image.

## 1. Provision Postgres (Supabase free tier)

Space filesystems are ephemeral, so SQLite would be wiped on every restart/rebuild.

1. Create a Supabase project.
2. **SQL Editor** → paste `db/schema.sql` → Run.
3. **Project Settings → Database → Connection pooling** (Transaction mode) and note:
   - host `aws-0-<region>.pooler.supabase.com`
   - port `6543`
   - user `postgres.<project-ref>`
   - the database password
4. Sanity check from your laptop:
   ```bash
   psql "postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require" -c '\dt'
   ```
   You should see `news_items`, `telegram_updates`, `telegram_offset`, `reactions`,
   `category_prefs`, `ideas`.

## 2. Create the Space

Hardware/template selections:

| Setting | Value |
| --- | --- |
| SDK / template | **Docker → Blank** (do not pick a Gradio/Streamlit template) |
| Hardware | **CPU basic · 2 vCPU · 16 GB — FREE** (all inference is remote; no GPU needed) |
| Persistent storage | none (free tier); durable state lives in Postgres |
| Visibility | **Private** — the n8n editor is reachable at the Space URL |
| App port | `7860` (set via `app_port` in the README front matter) |
| Sleep time | free Spaces pause after ~48h idle; see §5 |

CLI (`pip install -U huggingface_hub`, which ships the `hf` command):

```bash
hf auth login                                   # paste a token with write permission
hf repos create <user>/cyber-orchestrator --repo-type space --sdk docker --private
```

Or click **New Space** on the website and choose Docker → Blank → CPU basic (free).

## 3. Push the code

The Space is a separate git remote on huggingface.co; push the same branch you deployed
locally. Authenticate with an HF **write** token as the password (not your account password).

```bash
cd cyber-orchestrator
git remote add space https://huggingface.co/spaces/<user>/cyber-orchestrator
git push space main:main                        # username: <user>, password: <hf_write_token>
```

If the Space was created with a starter README, the first push is rejected as non-fast-forward:

```bash
git fetch space
git merge --allow-unrelated-histories space/main   # keep OUR README front matter
git push space main:main
```

Subsequent deploys are just `git push space main:main` — each push triggers a rebuild.

The Space reads its configuration from the YAML front matter at the top of `README.md`
(already committed):

```yaml
---
title: Cyber Orchestrator
emoji: 🕶️
colorFrom: gray
colorTo: red
sdk: docker
app_port: 7860
pinned: false
---
```

`app_port: 7860` is what makes the Space proxy traffic to n8n.

## 4. Space secrets and variables

**Settings → Variables and secrets.** Secrets are write-only and hidden from build logs;
variables are visible. Both arrive as environment variables, which is exactly what the n8n
nodes read (`{{ $env.HF_TOKEN }}`, `{{ $env.TELEGRAM_BOT_TOKEN }}`, …).

Secrets:

| Key | Value |
| --- | --- |
| `HF_TOKEN` | HF token with **Inference** permission (can be the same account as the Space) |
| `TELEGRAM_BOT_TOKEN` | BotFather token |
| `N8N_ENCRYPTION_KEY` | any ≥32-char random string — **never change it afterwards**, your saved n8n credentials are encrypted with it (`openssl rand -hex 24`) |
| `SERVICE_TOKEN` | shared secret between n8n and FastAPI (`openssl rand -hex 16`) |
| `DB_POSTGRESDB_PASSWORD` | Supabase database password |

Variables:

| Key | Value |
| --- | --- |
| `DB_TYPE` | `postgresdb` |
| `DB_POSTGRESDB_HOST` | `aws-0-<region>.pooler.supabase.com` |
| `DB_POSTGRESDB_PORT` | `6543` |
| `DB_POSTGRESDB_USER` | `postgres.<project-ref>` |
| `DB_POSTGRESDB_DATABASE` | `postgres` |
| `DB_POSTGRESDB_SCHEMA` | `public` |
| `DB_POSTGRESDB_SSL_ENABLED` | `true` |
| `DB_POSTGRESDB_SSL_REJECT_UNAUTHORIZED` | `false` |
| `COGNITIVE_BASE_URL` | `http://127.0.0.1:8500` |
| `HF_MODEL` | `meta-llama/Llama-3.3-70B-Instruct` |
| `HF_ROUTER_BASE` | `https://router.huggingface.co` |
| `HF_API_BASE` | `https://router.huggingface.co/v1` |
| `HF_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` |
| `TELEGRAM_SUPERGROUP_ID` | your supergroup id (`-100…`) |
| `TOPIC_AI` / `TOPIC_HACK` / `TOPIC_REDPILL` | forum topic ids |
| `N8N_HOST` | `<user>-cyber-orchestrator.hf.space` |
| `WEBHOOK_URL` | `https://<user>-cyber-orchestrator.hf.space/` |
| `N8N_EDITOR_BASE_URL` | same as `WEBHOOK_URL` |
| `N8N_PROXY_HOPS` | `1` (the Space sits behind a reverse proxy) |
| `N8N_SECURE_COOKIE` | `true` |
| `GENERIC_TIMEZONE` | `Asia/Tehran` |
| `CHROMA_PATH` | `/data/chroma` |

Already baked into the image (override only if you know why): `N8N_PORT=7860`,
`N8N_LISTEN_ADDRESS=0.0.0.0`, `N8N_USER_FOLDER=/home/user`, `FASTAPI_PORT=8500`.

## 5. First boot

1. **Logs** tab → wait for `Editor is now accessible via …` / `n8n ready on 0.0.0.0, port 7860`.
   `entrypoint.sh` prints an explicit warning first if any Postgres/HF variable is missing.
2. Open the Space URL and create the n8n owner account (stored in Postgres, so it survives rebuilds).
3. **Credentials → New → Postgres**: same pooler host/port/user/password, SSL on.
4. **Workflows → Import from File** for `n8n_workflows/01…06`, select the Postgres credential in
   every Postgres node, and in workflow 02 point **Handle button press** at workflow 05.
5. Run 01 → 03 → 04 manually once (same order as the local test) and confirm a message lands in
   the AI topic with the three inline buttons.
6. Activate 01, 02, 03, 04, 06. Workflow 05 is called by 02 — save it, no activation needed.

## 6. Free-tier realities

- **Sleep:** free Spaces pause after ~48h without traffic, and schedule triggers do not run while
  paused. Ping the Space URL every few minutes (UptimeRobot / cron-job.org) to keep it awake.
- **Rebuild = fresh disk:** only Postgres survives. `/data/chroma` is rebuilt from the `ideas`
  table if you re-seed it; n8n credentials survive because they live in Postgres (encrypted with
  `N8N_ENCRYPTION_KEY` — losing that key means re-entering every credential).
- **2 vCPU / 16 GB:** n8n + uvicorn fit comfortably since all inference is remote.
- **HF inference credits:** serverless usage is credit-limited per account; the editorial workflow
  processes 5 items per run — lower it if you hit 429s.
- **Telegram flood limits:** the publisher waits 2s between chunks; keep it.
- **Secrets:** never bake tokens into the image — they are injected as env vars at runtime.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Build ok, Space shows "Configuration error" | `app_port` missing from the README front matter |
| Container restarts in a loop, log says `ECONNREFUSED :5432` | `DB_POSTGRESDB_*` not set, or the direct (non-pooler) host was used |
| `self signed certificate in certificate chain` | set `DB_POSTGRESDB_SSL_REJECT_UNAUTHORIZED=false` |
| Login page loops / "Secure cookie" error | `WEBHOOK_URL`/`N8N_HOST` do not match the real Space URL |
| Every credential is suddenly invalid | `N8N_ENCRYPTION_KEY` changed |
| `not supported by any provider you have enabled` | model not enabled for your token — list options with `curl -H "Authorization: Bearer $HF_TOKEN" https://router.huggingface.co/v1/models` |
| Nothing happens on schedule | the Space is asleep — add an uptime ping |
