from datetime import date, datetime

from app.utils.time import now_ist

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

QUOTE_STATUSES = ["draft", "sent", "accepted", "rejected"]

QUOTE_STATUS_LABELS = {
    "draft":    "Draft",
    "sent":     "Sent",
    "accepted": "Accepted",
    "rejected": "Rejected",
}

QUOTE_STATUS_CLS = {
    "draft":    "bg-gray-100 text-gray-600 border border-gray-200",
    "sent":     "bg-blue-50 text-blue-700 border border-blue-200",
    "accepted": "bg-green-50 text-green-700 border border-green-200",
    "rejected": "bg-red-50 text-red-600 border border-red-200",
}


class Quotation(Base):
    __tablename__ = "quotations"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_number: Mapped[str | None] = mapped_column(String(250), nullable=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)

    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    terms_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Client & contact info (quote-specific, may differ from project client)
    client_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    client_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_number: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Payment details
    payment_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_account_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payment_account_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payment_ifsc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    payment_bank_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    discount_type: Mapped[str | None] = mapped_column(String(10), nullable=True)  # 'percent' or 'flat'
    discount_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    cgst_percent: Mapped[float] = mapped_column(Float, default=9.0, nullable=False)
    sgst_percent: Mapped[float] = mapped_column(Float, default=9.0, nullable=False)
    igst_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Calculated totals — stored for fast display, recalculated on every save
    subtotal: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    discount_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    taxable_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cgst_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sgst_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    igst_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist, onupdate=now_ist)

    project: Mapped["Project"] = relationship("Project", back_populates="quotations")  # noqa: F821
    items: Mapped[list["QuoteItem"]] = relationship(
        "QuoteItem", back_populates="quotation",
        cascade="all, delete-orphan", order_by="QuoteItem.sort_order",
    )
    sundries: Mapped[list["QuoteSundry"]] = relationship(
        "QuoteSundry", back_populates="quotation",
        cascade="all, delete-orphan", order_by="QuoteSundry.sort_order",
    )


class QuoteItem(Base):
    __tablename__ = "quote_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotations.id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    size: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_name: Mapped[str] = mapped_column(Text, nullable=False)
    material: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    qty: Mapped[float] = mapped_column(Float, default=1.0)
    unit: Mapped[str] = mapped_column(String(20), default="pcs")
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    gst_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)

    quotation: Mapped["Quotation"] = relationship("Quotation", back_populates="items")


class QuoteSundry(Base):
    __tablename__ = "quote_sundries"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotations.id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    particular: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)

    quotation: Mapped["Quotation"] = relationship("Quotation", back_populates="sundries")
