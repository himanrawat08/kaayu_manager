from datetime import date, datetime

from app.utils.time import now_ist

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

TASK_PRIORITIES = ["high", "medium", "low"]
TASK_PRIORITY_LABELS = {"high": "High", "medium": "Medium", "low": "Low"}
TASK_PRIORITY_COLORS = {"high": "red", "medium": "amber", "low": "gray"}

TASK_STATUSES = ["todo", "in_progress", "review", "done"]
TASK_STATUS_LABELS = {
    "todo": "To Do",
    "in_progress": "In Progress",
    "review": "Review",
    "done": "Done",
}

TASK_DEPARTMENTS = [
    "Design",
    "Marketing",
    "Logistics",
    "Admin",
    "Production",
    "Accounts",
    "Operations",
    "Sales",
]

NOTE_TYPES = ["comment", "feedback", "revision_request", "approval"]
NOTE_TYPE_LABELS = {
    "comment": "Comment",
    "feedback": "Feedback",
    "revision_request": "Revision Request",
    "approval": "Approved",
}


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    assigned_to: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma-separated full names
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)

    # Extended fields
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="todo", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist, onupdate=now_ist)

    project: Mapped["Project"] = relationship("Project")  # noqa: F821
    thread: Mapped[list["TaskNote"]] = relationship(
        "TaskNote",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskNote.created_at",
    )
    subtasks: Mapped[list["SubTask"]] = relationship(
        "SubTask",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="SubTask.created_at",
    )
    files: Mapped[list["TaskFile"]] = relationship(
        "TaskFile",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskFile.created_at",
    )


class TaskNote(Base):
    __tablename__ = "task_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    note_type: Mapped[str] = mapped_column(String(50), default="comment", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)

    task: Mapped["Task"] = relationship("Task", back_populates="thread")


class SubTask(Base):
    __tablename__ = "subtasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma-separated full names
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)

    task: Mapped["Task"] = relationship("Task", back_populates="subtasks")
    notes: Mapped[list["SubTaskNote"]] = relationship(
        "SubTaskNote",
        back_populates="subtask",
        cascade="all, delete-orphan",
        order_by="SubTaskNote.created_at",
    )


class SubTaskNote(Base):
    __tablename__ = "subtask_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    subtask_id: Mapped[int] = mapped_column(
        ForeignKey("subtasks.id", ondelete="CASCADE"), nullable=False
    )
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    note_type: Mapped[str] = mapped_column(String(50), default="comment", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)

    subtask: Mapped["SubTask"] = relationship("SubTask", back_populates="notes")


class TaskFile(Base):
    __tablename__ = "task_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    subtask_id: Mapped[int | None] = mapped_column(
        ForeignKey("subtasks.id", ondelete="CASCADE"), nullable=True
    )
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)

    task: Mapped["Task"] = relationship("Task", back_populates="files")
