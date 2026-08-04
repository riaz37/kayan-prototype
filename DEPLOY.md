# Railway Deployment Guide

## Prerequisites

1. Install Railway CLI: `npm i -g @railway/cli`
2. Login: `railway login`
3. Create project: `railway init`

## Step 1: Deploy Backend + Agent

```bash
# From project root
railway service create backend-agent
railway service connect backend-agent

# Set environment variables
railway variables set LLM_BASE_URL="http://your-llm-host:9025"
railway variables set LLM_MODEL="qwen"
railway variables set WHATSAPP_ACCESS_TOKEN="your-token"
railway variables set WHATSAPP_PHONE_NUMBER_ID="your-phone-id"
railway variables set WHATSAPP_VERIFY_TOKEN="kayan-verify-token"
railway variables set WHATSAPP_APP_SECRET="your-secret"
railway variables set BACKEND_URL="http://127.0.0.1:8001"

# Add persistent volume for SQLite
railway volume add -m /app/data

# Deploy
railway up
```

## Step 2: Deploy Frontend

```bash
# Create frontend service
railway service create frontend
railway service connect frontend

# Set backend URL (use Railway internal URL)
railway variables set BACKEND_URL="https://backend-agent.up.railway.app"

# Deploy
railway up
```

## Step 3: Configure Domains

```bash
# Add public domain to frontend
railway domain

# Add public domain to backend (for webhooks)
railway domain
```

## Step 4: Update WhatsApp Webhook

In Meta Developer Console, update the webhook URL:
- **Webhook URL:** `https://backend-agent.up.railway.app/webhook`
- **Verify token:** `kayan-verify-token`

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_BASE_URL` | No | OpenAI-compatible LLM endpoint (default: the self-hosted vLLM) |
| `LLM_MODEL` | No | Model name at that endpoint (default `qwen`) |
| `LLM_API_KEY` | No | API key for the LLM endpoint (`none` for the local vLLM) |
| `LLM_ENABLE_THINKING` | No | `1` to keep the model's reasoning pass on (slower replies) |
| `DATA_DIR` | No | Where `kayan.db` lives; must match the mounted volume |
| `WHATSAPP_ACCESS_TOKEN` | Yes | Meta WhatsApp Cloud API token |
| `WHATSAPP_PHONE_NUMBER_ID` | Yes | WhatsApp business phone number ID |
| `WHATSAPP_VERIFY_TOKEN` | Yes | Webhook verification token |
| `WHATSAPP_APP_SECRET` | Yes | Meta app secret for webhook validation |
| `BACKEND_URL` | Yes | Backend URL (internal or external) |
| `PORT` | Auto | Set by Railway automatically |

## Architecture

```
┌─────────────────────────────────────────┐
│  Railway: backend-agent service         │
│  ┌─────────────┐  ┌─────────────┐       │
│  │ Backend :8001│  │ Agent :8002 │       │
│  └─────────────┘  └─────────────┘       │
│  Volume: /app/data (SQLite)             │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Railway: frontend service              │
│  nginx :PORT (static files)             │
└─────────────────────────────────────────┘
```

## Local Development

```bash
# Start all services locally
docker-compose up --build

# Or without Docker (venv, build, seed, serve)
./run.sh
```

## Logs

```bash
# View logs
railway logs

# Follow logs
railway logs --follow
```

## Troubleshooting

### Backend crashes on startup
- Check the volume is mounted at the path `DATA_DIR` points to
- `GET /health` should return `{"status":"ok"}` before the agent will work

### Agent replies with a technical-error message
- `GET /` on the agent reports the model and base URL it is actually using
- Confirm the LLM endpoint is reachable *from Railway*, not just from your laptop

### SQLite database is empty
- Ensure volume is mounted to `/app/data`
- Check volume is persistent (not ephemeral)
- Seed it once: `POST /admin/seed` (this wipes and regenerates the demo data)

### "no such column" errors after deploying
- Should not happen: `backend/store.py` migrates missing columns on startup.
- If it does, the column is missing from `_MIGRATIONS` — add it there rather
  than editing the database by hand, so every environment converges.

### Frontend can't reach backend
- Verify BACKEND_URL points to the correct service
- Check backend service is healthy
