from datetime import datetime

from pydantic import NonNegativeInt

from src.models.db.base import Base
from src.models.geometry import PointGeometry


class TracePointValidating(Base.Validating):
    track_idx: NonNegativeInt
    captured_at: datetime
    point: PointGeometry
    elevation: float | None
