from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class UpdatedAt:
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_onupdate=func.now())
