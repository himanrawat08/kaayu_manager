import binascii
import hashlib
import hmac
import os
from datetime import datetime

from app.utils.time import now_ist

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

USER_ROLES = ["super_admin", "admin", "sales", "design", "viewer"]

USER_ROLE_LABELS = {
    "super_admin": "Super Admin",
    "admin":       "Admin",
    "sales":       "Sales",
    "design":      "Design",
    "viewer":      "Viewer",
}

USER_ROLE_CLS = {
    "super_admin": "bg-[#2E2E2E] text-white",
    "admin":       "bg-[#B17457] text-white",
    "sales":       "bg-blue-100 text-blue-700 border border-blue-200",
    "design":      "bg-[#637C60] text-white",
    "viewer":      "bg-gray-100 text-gray-600 border border-gray-300",
}


def hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256 with random salt. No external deps."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return binascii.hexlify(salt).decode() + ":" + binascii.hexlify(key).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, key_hex = stored.split(":", 1)
        salt = binascii.unhexlify(salt_hex)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
        # Constant-time comparison prevents timing-based attacks
        return hmac.compare_digest(binascii.hexlify(key).decode(), key_hex)
    except Exception:
        return False


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="sales", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_ist, onupdate=now_ist
    )
