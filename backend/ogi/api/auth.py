"""JWT authentication dependency for FastAPI routes.

When Supabase is configured (supabase_jwt_secret is set), requests must carry
a valid ``Authorization: Bearer <token>`` header.  The JWT is validated with
the Supabase JWT secret and the ``sub`` claim is used as the user id.

When running in local/SQLite mode without Supabase credentials, auth is
bypassed and an anonymous user profile is returned so existing workflows are
unaffected.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import Request, HTTPException

from ogi.config import settings
from ogi.models import UserProfile

# A fixed anonymous profile returned when auth is disabled (local dev)
_ANON_USER = UserProfile(
    id=UUID("00000000-0000-0000-0000-000000000000"),
    email="local@localhost",
    display_name="Local User",
)


def _decode_jwt(token: str) -> dict[str, object]:
    """Decode and verify a Supabase-issued JWT."""
    from jose import jwt, JWTError

    try:
        payload: dict[str, object] = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc


async def get_current_user(request: Request) -> UserProfile:
    """FastAPI dependency: extract the authenticated user from the request.

    If Supabase JWT secret is not configured (local dev mode), returns a
    fixed anonymous profile.
    """
    if not settings.supabase_jwt_secret:
        return _ANON_USER

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty token")

    payload = _decode_jwt(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing sub claim")

    return UserProfile(
        id=UUID(str(user_id)),
        email=str(payload.get("email", "")),
    )


async def get_optional_user(request: Request) -> UserProfile | None:
    """Like ``get_current_user`` but returns ``None`` instead of raising."""
    try:
        return await get_current_user(request)
    except HTTPException:
        return None
