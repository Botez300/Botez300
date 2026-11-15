from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import Principal, audit, client_ip, current_principal, get_rate_limiter
from ..entitlements import PLANS
from ..models import Membership, Organization, User
from ..security import COOKIE_NAME, RateLimiter, create_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    display_name: str = Field(min_length=1, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


def _session(response: Response, user: User, org: Organization, role: str) -> dict:
    token, ttl = create_token(user.id, org.id)
    response.set_cookie(COOKIE_NAME, token, max_age=ttl, httponly=True, samesite="lax",
                        secure=get_settings().cookie_secure, path="/")
    return {"access_token": token, "token_type": "bearer", "expires_in": ttl, **_me(user, org, role)}


def _me(user: User, org: Organization, role: str) -> dict:
    return {"user": {"id": user.id, "email": user.email, "display_name": user.display_name},
            "organization": {"id": org.id, "name": org.name, "plan": org.plan,
                             "entitlements": PLANS.get(org.plan, PLANS["free"])},
            "role": role}


def _throttle(limiter: RateLimiter, request: Request, scope: str, email: str) -> None:
    s = get_settings()
    ip = client_ip(request)
    if not (limiter.allow(f"auth:ip:{ip}", s.login_attempts_per_window * 5, s.login_window_seconds)
            and limiter.allow(f"auth:{scope}:{ip}:{email}", s.login_attempts_per_window, s.login_window_seconds)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Try again in a few minutes.")


@router.post("/register", status_code=201)
def register(body: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db),
             limiter: RateLimiter = Depends(get_rate_limiter)) -> dict:
    email = body.email.strip().lower()
    _throttle(limiter, request, "register", email)
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(email=email, display_name=body.display_name.strip(), password_hash=hash_password(body.password))
    org = Organization(name=f"{user.display_name}'s workspace")
    db.add_all([user, org])
    try:
        db.flush()
        db.add(Membership(org_id=org.id, user_id=user.id, role="owner"))
        audit(db, "auth.register", request=request, target=user.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists") from None
    return _session(response, user, org, "owner")


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db),
          limiter: RateLimiter = Depends(get_rate_limiter)) -> dict:
    email = body.email.strip().lower()
    _throttle(limiter, request, "login", email)
    user = db.scalar(select(User).where(User.email == email))
    if not verify_password(body.password, user.password_hash if user else None) or user is None:
        audit(db, "auth.login_failed", request=request, detail={"email": email})
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    row = db.execute(
        select(Organization, Membership.role).join(Membership, Membership.org_id == Organization.id)
        .where(Membership.user_id == user.id).order_by(Membership.created_at)
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account does not belong to a workspace")
    audit(db, "auth.login", request=request, target=user.id)
    db.commit()
    return _session(response, user, row[0], row[1])


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me")
def me(principal: Principal = Depends(current_principal)) -> dict:
    return _me(principal.user, principal.org, principal.role)
