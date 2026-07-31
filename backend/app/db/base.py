from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    """Shared declarative base with predictable table names."""

    @declared_attr.directive
    def __tablename__(cls) -> str:
        name = cls.__name__
        table = []
        for index, char in enumerate(name):
            if char.isupper() and index > 0:
                table.append("_")
            table.append(char.lower())
        return "".join(table)
