from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class GenerateApplicationRequest(BaseModel):
    url: str = ""
    offer_text: str = ""
    source: str = ""
    preferred_language: Literal["auto", "es", "en", "fr"] = "auto"

    @model_validator(mode="after")
    def require_offer_source(self):
        if len(self.offer_text.strip()) < 30 and not self.url.strip():
            raise ValueError("Paste at least 30 characters of offer text or provide a URL.")
        return self


class ApplicationUpdate(BaseModel):
    company: str | None = None
    role: str | None = None
    url: str | None = None
    source: str | None = None
    location: str | None = None
    work_mode: str | None = None
    contract_type: str | None = None
    language: Literal["es", "en", "fr"] | None = None
    salary: str | None = None
    fit_score: float | None = Field(default=None, ge=0, le=100)
    status: str | None = None
    applied_at: date | None = None
    next_follow_up: date | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    outcome: str | None = None
    rejection_reason: str | None = None
    notes: str | None = None


class InterviewCreate(BaseModel):
    kind: str
    scheduled_at: datetime | None = None
    interviewer: str = ""
    meeting_url: str = ""
    result: str = ""
    notes: str = ""


class ProfilePayload(BaseModel):
    data: dict[str, Any]
