from datetime import datetime

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column


# TODO: created_at not reliable to diff by when transaction?
class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(True), nullable=False, server_default=func.statement_timestamp()
    )
