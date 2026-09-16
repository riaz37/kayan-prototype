"""
Sign-in and staff account management.

Sign-in:   POST /auth/login, POST /auth/logout, GET /auth/me, POST /auth/change-password
Staff:     GET/POST /staff/users, PATCH /staff/users/{id}, POST /staff/users/{id}/set-password
All staff endpoints require the staff:manage permission (admins hold it by default).
"""
import os
import secrets
import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
import re

from pydantic import BaseModel, Field, field_validator

from backend import auth, store as db

router = APIRouter()
T_AUTH = "auth"
T_STAFF = "staff"


def _secure_cookie(request: Request) -> bool:
    """Mark the session cookie Secure when the console is served over HTTPS."""
    forwarded = request.headers.get("x-forwarded-proto", "")
    return request.url.scheme == "https" or forwarded.split(",")[0].strip() == "https"


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def _check_email(value: str) -> str:
    value = (value or "").strip().lower()
    if not EMAIL_RE.match(value):
        raise ValueError("Enter a valid email address")
    return value


class LoginIn(BaseModel):
    email: str = Field(..., examples=["staff@kayan.org.sa"])
    password: str = Field(..., examples=["your-password"])

    _email = field_validator("email")(_check_email)


# ---- brute-force throttle: per email + client IP, in memory (single process)
_MAX_ATTEMPTS = 10
_WINDOW_SECONDS = 900
_attempts: dict[str, list[float]] = {}


def _throttle_key(email: str, request: Request) -> str:
    client = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "?")
    return f"{email.lower()}|{client}"


def _check_throttle(key: str) -> None:
    now = time.time()
    recent = [t for t in _attempts.get(key, []) if now - t < _WINDOW_SECONDS]
    _attempts[key] = recent
    if len(recent) >= _MAX_ATTEMPTS:
        raise HTTPException(429, "Too many sign-in attempts. Try again later.")


def _record_failure(key: str) -> None:
    _attempts.setdefault(key, []).append(time.time())


@router.post("/auth/login", tags=[T_AUTH], summary="Sign in", include_in_schema=True)
def login(body: LoginIn, request: Request, response: Response):
    throttle_key = _throttle_key(body.email, request)
    _check_throttle(throttle_key)
    user = db.user_by_email(body.email)
    # Same error and comparable timing whether the email exists or not.
    if not user or not auth.verify_password(body.password, user.get("password_hash")):
        auth.verify_password(body.password, auth.hash_password(secrets.token_urlsafe(16)))
        _record_failure(throttle_key)
        raise HTTPException(401, "Incorrect email or password")
    if not user.get("is_active", 1):
        raise HTTPException(403, "This account has been deactivated")
    _attempts.pop(throttle_key, None)
    auth.start_session(user["id"], response, _secure_cookie(request))
    db.update_row("users", user["id"], {"last_login_at": db.now_iso()})
    return {"user": auth.public_user({**user, "last_login_at": db.now_iso()})}


@router.post("/auth/logout", tags=[T_AUTH], summary="Sign out")
def logout(response: Response, kayan_session: Optional[str] = Cookie(default=None, alias=auth.SESSION_COOKIE)):
    auth.end_session(kayan_session, response)
    return {"status": "ok"}


@router.get("/auth/me", tags=[T_AUTH], summary="Current user and permissions")
def me(principal: dict = Depends(auth.require_user)):
    if principal.get("is_service"):
        return {"user": {"id": "agent", "role": "agent", "permissions": principal["permissions"]},
                "roles": auth.ROLES, "all_permissions": auth.ALL_PERMISSIONS}
    return {"user": auth.public_user(principal), "roles": auth.ROLES, "all_permissions": auth.ALL_PERMISSIONS}


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


@router.post("/auth/change-password", tags=[T_AUTH], summary="Change your own password")
def change_password(body: ChangePasswordIn, principal: dict = Depends(auth.require_user)):
    if principal.get("is_service"):
        raise HTTPException(403, "Service accounts cannot change a password")
    user = db.get_user(principal["id"])
    if not auth.verify_password(body.current_password, (user or {}).get("password_hash")):
        raise HTTPException(401, "Current password is incorrect")
    db.update_row("users", user["id"], {"password_hash": auth.hash_password(body.new_password),
                                        "must_change_password": 0, "updated_at": db.now_iso()})
    return {"status": "ok"}


# ---------------------------------------------------------------- staff accounts
class CreateUserIn(BaseModel):
    email: str
    password: str = Field(..., min_length=8)
    name_ar: str = Field(..., min_length=2)
    name_en: Optional[str] = None
    role: str = Field(auth.DEFAULT_ROLE, examples=list(auth.ROLES))
    department_id: Optional[str] = None
    staff_id: Optional[str] = None
    must_change_password: bool = True

    _email = field_validator("email")(_check_email)


