"""Schemas for legal compliance acceptance."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LegalComplianceStatusResponse(BaseModel):
    policy_version: str
    accepted: bool
    accepted_at: datetime | None = None


class LegalComplianceAcceptanceResponse(LegalComplianceStatusResponse):
    detail: str = "Legal compliance terms accepted."
