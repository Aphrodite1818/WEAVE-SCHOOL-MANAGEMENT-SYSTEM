# ==========================#
#      AI SCHEMAS.PY       #
# ==========================#

"""Define request and message schemas used by the AI module."""

from enum import Enum
import re

from pydantic import BaseModel, field_validator


class Role(str, Enum):
    """Enumeration of supported AI values."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ConversationMessage(BaseModel):
    """Represent the ConversationMessage type."""

    role: Role
    content: str
    tool_name: str | None = None
    tool_call_id: str | None = None


class AIChatRequest(BaseModel):
    """Pydantic schema for the AI domain."""

    message: str
    phone_number: str
    tenant_id: str | None = None
    provider: str | None = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, value: str) -> str:
        """Validate phone number."""
        pattern = r"^\+?[1-9]\d{6,14}$"
        cleaned = re.sub(r"[\s\-().]+", "", value.strip())

        if not re.match(pattern, cleaned):
            raise ValueError(f"invalid phone number: {value}")
        return cleaned


def validate_phone_number(phone_number: str) -> str:
    """Validate phone number."""
    pattern = r"^\+?[1-9]\d{6,14}$"
    cleaned = re.sub(r"[\s\-().]+", "", phone_number.strip())

    if not re.match(pattern, cleaned):
        # Keep legacy behavior: this helper reports the issue but does not raise.
        print("weird number format")
    return cleaned
