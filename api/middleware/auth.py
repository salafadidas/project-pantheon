"""
API-key authentication middleware for Pantheon.

S1-AUTH-2: Validates requests to /api/v1/* endpoints against the
``api_keys`` table (SHA-256 hash comparison).

Design constraints (Sprint 1):
- Hash comparison only — no scopes, no last_used_at, no rate limiting
  (deferred to Sprint 2+, per 001_auth_schema.sql header).
- Telegram adapter bypasses this middleware (it communicates via internal
  AgentManager, not the HTTP API).
- /api/v1/health is exempt (liveness probe).

Usage:
    app.add_middleware(APIKeyMiddleware, pool=pg_pool)
"""
from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

# Routes that bypass auth entirely.
_EXEMPT_PREFIXES = (
    "/api/v1/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)


def _hash_key(raw_key: str) -> str:
    """Return SHA-256 hex digest of the raw API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def _lookup_key(pool: "AsyncConnectionPool", key_hash: str) -> bool:
    """Return True if *key_hash* exists in the api_keys table."""
    try:
        async with pool.connection() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM api_keys WHERE key_hash = $1 LIMIT 1",
                key_hash,
            )
            return row is not None
    except Exception as exc:
        logger.error("api_key lookup failed: %s", exc)
        return False


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that enforces API-key auth on /api/v1/* routes.

    Reads the key from the ``X-API-Key`` header.  Requests missing the
    header, or whose key hash is not in ``api_keys``, receive a 401 response.

    Exempt routes (health probe, docs) bypass the check unconditionally.
    """

    def __init__(self, app, pool: "AsyncConnectionPool") -> None:
        super().__init__(app)
        self._pool = pool

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Exempt: health, docs, non-API paths
        if not path.startswith("/api/v1/") or any(
            path.startswith(p) for p in _EXEMPT_PREFIXES
        ):
            return await call_next(request)

        raw_key = request.headers.get("X-API-Key", "").strip()
        if not raw_key:
            logger.warning("auth: missing X-API-Key header path=%s", path)
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing X-API-Key header"},
            )

        key_hash = _hash_key(raw_key)
        valid = await _lookup_key(self._pool, key_hash)
        if not valid:
            logger.warning("auth: invalid API key path=%s hash_prefix=%s", path, key_hash[:8])
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid API key"},
            )

        logger.debug("auth: accepted path=%s hash_prefix=%s", path, key_hash[:8])
        return await call_next(request)
