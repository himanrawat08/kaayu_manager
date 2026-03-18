from datetime import date, datetime

from app.utils.time import now_ist

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

STAGES = ["design", "laser_cutting", "polish", "pre_production_check", "production", "completed"]

STAGE_LABELS = {
    "design": "Design",
    "laser_cutting": "Laser Cutting",
    "polish": "Polish",
    "pre_production_check": "Pre-Production Check",
    "production": "Production",
    "completed": "Completed",
}


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_stage: Mapped[str] = mapped_column(String(50), default="design")
    status: Mapped[str] = mapped_column(String(50), default="active")

    # New fields
    completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    project_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    project_contact_phone: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_ist, onupdate=now_ist
    )

    client: Mapped["Client"] = relationship("Client", back_populates="projects")  # noqa: F821
    stage_logs: Mapped[list["StageLog"]] = relationship(
        "StageLog", back_populates="project", cascade="all, delete-orphan", order_by="StageLog.created_at"
    )
    design_revisions: Mapped[list["DesignRevision"]] = relationship(  # noqa: F821
        "DesignRevision", back_populates="project", cascade="all, delete-orphan",
        order_by="DesignRevision.revision_number"
    )
    brief_files: Mapped[list["ProjectBriefFile"]] = relationship(  # noqa: F821
        "ProjectBriefFile", back_populates="project", cascade="all, delete-orphan",
        order_by="ProjectBriefFile.uploaded_at"
    )
    design_files: Mapped[list["DesignFile"]] = relationship(  # noqa: F821
        "DesignFile", back_populates="project", cascade="all, delete-orphan",
        order_by="DesignFile.uploaded_at"
    )
    production_files: Mapped[list["ProductionFile"]] = relationship(  # noqa: F821
        "ProductionFile", back_populates="project", cascade="all, delete-orphan",
        order_by="ProductionFile.uploaded_at"
    )
    project_activities: Mapped[list["ProjectActivity"]] = relationship(  # noqa: F821
        "ProjectActivity", back_populates="project", cascade="all, delete-orphan",
        order_by="ProjectActivity.created_at"
    )
    quotations: Mapped[list["Quotation"]] = relationship(  # noqa: F821
        "Quotation", back_populates="project", cascade="all, delete-orphan",
    )


class StageLog(Base):
    __tablename__ = "stage_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)

    project: Mapped["Project"] = relationship("Project", back_populates="stage_logs")
