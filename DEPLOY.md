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
railway variables set GEMINI_API_KEY="your-key"
railway variables set WHATSAPP_ACCESS_TOKEN="your-token"
railway variables set WHATSAPP_PHONE_NUMBER_ID="your-phone-id"
railway variables set WHATSAPP_VERIFY_TOKEN="kayan-verify-token"
railway variables set ADMIN_EMAIL="admin@kayan.org.sa"
railway variables set ADMIN_PASSWORD="a-long-password"
railway variables set AGENT_API_KEY="$(openssl rand -hex 32)"
railway variables set WHATSAPP_APP_SECRET="your-secret"
railway variables set BACKEND_URL="http://localhost:8000"

# Add persistent volume for SQLite
railway volume add -m /app/data

# Deploy
railway up
```

## Step 2: Deploy the console (Vercel)

The console is a Next.js app and is deployed on Vercel; Railway runs only the backend + agent.

1. **Import the repository** at vercel.com → New Project → pick this repo.
2. **Root Directory: `frontend`** (Vercel then detects Next.js automatically).
3. **Environment variables** (Production and Preview):

   | Variable | Value |
   |---|---|
   | `BACKEND_URL` | `https://<your-backend>.up.railway.app` |

   The browser only ever calls the console's own `/api`, which forwards to `BACKEND_URL`
   server-side. That keeps the session cookie first-party, so no CORS setup is needed.
4. **Deploy.** Every push to `main` deploys; pull requests get preview URLs.
5. On the backend, set `ALLOWED_ORIGINS` to your Vercel domain if you ever call the API
   directly from a browser (not needed for the console itself).

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
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Yes (first deploy) | Creates the first console admin while no account exists |
| `AGENT_API_KEY` | Yes | Shared service key: the WhatsApp agent authenticates to the API with it |
| `BACKEND_URL` | Yes (frontend service) | Backend URL the console's `/api` proxy forwards to |
| `ALLOWED_ORIGINS` | No | Comma-separated origins for direct browser calls (default `*`) |
| `LLM_API_KEY` | No | API key for the LLM endpoint (empty for local) |
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
│  │ Backend :PORT│  │ Agent :8001 │       │
│  └─────────────┘  └─────────────┘       │
│  Volume: /app/data (SQLite)             │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Vercel: console (Next.js)              │
│  /ar, /en  +  /api proxy → backend      │
└─────────────────────────────────────────┘
```

## Local Development

```bash
# Start all services locally
docker-compose up --build

# Or without Docker
./start.sh
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
- Check if all environment variables are set
- Verify GEMINI_API_KEY is valid

### SQLite database is empty
- Ensure volume is mounted to `/app/data`
- Check volume is persistent (not ephemeral)

### Frontend can't reach backend
- Verify BACKEND_URL points to the correct service
- Check backend service is healthy
