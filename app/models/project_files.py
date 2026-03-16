from datetime import date, datetime

from app.utils.time import now_ist

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

PRODUCTION_FILE_CATEGORIES = {
    "laser_cutting": "Laser Cutting File",
    "stitch": "Stitch File",
    "colour": "Colour File",
}


class ProjectBriefFile(Base):
    __tablename__ = "project_brief_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)

    project: Mapped["Project"] = relationship("Project", back_populates="brief_files")  # noqa: F821


# Defined before DesignFile so we can reference the column directly in order_by
class DesignFileFeedback(Base):
    __tablename__ = "design_file_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    design_file_id: Mapped[int] = mapped_column(ForeignKey("design_files.id"), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)

    design_file: Mapped["DesignFile"] = relationship("DesignFile", back_populates="feedback_entries")


class DesignFile(Base):
    __tablename__ = "design_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)  # legacy
    next_revision_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)

    project: Mapped["Project"] = relationship("Project", back_populates="design_files")  # noqa: F821
    feedback_entries: Mapped[list["DesignFileFeedback"]] = relationship(
        "DesignFileFeedback",
        back_populates="design_file",
        cascade="all, delete-orphan",
        order_by=DesignFileFeedback.created_at,
    )


class ProductionFile(Base):
    __tablename__ = "production_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    file_category: Mapped[str] = mapped_column(String(50), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)

    project: Mapped["Project"] = relationship("Project", back_populates="production_files")  # noqa: F821
