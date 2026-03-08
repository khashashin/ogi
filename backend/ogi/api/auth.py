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

from supabase import create_client, Client

# A fixed anonymous profile returned when auth is disabled (local dev)
_ANON_USER = UserProfile(
    id=UUID("00000000-0000-0000-0000-000000000000"),
    email="local@localhost",
)

_supabase_client: Client | None = None

def get_supabase_client() -> Client | None:
    global _supabase_client
    if _supabase_client is None and settings.supabase_url and settings.supabase_anon_key:
        _supabase_client = create_client(settings.supabase_url, settings.supabase_anon_key)
    return _supabase_client

async def get_current_user(request: Request) -> UserProfile:
    """FastAPI dependency: extract and intensely verify the authenticated user.

    If Supabase credentials are not configured (local dev mode), returns a fixed anonymous profile.
    """
    if not settings.supabase_url or not settings.supabase_anon_key:
        return _ANON_USER

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty token")

    supabase = get_supabase_client()
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client missing configuration")

    try:
        # Ask Supabase Auth (GoTrue) to securely validate the JWT token.
        # This checks the signature, expiration, and revocation status natively.
        response = supabase.auth.get_user(token)
        if not response or not response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        user = response.user
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {exc}")

    return UserProfile(
        id=UUID(str(user.id)),
        email=str(user.email or ""),
    )

async def get_optional_user(request: Request) -> UserProfile | None:
    """Like ``get_current_user`` but returns ``None`` instead of raising."""
    try:
        return await get_current_user(request)
    except HTTPException:
        return None
