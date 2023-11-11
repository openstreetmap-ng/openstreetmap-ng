from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


# TODO: created_at not reliable to diff by when transaction?
class CreatedAt:
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
