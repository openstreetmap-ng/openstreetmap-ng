from datetime import datetime

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, MappedAsDataclass, mapped_column


class UpdatedAtMixin(MappedAsDataclass):
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(True),
        init=False,
        nullable=False,
        server_default=func.statement_timestamp(),
        onupdate=func.statement_timestamp(),
    )
