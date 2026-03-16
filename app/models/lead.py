from datetime import datetime

from app.utils.time import now_ist

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

LEAD_STAGES = [
    "lead_in",
    "contact_made",
    "requirement_gathering",
    "quote_sent",
    "negotiation",
    "won",
    "lost",
]

LEAD_STAGE_LABELS = {
    "lead_in": "Lead In",
    "contact_made": "Contact Made",
    "requirement_gathering": "Requirement Gathering",
    "quote_sent": "Quote Sent",
    "negotiation": "Negotiation",
    "won": "Won",
    "lost": "Lost",
}

LEAD_SOURCES = {
    "walk_in": "Walk In",
    "referral": "Referral",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "google": "Google",
    "justdial": "JustDial",
    "website": "Website",
    "exhibition": "Exhibition",
    "cold_call": "Cold Call",
    "other": "Other",
}

LEAD_ACTIVITY_TYPES = {
    "call": "Call",
    "site_visit": "Site Visit",
    "email_sent": "Email Sent",
    "note": "Note",
    "follow_up": "Follow Up",
}


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False, unique=True)
    lead_code: Mapped[str] = mapped_column(String(20), unique=True)
    stage: Mapped[str] = mapped_column(String(50), default="lead_in")
    source: Mapped[str] = mapped_column(String(50), default="other")
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    lost_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_ist, onupdate=now_ist
    )

    client: Mapped["Client"] = relationship("Client", back_populates="lead")  # noqa: F821
    activities: Mapped[list["LeadActivity"]] = relationship(
        "LeadActivity", back_populates="lead", cascade="all, delete-orphan"
    )
    stage_history: Mapped[list["LeadStageHistory"]] = relationship(
        "LeadStageHistory", back_populates="lead", cascade="all, delete-orphan"
    )


class LeadActivity(Base):
    __tablename__ = "lead_activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)

    lead: Mapped["Lead"] = relationship("Lead", back_populates="activities")


class LeadStageHistory(Base):
    __tablename__ = "lead_stage_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), nullable=False)
    from_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    to_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)

    lead: Mapped["Lead"] = relationship("Lead", back_populates="stage_history")
