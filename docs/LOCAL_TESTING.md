# Local end-to-end testing

Everything below runs on your machine with Docker Compose before you touch Hugging Face.

## 0. Prerequisites

- Docker + Docker Compose v2
- A Hugging Face token with Inference permissions (`HF_TOKEN`)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A Telegram **supergroup with Topics enabled**, bot added as admin

### Get the group id and topic ids

1. Post any message in the group, then open:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
2. `result[].message.chat.id` is `TELEGRAM_SUPERGROUP_ID` (starts with `-100`).
3. Post one message inside each topic (AI, Hack/Jailbreaks, Red Pill Vault) and read
   `message.message_thread_id` → `TOPIC_AI`, `TOPIC_HACK`, `TOPIC_REDPILL`.
4. Make sure no webhook is registered, otherwise `getUpdates` returns 409:
   `curl "https://api.telegram.org/bot<TOKEN>/deleteWebhook?drop_pending_updates=false"`

## 1. Configure and boot

```bash
cp .env.example .env
$EDITOR .env            # HF_TOKEN, TELEGRAM_*, SERVICE_TOKEN, N8N_ENCRYPTION_KEY
docker compose up -d --build
docker compose ps       # postgres healthy, cognitive + n8n running
```

`db/schema.sql` is applied automatically on first Postgres boot. To re-apply manually:

```bash
docker compose exec -T postgres psql -U n8n -d n8n < db/schema.sql
```

## 2. Smoke-test the cognitive engine (no n8n involved)

```bash
curl -s localhost:8500/health

curl -s -X POST localhost:8500/ideas \
  -H 'Content-Type: application/json' -H "X-Service-Token: $SERVICE_TOKEN" \
  -d '{"text":"ایده: یک ربات که لاگ‌های فایروال را با LLM تحلیل کند","user_id":"1"}'

curl -s -X POST localhost:8500/collide \
  -H 'Content-Type: application/json' -H "X-Service-Token: $SERVICE_TOKEN" \
  -d '{"title":"New LLM-powered firewall log triage tool released","summary":"...","url":"https://example.com/x"}'

curl -s -X POST localhost:8500/butterfly \
  -H 'Content-Type: application/json' -H "X-Service-Token: $SERVICE_TOKEN" \
  -d '{"title":"Critical RCE in a popular VPN appliance","url":"https://example.com/y"}'
```

Expected: Persian output, emoji-heavy, and **no** «حاجی»/«داداش». A 502 means `HF_TOKEN` is
missing/invalid or the model is cold — retry once.

## 3. Import the workflows into n8n

1. Open <http://localhost:7860> and create the owner account.
2. **Credentials → New → Postgres**: host `postgres`, port `5432`, db/user/password from `.env`.
   (For Supabase later: the pooler host, port `6543`, SSL on.)
3. **Workflows → Import from File** for each file in `n8n_workflows/` (01 → 06).
4. In every Postgres node, pick the credential you created (the JSON ships a
   `REPLACE_WITH_POSTGRES_CREDENTIAL_ID` placeholder).
5. Open workflow 02 → node **Handle button press** → select workflow **05** in the dropdown.

## 4. Walk the pipeline manually (in order)

| Step | Action | Expected |
| --- | --- | --- |
| 1 | Workflow 01 → *Execute workflow* | rows in `news_items` with `status='new'`; a second run inserts no duplicates (upsert on `url`) |
| 2 | Workflow 03 → *Execute workflow* | up to 5 rows move to `status='edited'` with a Persian `article` |
| 3 | Workflow 04 → *Execute workflow* | messages land in the right forum topic with the three inline buttons; long articles arrive as `(1/2)`, `(2/2)` |
| 4 | Tap 🔥 / 💤 in Telegram, then workflow 02 → *Execute workflow* | toast appears; a row in `reactions`; `category_prefs.ignore_streak` increments on 💤 and resets on 🔥 |
| 5 | Tap 💊 and run workflow 02 again | workflow 05 executes and posts the deep-dive report into the Red Pill Vault topic |
| 6 | Send a text or voice message to the bot, run 02 | idea stored (`curl localhost:8500/health` count grows; voice also returns a transcript) |
| 7 | Tap 💤 three times on the same category, then workflow 06 → *Execute workflow* | the "reduce frequency" suggestion message with its two buttons |

Useful queries:

```bash
docker compose exec postgres psql -U n8n -d n8n -c \
  "select status, count(*) from news_items group by 1;"
docker compose exec postgres psql -U n8n -d n8n -c \
  "select * from category_prefs;"
docker compose exec postgres psql -U n8n -d n8n -c "select * from telegram_offset;"
```

## 5. Turn it autonomous

Activate workflows 01–04 and 06 (05 is called by 02, so it only needs to be saved and active).
Watch **Executions** for failures; `saveDataErrorExecution: all` keeps failed runs for inspection.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `getUpdates` returns 409 | a webhook is registered — call `deleteWebhook` |
| the same updates repeat | the offset never advanced; check the *Advance offset* node and `telegram_offset` |
| `Bad Request: message thread not found` | wrong `TOPIC_*` id, or Topics not enabled in the group |
| `can't parse entities` | the model emitted invalid HTML — the article is HTML-mode; re-run the editorial node |
| `$env.HF_TOKEN` is empty in a node | env var not passed to the n8n container, or `N8N_BLOCK_ENV_ACCESS_IN_NODE=true` |
| HF 503 / model loading | serverless cold start; the HTTP node retries 3× — raise the timeout if needed |
