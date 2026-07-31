"""initial schema for Smart Report Builder and NL2SQL

Revision ID: 202607310001
Revises:
Create Date: 2026-07-31 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

from app.db.base import Base
from app.models import domain  # noqa: F401 - registers metadata tables

# revision identifiers, used by Alembic.
revision = "202607310001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
