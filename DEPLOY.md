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
railway variables set WHATSAPP_APP_SECRET="your-secret"
railway variables set BACKEND_URL="http://localhost:8000"

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
│  Railway: frontend service              │
│  nginx :PORT (static files)             │
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
