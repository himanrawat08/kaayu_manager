"""
Supabase Storage service.
Handles upload, delete, and public URL generation for project files.
"""

import logging
import mimetypes

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
        "apikey": settings.SUPABASE_SERVICE_KEY,
    }


def upload(path: str, data: bytes, filename: str) -> None:
    """Upload bytes to Supabase Storage at the given path within the bucket."""
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    url = f"{settings.SUPABASE_URL}/storage/v1/object/{settings.SUPABASE_BUCKET}/{path}"
    logger.info("Uploading to: %s", url)
    resp = httpx.post(
        url,
        content=data,
        headers={**_headers(), "Content-Type": content_type},
        timeout=120.0,  # 2-minute timeout for large file uploads
    )
    logger.info("Upload response: %s %s", resp.status_code, resp.text)
    resp.raise_for_status()


def delete(path: str) -> None:
    """Delete a file from Supabase Storage."""
    url = f"{settings.SUPABASE_URL}/storage/v1/object/{settings.SUPABASE_BUCKET}"
    try:
        resp = httpx.delete(url, json={"prefixes": [path]}, headers=_headers())
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Could not delete storage file %s: %s", path, exc)


def public_url(path: str) -> str:
    """Return the public URL for a file stored in the bucket."""
    return f"{settings.SUPABASE_URL}/storage/v1/object/public/{settings.SUPABASE_BUCKET}/{path}"
