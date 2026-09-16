"""
Kayan Orphan Care Association — AI Agent Platform (PROTOTYPE)
=============================================================
A runnable mock of Kayan's beneficiary management platform, built so AI agents
on PHONE (SIP) and WHATSAPP can perform the full journey described in the
association's guide "رحلة المستفيد في نظام جمعية كيان":

  registration -> eligibility -> the 10-section file -> dependents -> documents
  -> financial profile -> support request (5 programs / 43 request types)
  -> case study (visit, interview, psychological assessment) -> committee
  -> decision + notification -> enrollment -> monthly disbursement -> payment

Plus the CRM seen in the client's admin screenshots: kanban ticket board,
SLA countdown, department routing, WhatsApp 24-hour session windows.

Every endpoint is designed to be registered as a TOOL in an AI agent builder.
Conversational endpoints return `reply_ar` — speech/print-ready Arabic.

ALL DATA IS SYNTHETIC. This is a simulation for agent testing, not the real
Kayan system and not a security-hardened service.

Run:  uvicorn backend.main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


from backend import auth, store as db
from backend.routers import accounts, beneficiary, crm, programs, finance

logger = logging.getLogger("kayan")


@asynccontextmanager
async def lifespan(_: FastAPI):
    created = accounts.ensure_admin()
    if created:
        logger.info("Created the first admin account: %s", created)
    elif not db.count_users():
        logger.warning("No staff accounts exist. Set ADMIN_EMAIL and ADMIN_PASSWORD, then restart.")
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Kayan Orphan Care — AI Agent Platform (Mock)",
    version="1.0.0",
    description=(
        "Prototype backend simulating جمعية كيان للايتام beneficiary management. "
        "Multi-channel (Voice/SIP + WhatsApp), Arabic-first. Each route is an agent tool."
    ),
)
# The console talks to this API through its own /api proxy, so credentials never cross origins.
_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_origins,
                   allow_credentials=_origins != ["*"], allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def authorize(request: Request, call_next):
    """Every endpoint needs a signed-in user (or the agent service key), except the
    public ones; write operations additionally need the permission for that area."""
    path = request.url.path
    if request.method == "OPTIONS" or auth.is_public(path):
        return await call_next(request)
    principal = auth.principal_from_request(request)
    if not principal:
        return JSONResponse(status_code=401, content={"detail": "Sign in required"})
    permission = auth.required_permission(request.method, path)
    if permission and not auth.has_permission(principal, permission):
        return JSONResponse(status_code=403,
                            content={"detail": "You do not have permission for this action",
                                     "required": permission})
    request.state.principal = principal
    return await call_next(request)





@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )

app.include_router(accounts.router)
app.include_router(beneficiary.router)
app.include_router(crm.router)
app.include_router(programs.router)
app.include_router(finance.router)


@app.get("/health", tags=["system"], summary="Health check")
def health():
    return {"status": "ok"}


@app.get("/api", tags=["system"], summary="Platform info")
def api_info():
    return {
        "platform": "Kayan Orphan Care — AI Agent Platform (mock)",
        "association": "جمعية كيان للايتام",
        "served_category": "الايتام ذوو الظروف الخاصة (مجهولو الابوين)",
        "channels": ["voice_sip", "whatsapp", "portal"],
        "languages": ["ar", "en"],
        "programs": [p["name_ar"] for p in db.programs],
        "counts": {
            "beneficiaries": len(db.beneficiaries), "dependents": len(db.dependents),
            "documents": len(db.documents), "support_requests": len(db.support_requests),
            "request_types": len(db.request_types), "tickets": len(db.tickets),
            "enrollments": len(db.enrollments), "disbursements": len(db.disbursements),
            "payments": len(db.payments), "sponsorships": len(db.sponsorships),
        },
        "contact": {"beneficiary_services_whatsapp": "0506094154",
                    "phone": ["0533155582", "0112925559"],
                    "site": "kayan.org.sa", "email": "info@kayan.org.sa"},
        "docs": "/docs", "openapi": "/openapi.json",
    }


# ---- proxy /agent/* to the agent server (port 8002)
import httpx

AGENT_URL = os.environ.get("AGENT_URL", "http://127.0.0.1:8002")

@app.api_route("/agent/{path:path}", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=False)
async def proxy_agent(path: str, request: Request):
    """Forward /agent/* requests to the agent server."""
    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}
    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method=request.method,
            url=f"{AGENT_URL}/agent/{path}",
            headers=headers,
            content=body,
            timeout=120,
        )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
    )


@app.api_route("/webhook", methods=["GET", "POST"], include_in_schema=False)
async def proxy_webhook(request: Request):
    """Forward /webhook to the agent server for Meta WhatsApp Cloud API."""
    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}
    
    # Build URL with query parameters
    url = f"{AGENT_URL}/webhook"
    if request.query_params:
        url += "?" + str(request.query_params)
    
    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
            timeout=30,
        )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
    )


@app.post("/admin/seed", tags=["admin"])
def admin_seed():
    import subprocess, sys
    r = subprocess.run([sys.executable, "backend/seed_production.py"], capture_output=True, text=True, timeout=120)
    if r.returncode == 0:
        db._warm_indices()
    return {"status": "ok" if r.returncode == 0 else "error", "output": r.stdout + r.stderr}


# ---- frontend served separately (Vercel / static host)
