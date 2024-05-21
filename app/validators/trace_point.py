from datetime import datetime
from typing import NamedTuple

from pydantic import NonNegativeInt

from app.models.db.base import Base
from app.models.geometry import PointPrecisionGeometry


class TracePointCollectionMember(NamedTuple):
    track_idx: NonNegativeInt
    captured_at: datetime
    point: PointPrecisionGeometry
    elevation: float | None


class TracePointCollectionValidating(Base.Validating):
    points: list[TracePointCollectionMember]
