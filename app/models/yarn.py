from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.time import now_ist

LOW_STOCK_THRESHOLD = 5


class YarnColor(Base):
    __tablename__ = "yarn_colors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    color_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    opening_stock: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)

    transactions: Mapped[list["YarnTransaction"]] = relationship(
        "YarnTransaction", back_populates="color", cascade="all, delete-orphan"
    )


class YarnTransaction(Base):
    __tablename__ = "yarn_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    color_id: Mapped[int] = mapped_column(ForeignKey("yarn_colors.id"), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(3), nullable=False)  # "in" or "out"
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)

    color: Mapped["YarnColor"] = relationship("YarnColor", back_populates="transactions")
    project: Mapped["Project"] = relationship("Project")  # noqa: F821
