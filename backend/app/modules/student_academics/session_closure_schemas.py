"""Schemas for the staged academic-session closure workflow."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import Field

from app.modules.student_academics.schemas import (
    AcademicSessionResponse,
    InputBase,
    OutputBase,
    StudentProgressionRunDetailResponse,
)


class SessionClosureStartRequest(InputBase):
    confirmation: Literal["START_SESSION_CLOSING"]
    idempotency_key: str = Field(min_length=8, max_length=150)
    allow_terminal_completion: bool = False


class SessionClosureFinalizeRequest(InputBase):
    confirmation: Literal["FINALIZE_SESSION_CLOSE"]


class SessionProgressionRetryRequest(InputBase):
    confirmation: Literal["RETRY_SESSION_PROGRESSION"]


class SessionClosureAuditResponse(OutputBase):
    session_id: uuid.UUID
    is_ready: bool
    dependency_counts: dict[str, int]
    blocker_messages: list[str]
    checked_items: list[str]
    terminal_students: int = 0
    requires_terminal_confirmation: bool = False


class SessionClosureStartResponse(OutputBase):
    started: bool
    session: AcademicSessionResponse
    audit: SessionClosureAuditResponse
    progression_run: StudentProgressionRunDetailResponse | None = None
    queued: bool = False


class SessionClosureStatusResponse(OutputBase):
    session: AcademicSessionResponse
    audit: SessionClosureAuditResponse
    progression_run: StudentProgressionRunDetailResponse | None = None
    can_finalize: bool
    writes_paused: bool


class SessionClosureFinalizeResponse(OutputBase):
    closed_session: AcademicSessionResponse
    next_session: AcademicSessionResponse | None = None
    progression_run: StudentProgressionRunDetailResponse
