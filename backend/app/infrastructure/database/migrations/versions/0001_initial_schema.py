"""Initial schema — all platform tables from ORM metadata.

Revision ID: 0001
Revises:
Create Date: 2026-07-16
"""

from alembic import op

from app.infrastructure.database.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
