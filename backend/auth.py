"""Supabase JWT verification for FastAPI dependencies."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Header, HTTPException
from jose import JWTError, jwk, jwt
from jose.exceptions import ExpiredSignatureError

# Project root `.env` only (single source of truth for secrets).
_REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_REPO_ROOT / ".env")

_JWKS_CACHE: dict | None = None
_JWKS_FETCHED_AT = 0.0
_JWKS_TTL_SECONDS = 3600
_JWKS_ALGORITHMS = frozenset({"ES256", "RS256"})


def _supabase_url() -> str:
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    if not url:
        raise HTTPException(
            status_code=401,
            detail="SUPABASE_URL required in .env for JWT verification",
        )
    return url


def _fetch_jwks() -> dict:
    jwks_url = f"{_supabase_url()}/auth/v1/.well-known/jwks.json"
    try:
        with urllib.request.urlopen(jwks_url, timeout=10) as response:
            return json.loads(response.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Could not load Supabase JWKS for token verification",
        ) from exc


def _get_jwks(*, force_refresh: bool = False) -> dict:
    global _JWKS_CACHE, _JWKS_FETCHED_AT

    now = time.time()
    if (
        not force_refresh
        and _JWKS_CACHE is not None
        and now - _JWKS_FETCHED_AT < _JWKS_TTL_SECONDS
    ):
        return _JWKS_CACHE

    _JWKS_CACHE = _fetch_jwks()
    _JWKS_FETCHED_AT = now
    return _JWKS_CACHE


def _find_jwk(jwks: dict, kid: str | None) -> dict | None:
    keys = jwks.get("keys") or []
    if not isinstance(keys, list):
        return None
    if kid:
        for entry in keys:
            if isinstance(entry, dict) and entry.get("kid") == kid:
                return entry
    if len(keys) == 1 and isinstance(keys[0], dict):
        return keys[0]
    return None


def _decode_with_jwks(token: str, alg: str) -> dict:
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    jwks = _get_jwks()
    jwk_data = _find_jwk(jwks, kid if isinstance(kid, str) else None)
    if jwk_data is None:
        jwks = _get_jwks(force_refresh=True)
        jwk_data = _find_jwk(jwks, kid if isinstance(kid, str) else None)
    if jwk_data is None:
        raise JWTError("No matching signing key in Supabase JWKS")

    public_key = jwk.construct(jwk_data)
    return jwt.decode(
        token,
        public_key,
        algorithms=[alg],
        options={"verify_aud": False},
    )


def _decode_with_legacy_secret(token: str) -> dict:
    secret = (os.getenv("SUPABASE_JWT_SECRET") or "").strip()
    if not secret:
        raise HTTPException(
            status_code=401,
            detail=(
                "HS256 token requires SUPABASE_JWT_SECRET (legacy JWT secret). "
                "User session tokens use ES256 — set SUPABASE_URL instead."
            ),
        )
    return jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )


def _decode_supabase_token(token: str) -> dict:
    """Verify Supabase access token (ES256 via JWKS, or legacy HS256)."""
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Malformed access token") from exc

    alg = header.get("alg")
    if isinstance(alg, str) and alg in _JWKS_ALGORITHMS:
        return _decode_with_jwks(token, alg)
    if alg == "HS256":
        return _decode_with_legacy_secret(token)

    raise HTTPException(
        status_code=401,
        detail=f"Unsupported JWT algorithm: {alg!r}",
    )


def get_current_user_id(authorization: str | None = Header(default=None)) -> str:
    """Decode Supabase access token and return the user id (`sub` claim).

    Returns:
        Supabase user UUID from JWT `sub`.

    Raises:
        HTTPException: 401 if the header, token, or configuration is invalid.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    token = parts[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    try:
        payload = _decode_supabase_token(token)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token expired. Sign in again or refresh the page.",
        ) from None
    except HTTPException:
        raise
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail=(
                "Invalid access token. Ensure SUPABASE_URL matches VITE_SUPABASE_URL "
                "and sign in again after backend restart."
            ),
        ) from None

    sub = payload.get("sub")
    if not sub or not isinstance(sub, str) or not sub.strip():
        raise HTTPException(status_code=401, detail="Invalid token payload")

    return sub


class AuthenticatedUser:
    """Minimal user object for optional auth dependencies."""

    def __init__(self, user_id: str) -> None:
        self.id = user_id


async def get_current_user_optional(
    authorization: str | None = Header(default=None),
) -> AuthenticatedUser | None:
    """Returns None instead of raising 401 when no valid JWT is present."""
    if not authorization:
        return None
    try:
        return AuthenticatedUser(get_current_user_id(authorization))
    except HTTPException:
        return None
    except Exception:
        return None
