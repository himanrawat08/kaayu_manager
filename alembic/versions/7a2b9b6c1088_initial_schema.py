"""initial_schema

Revision ID: 7a2b9b6c1088
Revises:
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op
from app.database import Base
import app.models.activity       # noqa: F401
import app.models.client         # noqa: F401
import app.models.design         # noqa: F401
import app.models.lead           # noqa: F401
import app.models.project        # noqa: F401
import app.models.project_files  # noqa: F401
import app.models.quotation      # noqa: F401
import app.models.social_post    # noqa: F401
import app.models.system_log     # noqa: F401
import app.models.task           # noqa: F401
import app.models.user           # noqa: F401

revision: str = '7a2b9b6c1088'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
