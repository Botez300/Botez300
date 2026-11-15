from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from threading import Lock

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from .config import get_settings

_hasher = PasswordHasher()
# Verified against when the account does not exist, so both paths cost the same.
_DUMMY_HASH = _hasher.hash("legion-dummy-password")
ALGORITHM = "HS256"
COOKIE_NAME = "legion_session"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def create_token(user_id: str, org_id: str) -> tuple[str, int]:
    s = get_settings()
    now = datetime.now(UTC)
    ttl = s.access_token_minutes * 60
    payload = {"sub": user_id, "org": org_id, "iat": now, "exp": now + timedelta(seconds=ttl), "jti": uuid.uuid4().hex}
    return jwt.encode(payload, s.jwt_secret, algorithm=ALGORITHM), ttl


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM],
                          options={"require": ["sub", "org", "exp"]})
    except jwt.PyJWTError:
        return None


class RateLimiter:
    """Sliding-window limiter. Uses Redis when given a client (shared across replicas), else process memory."""

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window: int) -> bool:
        if self._redis is not None:
            try:
                k = f"rl:{key}"
                count = self._redis.incr(k)
                if count == 1:
                    self._redis.expire(k, window)
                return count <= limit
            except Exception:  # Redis unavailable: degrade to the local limiter rather than fail open
                pass
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
