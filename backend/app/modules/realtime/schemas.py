# ====================================== #
#       modules/realtime/schemas.py      #
# ====================================== #

"""Generic contracts for Weave realtime events and routing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


RealtimeAudienceKind = Literal[
    "actor",
    "tenant",
    "broadcast",
]


class RealtimeContract(BaseModel):
    """Base configuration shared by realtime contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )


class RealtimeEvent(RealtimeContract):
    """
    A generic realtime event.

    The realtime infrastructure does not understand domain business logic.
    Each domain decides the event type and payload it publishes.
    """

    event_id: UUID = Field(
        default_factory=uuid4,
    )

    type: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    )

    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    data: dict[str, Any] = Field(
        default_factory=dict,
    )


class RealtimeAudience(RealtimeContract):
    """
    Internal routing target for a realtime event.

    actor:
        Send to one specific authenticated actor.

    tenant:
        Send to every connected actor belonging to one tenant.

    broadcast:
        Send to every connected realtime client.
    """

    kind: RealtimeAudienceKind

    actor_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9_]*$",
    )

    actor_id: UUID | None = None

    tenant_id: UUID | None = None

    @model_validator(mode="after")
    def validate_target(self) -> "RealtimeAudience":
        if self.kind == "actor":
            if self.actor_type is None or self.actor_id is None:
                raise ValueError("Actor audience requires actor_type and actor_id.")

            return self

        if self.kind == "tenant":
            if self.tenant_id is None:
                raise ValueError("Tenant audience requires tenant_id.")

            if self.actor_type is not None or self.actor_id is not None:
                raise ValueError("Tenant audience cannot include actor routing fields.")

            return self

        # broadcast
        if self.actor_type is not None or self.actor_id is not None or self.tenant_id is not None:
            raise ValueError("Broadcast audience cannot include actor or tenant routing fields.")

        return self


class RealtimeBrokerMessage(RealtimeContract):
    """
    Internal Redis transport message

    This contract is used between Weave processes
    It is not sent directly to the browser
    """

    event: RealtimeEvent
    audience: RealtimeAudience


class RealtimeAuthFrame(RealtimeContract):
    type: Literal["auth"]
    access_token: str = Field(min_length=1)


class RealtimeAuthRefreshFrame(RealtimeContract):
    type: Literal["auth.refresh"]
    access_token: str = Field(min_length=1)


class RealtimePingFrame(RealtimeContract):
    type: Literal["ping"]


RealtimeClientControlFrame = Annotated[
    RealtimeAuthFrame | RealtimeAuthRefreshFrame | RealtimePingFrame,
    Field(discriminator="type"),
]


class RealtimeConnectionReadyFrame(RealtimeContract):
    type: Literal["connection.ready"] = "connection.ready"
    connection_id: UUID
    token_expires_at: datetime


class RealtimeAuthRefreshedFrame(RealtimeContract):
    type: Literal["auth.refreshed"] = "auth.refreshed"
    token_expires_at: datetime


class RealtimePongFrame(RealtimeContract):
    type: Literal["pong"] = "pong"
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RealtimeErrorFrame(RealtimeContract):
    type: Literal["error"] = "error"
    code: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=256)
