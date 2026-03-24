"""
Storage service — local filesystem (default) or Supabase Storage.

Backend selection:
  • If SUPABASE_URL is set in .env  → Supabase Storage  (Railway / cloud)
  • Otherwise                        → local filesystem  (VPS / dev)

Local files are stored under  <project_root>/uploads/<path>
and served by FastAPI's StaticFiles mount at  /uploads/<path>.
"""

import logging
import mimetypes
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Project root → uploads directory
_UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"


# ── Backend detection ─────────────────────────────────────────────────────────

def _use_supabase() -> bool:
    return bool(settings.SUPABASE_URL and settings.SUPABASE_URL.strip())


# ── Supabase helpers ──────────────────────────────────────────────────────────

def _sb_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
        "apikey": settings.SUPABASE_SERVICE_KEY,
    }


def _sb_upload(path: str, data: bytes, filename: str) -> None:
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    url = (
        f"{settings.SUPABASE_URL.strip()}/storage/v1/object"
        f"/{settings.SUPABASE_BUCKET.strip()}/{path}"
    )
    logger.info("Uploading to Supabase: %s", url)
    resp = httpx.post(
        url,
        content=data,
        headers={**_sb_headers(), "Content-Type": content_type},
        timeout=120.0,
    )
    logger.info("Upload response: %s %s", resp.status_code, resp.text)
    resp.raise_for_status()


def _sb_delete(path: str) -> None:
    url = (
        f"{settings.SUPABASE_URL.strip()}/storage/v1/object"
        f"/{settings.SUPABASE_BUCKET.strip()}"
    )
    try:
        resp = httpx.delete(url, json={"prefixes": [path]}, headers=_sb_headers())
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Could not delete Supabase file %s: %s", path, exc)


def _sb_public_url(path: str) -> str:
    return (
        f"{settings.SUPABASE_URL.strip()}/storage/v1/object/public"
        f"/{settings.SUPABASE_BUCKET.strip()}/{path}"
    )


# ── Local filesystem helpers ──────────────────────────────────────────────────

def _local_upload(path: str, data: bytes, filename: str) -> None:
    dest = _UPLOADS_DIR / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    logger.info("Saved file locally: %s", dest)


def _local_delete(path: str) -> None:
    dest = _UPLOADS_DIR / path
    try:
        dest.unlink(missing_ok=True)
        logger.info("Deleted local file: %s", dest)
    except Exception as exc:
        logger.warning("Could not delete local file %s: %s", path, exc)


def _local_public_url(path: str) -> str:
    return f"/uploads/{path}"


# ── Public API ────────────────────────────────────────────────────────────────

def upload(path: str, data: bytes, filename: str) -> None:
    """Upload bytes to the configured storage backend at the given path."""
    if _use_supabase():
        _sb_upload(path, data, filename)
    else:
        _local_upload(path, data, filename)


def delete(path: str) -> None:
    """Delete a file from the configured storage backend."""
    if _use_supabase():
        _sb_delete(path)
    else:
        _local_delete(path)


def public_url(path: str) -> str:
    """Return the public URL for a stored file."""
    if _use_supabase():
        return _sb_public_url(path)
    return _local_public_url(path)
