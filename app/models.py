from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company: Mapped[str] = mapped_column(String(200), default="")
    role: Mapped[str] = mapped_column(String(250), default="")
    url: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(100), default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    work_mode: Mapped[str] = mapped_column(String(50), default="")
    contract_type: Mapped[str] = mapped_column(String(100), default="")
    language: Mapped[str] = mapped_column(String(10), default="en")
    salary: Mapped[str] = mapped_column(String(150), default="")
    status: Mapped[str] = mapped_column(String(50), default="Nueva")
    fit_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    offer_text: Mapped[str] = mapped_column(Text, default="")
    analysis_json: Mapped[str] = mapped_column(Text, default="{}")
    generated_content_json: Mapped[str] = mapped_column(Text, default="{}")
    cv_path: Mapped[str] = mapped_column(Text, default="")
    letter_path: Mapped[str] = mapped_column(Text, default="")
    applied_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_follow_up: Mapped[date | None] = mapped_column(Date, nullable=True)
    contact_name: Mapped[str] = mapped_column(String(200), default="")
    contact_email: Mapped[str] = mapped_column(String(250), default="")
    outcome: Mapped[str] = mapped_column(String(100), default="")
    rejection_reason: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    interviews: Mapped[list["Interview"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    kind: Mapped[str] = mapped_column(String(100), default="")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    interviewer: Mapped[str] = mapped_column(String(200), default="")
    meeting_url: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[str] = mapped_column(String(100), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    application: Mapped[Application] = relationship(back_populates="interviews")

