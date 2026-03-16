from datetime import date, datetime

from app.utils.time import now_ist

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

PLATFORMS = ["instagram", "facebook", "twitter", "linkedin", "youtube"]
PLATFORM_LABELS = {
    "instagram": "Instagram",
    "facebook": "Facebook",
    "twitter": "Twitter/X",
    "linkedin": "LinkedIn",
    "youtube": "YouTube",
}
PLATFORM_EMOJIS = {
    "instagram": "📸",
    "facebook": "📘",
    "twitter": "𝕏",
    "linkedin": "💼",
    "youtube": "▶️",
}
PLATFORM_CHIP_CLS = {
    "instagram": "bg-pink-100 text-pink-700 border border-pink-200",
    "facebook": "bg-blue-100 text-blue-700 border border-blue-200",
    "twitter": "bg-sky-100 text-sky-700 border border-sky-200",
    "linkedin": "bg-indigo-100 text-indigo-700 border border-indigo-200",
    "youtube": "bg-red-100 text-red-700 border border-red-200",
}

CONTENT_TYPES = ["post", "story", "reel", "carousel", "video", "thread"]
CONTENT_TYPE_LABELS = {
    "post": "Post",
    "story": "Story",
    "reel": "Reel",
    "carousel": "Carousel",
    "video": "Video",
    "thread": "Thread",
}

POST_STATUSES = ["draft", "scheduled", "published", "cancelled"]
POST_STATUS_LABELS = {
    "draft": "Draft",
    "scheduled": "Scheduled",
    "published": "Published",
    "cancelled": "Cancelled",
}
POST_STATUS_CLS = {
    "draft": "bg-gray-100 text-gray-600 border border-gray-200",
    "scheduled": "bg-blue-50 text-blue-700 border border-blue-200",
    "published": "bg-green-50 text-green-700 border border-green-200",
    "cancelled": "bg-red-50 text-red-500 border border-red-200",
}


class SocialPost(Base):
    __tablename__ = "social_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), default="post", nullable=False)
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    scheduled_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    campaign: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_ist, onupdate=now_ist
    )

    task: Mapped["Task"] = relationship("Task")  # noqa: F821
