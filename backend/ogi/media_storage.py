from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import httpx

from ogi.config import settings


@dataclass
class StoredMediaRef:
    backend: str
    path: str
    content_type: str


@dataclass
class MediaPayload:
    content: bytes
    content_type: str


def _safe_extension(filename: str | None, content_type: str | None) -> str:
    name_ext = Path(filename or "").suffix.lower()
    if name_ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}:
        return name_ext

    guessed = mimetypes.guess_extension(content_type or "")
    if guessed:
        return ".jpg" if guessed == ".jpe" else guessed
    return ".bin"


def _normalize_content_type(content_type: str | None, filename: str | None) -> str:
    provided = (content_type or "").strip().lower()
    if provided and provided != "application/octet-stream":
        return provided
    guessed, _ = mimetypes.guess_type(filename or "")
    return guessed or "application/octet-stream"


def _upload_to_supabase(
    *,
    project_id: UUID,
    entity_id: UUID,
    filename: str | None,
    content_type: str,
    content: bytes,
) -> StoredMediaRef | None:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return None

    try:
        from supabase import create_client

        client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        storage = client.storage
        normalized_content_type = _normalize_content_type(content_type, filename)
        ext = _safe_extension(filename, normalized_content_type)
        object_path = f"projects/{project_id}/entities/{entity_id}/{uuid4().hex}{ext}"
        storage.from_(settings.media_bucket_name).upload(
            object_path,
            content,
            {"content-type": normalized_content_type, "x-upsert": "true"},
        )
        return StoredMediaRef(
            backend="supabase",
            path=object_path,
            content_type=normalized_content_type,
        )
    except Exception:
        return None


def _store_local_media(
    *,
    project_id: UUID,
    entity_id: UUID,
    filename: str | None,
    content_type: str,
    content: bytes,
) -> StoredMediaRef:
    normalized_content_type = _normalize_content_type(content_type, filename)
    ext = _safe_extension(filename, normalized_content_type)
    rel_path = (
        Path("projects")
        / str(project_id)
        / "entities"
        / str(entity_id)
        / f"{uuid4().hex}{ext}"
    )
    abs_path = settings.abs_media_path / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(content)
    return StoredMediaRef(
        backend="local",
        path=rel_path.as_posix(),
        content_type=normalized_content_type,
    )


def store_person_visual_image(
    *,
    project_id: UUID,
    entity_id: UUID,
    filename: str | None,
    content_type: str,
    content: bytes,
) -> StoredMediaRef:
    supabase_ref = _upload_to_supabase(
        project_id=project_id,
        entity_id=entity_id,
        filename=filename,
        content_type=content_type,
        content=content,
    )
    if supabase_ref:
        return supabase_ref

    return _store_local_media(
        project_id=project_id,
        entity_id=entity_id,
        filename=filename,
        content_type=content_type,
        content=content,
    )


def load_local_media(path: str, *, content_type: str | None = None) -> MediaPayload:
    rel_path = Path(path)
    abs_path = (settings.abs_media_path / rel_path).resolve()
    media_root = settings.abs_media_path.resolve()
    if media_root not in abs_path.parents and abs_path != media_root:
        raise FileNotFoundError("Invalid media path")
    content = abs_path.read_bytes()
    resolved_type = _normalize_content_type(content_type, abs_path.name)
    return MediaPayload(content=content, content_type=resolved_type)


async def load_supabase_media(path: str, *, content_type: str | None = None) -> MediaPayload:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise FileNotFoundError("Supabase storage is not configured")

    from supabase import create_client

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    storage = client.storage.from_(settings.media_bucket_name)
    signed = storage.create_signed_url(path, 60)
    signed_url = None
    if isinstance(signed, str):
        signed_url = signed
    elif isinstance(signed, dict):
        signed_url = (
            signed.get("signedURL")
            or signed.get("signedUrl")
            or signed.get("signed_url")
        )
    if not signed_url:
        raise FileNotFoundError("Failed to create signed media URL")

    async with httpx.AsyncClient(timeout=30.0) as client_http:
        response = await client_http.get(signed_url)
        response.raise_for_status()
        resolved_type = _normalize_content_type(
            response.headers.get("content-type") or content_type,
            path,
        )
        return MediaPayload(content=response.content, content_type=resolved_type)
