import json
from datetime import datetime

from app.utils.time import now_ist

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)  # Studio Name

    # Architecture-specific contact fields (legacy single-value — kept for backward compat)
    principal_architect_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    principal_architect_numbers: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_person_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_person_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Multi-value JSON fields
    principal_architects_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_persons_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Location
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Contact
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Legacy columns kept for DB compatibility
    phone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_ist)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_ist, onupdate=now_ist
    )

    activities: Mapped[list["ClientActivity"]] = relationship(  # noqa: F821
        "ClientActivity", back_populates="client",
        cascade="all, delete-orphan",
    )
    projects: Mapped[list["Project"]] = relationship(  # noqa: F821
        "Project", back_populates="client", cascade="all, delete-orphan"
    )
    lead: Mapped["Lead | None"] = relationship(  # noqa: F821
        "Lead", back_populates="client", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def architect_numbers_list(self) -> list[str]:
        if not self.principal_architect_numbers:
            return []
        return [n.strip() for n in self.principal_architect_numbers.split(",") if n.strip()]

    @property
    def principal_architects_list(self) -> list[dict]:
        if self.principal_architects_json:
            try:
                return json.loads(self.principal_architects_json)
            except (json.JSONDecodeError, TypeError):
                pass
        if self.principal_architect_name:
            return [{"name": self.principal_architect_name, "numbers": self.architect_numbers_list}]
        return []

    @property
    def contact_persons_list(self) -> list[dict]:
        if self.contact_persons_json:
            try:
                return json.loads(self.contact_persons_json)
            except (json.JSONDecodeError, TypeError):
                pass
        if self.contact_person_name:
            return [{"name": self.contact_person_name, "number": self.contact_person_number or ""}]
        return []
