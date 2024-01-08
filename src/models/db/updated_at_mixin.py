from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class UpdatedAtMixin:
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, onupdate=func.now())