class UpdateUserIn(BaseModel):
    name_ar: Optional[str] = None
    name_en: Optional[str] = None
    role: Optional[str] = None
    department_id: Optional[str] = None
    staff_id: Optional[str] = None
    is_active: Optional[bool] = None
    extra_permissions: Optional[List[str]] = None
    revoked_permissions: Optional[List[str]] = None


class SetPasswordIn(BaseModel):
    password: str = Field(..., min_length=8)
    must_change_password: bool = True


def _validate(role: Optional[str], extra: Optional[List[str]], revoked: Optional[List[str]]):
    if role is not None and role not in auth.ROLES:
        raise HTTPException(422, f"Unknown role. Valid roles: {sorted(auth.ROLES)}")
    for name, perms in (("extra_permissions", extra), ("revoked_permissions", revoked)):
        for perm in perms or []:
            if perm not in auth.ALL_PERMISSIONS:
                raise HTTPException(422, f"Unknown permission in {name}: {perm}")


@router.get("/staff/users", tags=[T_STAFF], summary="List staff accounts")
def list_users(_: dict = Depends(auth.require(auth.P.STAFF_MANAGE))):
    return {"count": db.count_users(), "users": [auth.public_user(u) for u in db.list_users()],
            "roles": auth.ROLES, "all_permissions": auth.ALL_PERMISSIONS}


@router.post("/staff/users", tags=[T_STAFF], summary="Create a staff account")
def create_user(body: CreateUserIn, _: dict = Depends(auth.require(auth.P.STAFF_MANAGE))):
    if db.user_by_email(body.email):
        raise HTTPException(409, "An account with this email already exists")
    _validate(body.role, None, None)
    user = db.insert_user({
        "id": f"USR-{uuid.uuid4().hex[:8].upper()}",
        "email": body.email, "password_hash": auth.hash_password(body.password),
        "name_ar": body.name_ar, "name_en": body.name_en, "role": body.role,
        "department_id": body.department_id, "staff_id": body.staff_id,
        "must_change_password": body.must_change_password,
    })
    return {"user": auth.public_user(user)}


@router.patch("/staff/users/{user_id}", tags=[T_STAFF], summary="Update a staff account")
def update_user(user_id: str, body: UpdateUserIn, principal: dict = Depends(auth.require(auth.P.STAFF_MANAGE))):
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    _validate(body.role, body.extra_permissions, body.revoked_permissions)
    fields = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "is_active" in fields:
        if user_id == principal["id"] and not fields["is_active"]:
            raise HTTPException(409, "You cannot deactivate your own account")
        fields["is_active"] = 1 if fields["is_active"] else 0
    if fields.get("role") and user_id == principal["id"] and fields["role"] != user["role"]:
        raise HTTPException(409, "You cannot change your own role")
    fields["updated_at"] = db.now_iso()
    db.update_row("users", user_id, fields)
    if fields.get("is_active") == 0:
        db.delete_sessions_for_user(user_id)  # sign the account out everywhere
    return {"user": auth.public_user(db.get_user(user_id))}


@router.post("/staff/users/{user_id}/set-password", tags=[T_STAFF], summary="Reset a staff password")
def set_password(user_id: str, body: SetPasswordIn, _: dict = Depends(auth.require(auth.P.STAFF_MANAGE))):
    if not db.get_user(user_id):
        raise HTTPException(404, "User not found")
    db.update_row("users", user_id, {"password_hash": auth.hash_password(body.password),
                                     "must_change_password": 1 if body.must_change_password else 0,
                                     "updated_at": db.now_iso()})
    db.delete_sessions_for_user(user_id)
    return {"status": "ok"}


# ---------------------------------------------------------------- bootstrap
def ensure_admin() -> Optional[str]:
    """Create the first admin from ADMIN_EMAIL / ADMIN_PASSWORD when no account exists yet."""
    if db.count_users():
        return None
    email = os.environ.get("ADMIN_EMAIL", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "").strip()
    if not email or not password:
        return None
    db.insert_user({
        "id": f"USR-{uuid.uuid4().hex[:8].upper()}", "email": email,
        "password_hash": auth.hash_password(password),
        "name_ar": os.environ.get("ADMIN_NAME", "مدير النظام"), "name_en": os.environ.get("ADMIN_NAME_EN", "System admin"),
        "role": "admin", "staff_id": "STF-01", "must_change_password": False,
    })
    return email
