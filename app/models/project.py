from datetime import date, datetime

from app.utils.time import now_ist

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

SALES_FLOW_STAGES = ["preliminary_design", "quote_sent", "quote_accepted"]
SALES_OUTCOME_STAGES = ["hold", "won", "lost"]
SALES_STAGES = SALES_FLOW_STAGES + SALES_OUTCOME_STAGES
PRODUCTION_STAGES = ["design", "laser_cutting", "polish", "pre_production_check", "production", "completed"]
STAGES = SALES_STAGES + PRODUCTION_STAGES

STAGE_LABELS = {
    "preliminary_design": "Preliminary Design",
    "quote_sent": "Quote Sent",
    "quote_accepted": "Quote Accepted",
    "hold": "Hold",
    "won": "Won",
    "lost": "Lost",
    "design": "Design",
    "laser_cutting": "Laser Cutting",
    "polish": "Polish",
    "pre_production_check": "Pre-Production Check",
    "production": "Production",
    "completed": "Completed",
}

# Maps each stage to the next stage for the "Advance" button.
# Outcome stages (hold, lost) are not in this map — no automatic advance.
# Won advances to Design (enters production pipeline).
STAGE_ADVANCE_MAP = {
    "preliminary_design": "quote_sent",
    "quote_sent":         "quote_accepted",
    "quote_accepted":     "design",
    "won":                "design",
    "design":             "laser_cutting",
    "laser_cutting":      "polish",
    "polish":             "pre_production_check",
    "pre_production_check": "production",
    "production":         "completed",
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

    # Order number (auto-assigned, e.g. KS/0001)
    order_number: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)

    # Production sheet details
    prod_design_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    prod_size: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prod_polish_stain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prod_polish_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prod_veneer_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prod_design_page: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)

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
