from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ActorContext:
    """Transport-neutral actor metadata passed from controllers to use cases."""

    actor_id: str | None
    tenant_id: str | None = None
    ip: str | None = None
    user_agent: str | None = None
    correlation_id: str | None = None
