# Deploying on a VPS (recommended for always-on operation)

Use this instead of a Hugging Face Space if you don't want a PRO subscription, or if you want a
scheduler that never sleeps. See `docs/HF_SPACES_DEPLOY.md` for the Spaces path and why it now
needs a paid plan.

Everything runs from the compose files already in the repo: `docker-compose.yml` plus
`docker-compose.prod.yml`, which adds Caddy (automatic Let's Encrypt HTTPS), drops the public
Postgres/FastAPI port mappings, and sets `restart: unless-stopped`.

## What you need

- A VPS with 1–2 vCPU and 2 GB RAM (Hetzner CX22, DigitalOcean, Vultr, Contabo — roughly $4–6/mo).
  All inference is remote, so this is a traffic-shuffling box, not a compute box.
- A DNS `A` record, e.g. `n8n.example.com`, pointing at the VPS IP (Caddy needs it for TLS).
- Ports 80 and 443 open.

Postgres runs in the compose stack here, so Supabase is optional. Keep Supabase instead if you
prefer managed backups — just point `DB_POSTGRESDB_*` at the pooler and remove the `postgres`
service from the command line.

## Steps

```bash
# 1. install Docker
curl -fsSL https://get.docker.com | sh

# 2. get the code
git clone https://github.com/amirhosien85/my_HF.git cyber-orchestrator
cd cyber-orchestrator

# 3. configure
cp .env.example .env
$EDITOR .env          # HF_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_SUPERGROUP_ID, TOPIC_*,
                      # N8N_ENCRYPTION_KEY, SERVICE_TOKEN, a strong DB_POSTGRESDB_PASSWORD,
                      # and N8N_HOST=n8n.example.com

# 4. launch
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 5. watch it come up
docker compose logs -f n8n
```

`db/schema.sql` is applied automatically on the first boot of the `postgres` volume.

Then open `https://n8n.example.com`, create the owner account, add the Postgres credential
(host `postgres`, port `5432`, the user/password from `.env`), import `n8n_workflows/01…06`,
point workflow 02's **Handle button press** at workflow 05, and activate 01–04 and 06.

## Operating it

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull   # update images
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# backup (do this before any upgrade — it holds your workflows and credentials)
docker compose exec -T postgres pg_dump -U n8n n8n | gzip > backup-$(date +%F).sql.gz
```

- Keep `N8N_ENCRYPTION_KEY` stable forever; it decrypts the stored credentials.
- The ChromaDB vector store lives in the `chroma_data` volume and can be rebuilt from the `ideas`
  table if lost.
- Don't publish the n8n port directly — the overlay deliberately removes `7860:7860`, `8500:8500`
  and `5432:5432` so only Caddy is reachable.

## Other managed hosts

| Host | Fit |
| --- | --- |
| Fly.io | good: `fly launch` on the root `Dockerfile`, set `internal_port = 7860`, add a Fly Postgres or keep Supabase. Free-ish allowance, machines can auto-stop — disable that or the schedule triggers pause. |
| Railway / Render | good: deploy from the repo Dockerfile, managed Postgres add-on, one env-var screen. Render's free web services sleep; use a paid instance for schedules. |
| Koyeb / Northflank | similar, both have a small always-on free tier. |
| Oracle Cloud Always Free | free ARM VM; the images are multi-arch, so the compose path above works unchanged. |

Whatever you pick, the requirements are the same: one container port (`7860`), an external
Postgres, and the same env vars listed in `docs/HF_SPACES_DEPLOY.md` §4.
