from datetime import datetime

from shapely import Point
from sqlalchemy import DateTime, Float, ForeignKey, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db.base import Base
from src.models.db.trace_ import Trace
from src.models.geometry_type import PointType


class TracePoint(Base.UUID):
    __tablename__ = 'trace_point'

    trace_id: Mapped[int] = mapped_column(ForeignKey(Trace.id), nullable=False)
    trace: Mapped[Trace] = relationship(back_populates='trace_points', lazy='raise')
    track_idx: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    point: Mapped[Point] = mapped_column(PointType, nullable=False)
    elevation: Mapped[float | None] = mapped_column(Float, nullable=True)
