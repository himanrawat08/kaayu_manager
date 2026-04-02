from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.time import now_ist


class JobCard(Base):
    __tablename__ = "job_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_card_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    receive_by_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist, onupdate=now_ist)

    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="job_cards")  # noqa: F821
    project: Mapped["Project | None"] = relationship("Project")  # noqa: F821
    items: Mapped[list["JobCardItem"]] = relationship(
        "JobCardItem", back_populates="job_card",
        cascade="all, delete-orphan", order_by="JobCardItem.sr_no",
    )


class JobCardItem(Base):
    __tablename__ = "job_card_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_card_id: Mapped[int] = mapped_column(ForeignKey("job_cards.id"), nullable=False)
    sr_no: Mapped[int] = mapped_column(Integer, default=0)
    particular_name: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    rate: Mapped[float] = mapped_column(Float, default=0.0)
    amount: Mapped[float] = mapped_column(Float, default=0.0)

    job_card: Mapped["JobCard"] = relationship("JobCard", back_populates="items")
