from __future__ import annotations

from sqlalchemy.orm import Session

from app.infrastructure.repositories.sqlalchemy_repositories import (
    SQLAlchemyAuditRepository,
    SQLAlchemyKnowledgeRepository,
    SQLAlchemySoftwareRepository,
)


class SQLAlchemyUnitOfWork:
    """SQLAlchemy adapter for application use cases.

    Routers create this adapter at the composition root. Use cases only know the UnitOfWorkPort
    protocol and remain independent from FastAPI and direct session handling.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.software = SQLAlchemySoftwareRepository(session)
        self.knowledge = SQLAlchemyKnowledgeRepository(session)
        self.audit = SQLAlchemyAuditRepository(session)

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
