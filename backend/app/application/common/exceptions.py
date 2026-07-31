from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ApplicationError(Exception):
    """Base class for use-case errors that API adapters map to HTTP responses."""

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class NotFoundError(ApplicationError):
    pass


class ConflictError(ApplicationError):
    pass


class BusinessRuleViolation(ApplicationError):
    pass


class ForbiddenError(ApplicationError):
    pass
