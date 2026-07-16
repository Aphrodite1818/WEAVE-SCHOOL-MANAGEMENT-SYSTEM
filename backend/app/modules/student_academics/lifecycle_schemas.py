"""Input schemas for academic-session opening and closure."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class AcademicSessionOpenRequest(BaseModel):
    """Open a prepared academic session as the tenant's current session."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(default="Academic session opened", min_length=3, max_length=500)


class AcademicSessionCloseRequest(BaseModel):
    """Close the current session and execute one idempotent progression run."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=8, max_length=150)
    effective_date: date
    reason: str = Field(default="End-of-session progression", min_length=3, max_length=500)
