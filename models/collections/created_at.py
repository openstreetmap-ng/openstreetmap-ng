from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class CreatedAt:
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
