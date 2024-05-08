from datetime import datetime

from pydantic import NonNegativeInt

from app.models.db.base import Base
from app.models.geometry import PointPrecisionGeometry


class TracePointValidating(Base.Validating):
    track_idx: NonNegativeInt
    captured_at: datetime
    point: PointPrecisionGeometry
    elevation: float | None
