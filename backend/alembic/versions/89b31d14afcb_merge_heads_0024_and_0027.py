"""merge heads 0024 and 0027

Revision ID: 89b31d14afcb
Revises: 20260412_0024, 20260412_0027
Create Date: 2026-04-12 16:13:14.992724

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '89b31d14afcb'
down_revision = ('20260412_0024', '20260412_0027')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

