from datetime import datetime

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column


class UpdatedAtMixin:
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(True),
        nullable=False,
        server_default=func.statement_timestamp(),
        server_onupdate=func.statement_timestamp(),
    )
