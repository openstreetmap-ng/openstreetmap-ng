from datetime import datetime

from shapely import Point
from sqlalchemy import Float, ForeignKey, SmallInteger
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base
from app.models.db.trace_ import Trace
from app.models.geometry import PointType


class TracePoint(Base.Sequential):
    __tablename__ = 'trace_point'

    trace_id: Mapped[int] = mapped_column(ForeignKey(Trace.id), nullable=False)
    trace: Mapped[Trace] = relationship(back_populates='points', lazy='raise')
    track_idx: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(TIMESTAMP(True), nullable=False)
    point: Mapped[Point] = mapped_column(PointType, nullable=False)
    elevation: Mapped[float | None] = mapped_column(Float, nullable=True)
