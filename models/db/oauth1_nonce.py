from datetime import datetime

from sqlalchemy import DateTime, Unicode, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from limits import OAUTH1_NONCE_MAX_LENGTH
from models.db.base import Base

# TODO: timestamp expire


class OAuth1Nonce(Base.NoID):
    __tablename__ = 'oauth1_nonce'

    nonce: Mapped[str] = mapped_column(Unicode(OAUTH1_NONCE_MAX_LENGTH), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (UniqueConstraint(nonce, created_at),)
