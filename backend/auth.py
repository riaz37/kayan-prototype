"""
Authentication, roles and permissions for the Kayan console.

- Passwords: scrypt (Python standard library) with a per-user salt — no extra dependency.
- Sessions: opaque random token in an httpOnly cookie; only its SHA-256 hash is stored,
  so a leaked database row cannot be replayed as a session.
- Authorisation: a role grants a default set of permissions; an admin can grant or
  revoke individual permissions per user on top of that role.
- The WhatsApp agent authenticates with a service key instead of a session.
"""
import hashlib
import hmac
import json
import os
import secrets
from datetime import timedelta
from typing import Optional

from fastapi import Cookie, Depends, Header, HTTPException, Response

from backend import store as db

SESSION_COOKIE = "kayan_session"
SESSION_DAYS = 14
_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32}


# ---------------------------------------------------------------- permissions
class P:
    """Permission keys. `*:view` are read-only, the rest allow changes."""
    TICKETS_VIEW = "tickets:view"
    TICKETS_MANAGE = "tickets:manage"          # reply, move, assign, close
    BENEFICIARIES_VIEW = "beneficiaries:view"
    BENEFICIARIES_MANAGE = "beneficiaries:manage"  # create and edit files
    BENEFICIARIES_REVIEW = "beneficiaries:review"  # approve / reject a file
    REQUESTS_VIEW = "requests:view"
    CASEWORK_MANAGE = "casework:manage"        # open case, schedule, findings, send to committee
    COMMITTEE_DECIDE = "committee:decide"      # accept / docs required / decline
    FINANCE_VIEW = "finance:view"
    FINANCE_MANAGE = "finance:manage"          # enroll, approve, pay
    AGENT_TEST = "agent:test"
    REQUESTS_CREATE = "requests:create"        # raise a support request / add details
    STAFF_MANAGE = "staff:manage"              # user accounts and roles
    ADMIN = "admin:all"


ALL_PERMISSIONS = [v for k, v in vars(P).items() if not k.startswith("_") and isinstance(v, str)]

# Everyone signed in can read the operational data (agreed access model:
# actions are restricted by role, the data itself is visible to all staff).
BASE_VIEW = [P.TICKETS_VIEW, P.BENEFICIARIES_VIEW, P.REQUESTS_VIEW, P.FINANCE_VIEW]

ROLES: dict[str, dict] = {
    "admin": {"name_ar": "مدير النظام", "name_en": "System admin",
              "permissions": ALL_PERMISSIONS},
    "services": {"name_ar": "خدمات المستفيدين", "name_en": "Beneficiary services",
                 "permissions": BASE_VIEW + [P.TICKETS_MANAGE, P.BENEFICIARIES_MANAGE, P.BENEFICIARIES_REVIEW,
                                            P.REQUESTS_CREATE, P.AGENT_TEST]},
    "caseworker": {"name_ar": "باحث اجتماعي", "name_en": "Case worker",
                   "permissions": BASE_VIEW + [P.CASEWORK_MANAGE, P.REQUESTS_CREATE, P.TICKETS_MANAGE]},
    "committee": {"name_ar": "عضو اللجنة المختصة", "name_en": "Committee member",
                  "permissions": BASE_VIEW + [P.COMMITTEE_DECIDE]},
    "finance": {"name_ar": "الشؤون المالية", "name_en": "Finance",
                "permissions": BASE_VIEW + [P.FINANCE_MANAGE]},
}
DEFAULT_ROLE = "services"


def role_permissions(role: str) -> list[str]:
    return list(ROLES.get(role, {}).get("permissions", BASE_VIEW))


def effective_permissions(user: dict) -> list[str]:
    """Role defaults, plus admin-granted extras, minus admin-revoked ones."""
    perms = set(role_permissions(user.get("role", DEFAULT_ROLE)))
    perms |= set(_as_list(user.get("extra_permissions")))
    perms -= set(_as_list(user.get("revoked_permissions")))
    if P.ADMIN in perms:
        perms = set(ALL_PERMISSIONS)
    return sorted(perms)


def _as_list(value) -> list[str]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except ValueError:
            return []
    return []


# ---------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    if len(password or "") < 8:
        raise HTTPException(422, "Password must be at least 8 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${_SCRYPT['n']}${_SCRYPT['r']}${_SCRYPT['p']}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: Optional[str]) -> bool:
    try:
        algo, n, r, p, salt_hex, digest_hex = (stored or "").split("$")
        if algo != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex),
                                n=int(n), r=int(r), p=int(p), dklen=len(digest_hex) // 2)
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


# ---------------------------------------------------------------- sessions
def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(user_id: str, response: Response, secure: bool) -> str:
    token = secrets.token_urlsafe(32)
    expires = db.now() + timedelta(days=SESSION_DAYS)
    db.insert_session(_token_hash(token), user_id, expires.isoformat() + "Z")
    response.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_DAYS * 24 * 3600, httponly=True,
        samesite="lax", secure=secure, path="/",
    )
    return token


def end_session(token: Optional[str], response: Response) -> None:
    if token:
        db.delete_session(_token_hash(token))
    response.delete_cookie(SESSION_COOKIE, path="/")


