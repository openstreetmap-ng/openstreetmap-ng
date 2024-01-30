from datetime import datetime

from sqlalchemy import PrimaryKeyConstraint, Unicode
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.limits import OAUTH1_NONCE_MAX_LENGTH
from app.models.db.base import Base

# TODO: timestamp expire, pruner


class OAuth1Nonce(Base.NoID):
    __tablename__ = 'oauth1_nonce'

    nonce: Mapped[str] = mapped_column(Unicode(OAUTH1_NONCE_MAX_LENGTH), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(True), nullable=False)

    __table_args__ = (PrimaryKeyConstraint(nonce, created_at),)
