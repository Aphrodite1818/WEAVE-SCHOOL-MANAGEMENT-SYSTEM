"""Focused request contracts for parent invitation acceptance."""

from pydantic import BaseModel, ConfigDict, Field


class ParentInvitationTokenOnlyRequest(BaseModel):
    """Invitation acceptance body; student identity travels in a header."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    invitation_token: str = Field(min_length=20, max_length=500)
