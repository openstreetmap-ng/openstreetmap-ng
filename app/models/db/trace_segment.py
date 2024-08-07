from datetime import datetime

from shapely import MultiPoint
from sqlalchemy import ARRAY, REAL, ForeignKey, Index, PrimaryKeyConstraint, SmallInteger
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base
from app.models.db.trace_ import Trace
from app.models.geometry import MultiPointType


class TraceSegment(Base.NoID):
    __tablename__ = 'trace_segment'

    trace_id: Mapped[int] = mapped_column(ForeignKey(Trace.id, ondelete='CASCADE'), init=False, nullable=False)
    trace: Mapped[Trace] = relationship(init=False, lazy='raise', innerjoin=True)
    track_num: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    segment_num: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    points: Mapped[MultiPoint] = mapped_column(MultiPointType, nullable=False)
    capture_times: Mapped[list[datetime | None] | None] = mapped_column(
        ARRAY(TIMESTAMP(True), dimensions=1), nullable=True
    )
    elevations: Mapped[list[float | None] | None] = mapped_column(ARRAY(REAL, dimensions=1), nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint(trace_id, track_num, segment_num),
        Index(
            'trace_segment_points_idx',
            points,
            postgresql_using='gist',
        ),
    )
