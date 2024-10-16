"""Hashed client_secret and preview

Revision ID: 1e23c648010a
Revises: 701a84ad141f
Create Date: 2024-10-16 14:52:37.358221+00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1e23c648010a'
down_revision: str | None = '701a84ad141f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('oauth2_application', sa.Column('client_secret_hashed', sa.LargeBinary(length=32), nullable=True))
    op.add_column('oauth2_application', sa.Column('client_secret_preview', sa.Unicode(length=7), nullable=True))
    op.drop_column('oauth2_application', 'client_secret_encrypted')
    # ### end Alembic commands ###


def downgrade() -> None:
    ...