def user_for_token(token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    user = db.user_for_session(_token_hash(token), db.now_iso())
    if not user or not user.get("is_active", 1):
        return None
    return user


# ---------------------------------------------------------------- service key (WhatsApp agent)
AGENT_PERMISSIONS = [
    P.TICKETS_VIEW, P.TICKETS_MANAGE, P.BENEFICIARIES_VIEW, P.BENEFICIARIES_MANAGE,
    P.REQUESTS_VIEW, P.REQUESTS_CREATE, P.FINANCE_VIEW,
]


def agent_key() -> str:
    return os.environ.get("AGENT_API_KEY", "").strip()


def _agent_principal() -> dict:
    return {"id": "agent", "name_ar": "الوكيل الذكي", "email": None, "role": "agent",
            "is_service": True, "permissions": AGENT_PERMISSIONS}


# ---------------------------------------------------------------- dependencies
def current_principal(
    kayan_session: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
    authorization: Optional[str] = Header(default=None),
    x_agent_key: Optional[str] = Header(default=None),
) -> Optional[dict]:
    """Session cookie, `Authorization: Bearer <session>`, or the agent service key."""
    key = agent_key()
    if key and x_agent_key and hmac.compare_digest(x_agent_key, key):
        return _agent_principal()
    token = kayan_session
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    user = user_for_token(token)
    if not user:
        return None
    return {**user, "is_service": False, "permissions": effective_permissions(user)}


def require_user(principal: Optional[dict] = Depends(current_principal)) -> dict:
    if not principal:
        raise HTTPException(401, "Sign in required")
    return principal


def require(*permissions: str):
    """Dependency factory: the caller must hold at least one of these permissions."""
    def dependency(principal: dict = Depends(require_user)) -> dict:
        held = set(principal.get("permissions", []))
        if P.ADMIN in held or held.intersection(permissions):
            return principal
        raise HTTPException(403, {"message": "You do not have permission for this action",
                                  "required": list(permissions)})
    return dependency


def public_user(user: dict) -> dict:
    """User record as returned by the API (never includes the password hash)."""
    return {
        "id": user["id"],
        "email": user.get("email"),
        "name_ar": user.get("name_ar"),
        "name_en": user.get("name_en"),
        "role": user.get("role"),
        "department_id": user.get("department_id"),
        "staff_id": user.get("staff_id"),
        "is_active": bool(user.get("is_active", 1)),
        "must_change_password": bool(user.get("must_change_password", 0)),
        "last_login_at": user.get("last_login_at"),
        "created_at": user.get("created_at"),
        "extra_permissions": _as_list(user.get("extra_permissions")),
        "revoked_permissions": _as_list(user.get("revoked_permissions")),
        "permissions": effective_permissions(user),
    }


# ---------------------------------------------------------------- request authorisation
import re as _re

# Paths anyone may call without signing in.
PUBLIC_PATHS = {"/health", "/", "/docs", "/redoc", "/openapi.json", "/favicon.ico",
                "/auth/login", "/auth/logout", "/webhook"}

# (methods, path regex, required permission). First match wins; unmatched paths need a
# signed-in user with any permission. Write operations must always match a rule here.
_RULES: list[tuple[set[str], str, str]] = [
    ("POST", r"^/admin/", P.ADMIN),
    ("*", r"^/staff/users", P.STAFF_MANAGE),
    ("*", r"^/agent/", P.AGENT_TEST),
    ("POST", r"^/beneficiary/[^/]+/review$", P.BENEFICIARIES_REVIEW),
    ("POST|PATCH", r"^/(registration|beneficiary)", P.BENEFICIARIES_MANAGE),
    ("POST|PATCH", r"^/crm/tickets", P.TICKETS_MANAGE),
    ("POST|PATCH", r"^/(whatsapp|voice)/", P.TICKETS_MANAGE),
    ("POST", r"^/support-requests/[^/]+/decision$", P.COMMITTEE_DECIDE),
    ("POST", r"^/(support-requests/[^/]+/open-case|cases/)", P.CASEWORK_MANAGE),
    ("POST|PATCH", r"^/support-requests", P.REQUESTS_CREATE),
    ("POST|PATCH", r"^/(enrollments|disbursements|payments|sponsorships)", P.FINANCE_MANAGE),
    ("POST|PATCH", r"^/events/", P.REQUESTS_CREATE),
]
_COMPILED = [(set(m.split("|")) if m != "*" else None, _re.compile(p), perm) for m, p, perm in _RULES]


def required_permission(method: str, path: str) -> str | None:
    for methods, pattern, perm in _COMPILED:
        if (methods is None or method.upper() in methods) and pattern.match(path):
            return perm
    return None


def is_public(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/static")


def principal_from_request(request) -> Optional[dict]:
    """Resolve the caller from the session cookie, bearer token, or agent key (for middleware)."""
    key = agent_key()
    header_key = request.headers.get("x-agent-key")
    if key and header_key and hmac.compare_digest(header_key, key):
        return _agent_principal()
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
    user = user_for_token(token)
    if not user:
        return None
    return {**user, "is_service": False, "permissions": effective_permissions(user)}


def has_permission(principal: dict, permission: str) -> bool:
    held = set(principal.get("permissions", []))
    return P.ADMIN in held or permission in held
