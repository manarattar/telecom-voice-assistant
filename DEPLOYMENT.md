# Deploying TelecomNL Voice Assistant

**Live at `voice.manarattar.com`.**

## How it is put together

FastAPI serves its own frontend — it mounts `/static` and returns
`static/index.html` at the root — so Caddy proxies the **whole host** rather
than serving files itself.

## Where this runs

Everything is on a single Contabo VPS. There is no Vercel, Render, or other
PaaS involved any more.

| | |
|---|---|
| Server | `194.163.176.183` — `ssh ubuntu@194.163.176.183` (key only, no password) |
| Stack | `/srv/stack/docker-compose.yml` + `/srv/stack/Caddyfile` |
| App sources | `/srv/apps/<name>` |
| Built static sites | `/srv/www/<name>` |
| Secrets | `/srv/stack/env/<name>.env` (0600, root-owned) |
| Database | one `postgres:18-alpine` container, internal network only |
| TLS | Caddy, automatic Let's Encrypt |
| Backups | nightly 03:17 to `/srv/backup/nightly`, 14-day rotation |

Caddy terminates TLS for every hostname and routes by host. Postgres has no
published port — it is reachable only on the internal Docker network.

## Secrets

Never commit them. Each app reads `/srv/stack/env/<name>.env` on the server,
which compose injects via `env_file`. `DATABASE_URL` is set by compose, not by
that file, so an app cannot accidentally point at an old database.

## Deploying a change

```bash
tar czf - --exclude=.env --exclude=__pycache__ --exclude=conversations . \
  | ssh ubuntu@194.163.176.183 'tar xzf - -C /srv/apps/telecom'
ssh ubuntu@194.163.176.183 'cd /srv/stack && sudo docker compose up -d --build telecom'
```

## Things that will catch you out

- The API is **same-origin**. `static/app.js` previously hardcoded a Render URL
  for any host that was not localhost or `*.onrender.com`, so the page rendered
  fine while every request went to a dead host. Keep `API_BASE = ''`.
- `app/config.py` still defaults `BACKEND_URL` to the old Render host. It is set
  explicitly in the env file; that default is a trap.
- The browser needs microphone access, so Caddy sends
  `Permissions-Policy: microphone=(self)` for this host only.
- `/docs`, `/redoc` and `/openapi.json` are blocked at Caddy — they were exposing
  the full API surface publicly.

## Rolling back

Rebuild from the previous commit and redeploy. There is no rollback to a
previous provider — the old Vercel and Render deployments were deleted in
September 2026. Database backups are on the server at
`/srv/backup/nightly` (nightly, 14-day rotation).
